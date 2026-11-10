import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.common.logging import configure_logging
from app.common.rate_limit import RateLimiter
from app.config import Settings
from app.main import create_app


def test_request_log_contains_trace_data_without_query_string(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        app_env="test",
        temp_root=tmp_path / "storage",
        cleanup_interval_seconds=3600,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/health?token=super-secret",
            headers={"X-Request-ID": "trace-123"},
        )

    assert response.status_code == 200
    log_text = (tmp_path / "logs" / "app.jsonl").read_text(encoding="utf-8")
    records = [json.loads(line) for line in log_text.splitlines()]
    request_log = next(record for record in records if record["event"] == "http_request")

    assert request_log["request_id"] == "trace-123"
    assert request_log["method"] == "GET"
    assert request_log["path"] == "/api/v1/health"
    assert request_log["status_code"] == 200
    assert request_log["duration_ms"] >= 0
    assert request_log["client_ip"]
    assert "super-secret" not in log_text


def test_trusted_proxy_ip_is_used_for_request_logging(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        app_env="test",
        temp_root=tmp_path / "storage",
        trust_proxy_headers=True,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health", headers={"X-Real-IP": "203.0.113.10"})

    assert response.status_code == 200
    records = [
        json.loads(line)
        for line in (tmp_path / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    request_log = next(record for record in records if record["event"] == "http_request")
    assert request_log["client_ip"] == "203.0.113.10"


def test_file_log_rotates_after_reaching_size_limit(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        app_env="test",
        temp_root=tmp_path / "storage",
        log_max_bytes=1024,
        log_backup_count=2,
    )
    configure_logging(settings)
    logger = logging.getLogger("rotation-test")

    for index in range(30):
        logger.info("rotation-%s-%s", index, "x" * 80)
    logging.shutdown()

    assert (tmp_path / "logs" / "app.jsonl").is_file()
    assert (tmp_path / "logs" / "app.jsonl.1").is_file()


def test_general_api_rate_limit_returns_retry_after(test_settings):
    settings = test_settings.model_copy(update={"rate_limit_per_minute": 1})
    with TestClient(create_app(settings)) as client:
        client.get("/api/v1/health")
        first = client.post("/api/v1/qrcode/mac/parse", json={"value": "AA:BB:CC:DD:EE:FF"})
        limited = client.post("/api/v1/qrcode/mac/parse", json={"value": "AA:BB:CC:DD:EE:FF"})

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1


def test_excel_rate_limit_has_separate_budget(test_settings):
    settings = test_settings.model_copy(update={"excel_rate_limit_per_minute": 1})
    with TestClient(create_app(settings)) as client:
        client.get("/api/v1/health")
        first = client.post(
            "/api/v1/excel/inspect",
            files={"files": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        )
        limited = client.post(
            "/api/v1/excel/inspect",
            files={"files": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        )

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_cors_allows_only_configured_origin(test_settings):
    settings = test_settings.model_copy(update={"cors_origins": "https://allowed.example"})
    with TestClient(create_app(settings)) as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "https://allowed.example"})
        rejected = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["Access-Control-Allow-Origin"] == "https://allowed.example"
    assert "Access-Control-Allow-Origin" not in rejected.headers


def test_cors_wildcard_is_rejected(test_settings):
    settings = test_settings.model_copy(update={"cors_origins": "*"})
    with pytest.raises(ValueError, match="通配符"):
        create_app(settings)


def test_rate_limit_window_resets_and_entry_cache_stays_bounded():
    now = 100.0
    limiter = RateLimiter(
        window_seconds=60,
        max_entries=2,
        clock=lambda: now,
    )

    assert limiter.check("first", 1).allowed is True
    assert limiter.check("first", 1).allowed is False
    assert limiter.check("second", 1).allowed is True
    assert limiter.check("third", 1).allowed is True
    assert limiter.check("first", 1).allowed is True

    now = 161.0
    assert limiter.check("first", 1).allowed is True


def test_rate_limit_concurrent_requests_cannot_exceed_limit():
    limiter = RateLimiter(
        window_seconds=60,
        max_entries=100,
        clock=lambda: 100.0,
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: limiter.check("same-client", 5), range(30)))

    assert sum(result.allowed for result in results) == 5
