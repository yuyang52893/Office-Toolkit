import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.common.logging import configure_logging
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
