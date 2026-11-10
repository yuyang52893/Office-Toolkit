import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.common.logging import DailyCappedFileHandler, JsonFormatter, cleanup_runtime_logs
from app.config import Settings
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.security.passwords import hash_password

SHANGHAI = timezone(timedelta(hours=8))


def make_handler(root: Path, *, max_bytes: int = 4096, total_max_bytes: int = 64 * 1024 * 1024):
    handler = DailyCappedFileHandler(
        root,
        max_bytes=max_bytes,
        retention_days=14,
        total_max_bytes=total_max_bytes,
    )
    handler.setFormatter(JsonFormatter())
    return handler


def make_logger(handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(f"runtime-test-{id(handler)}")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def test_runtime_error_file_filters_level_and_stops_at_daily_cap(tmp_path: Path):
    handler = make_handler(tmp_path, max_bytes=1024)
    logger = make_logger(handler)

    logger.info("not-persisted")
    for index in range(100):
        logger.error("failure-%s-%s", index, "x" * 100)
    handler.close()

    files = list(tmp_path.glob("runtime-errors-*.jsonl"))
    assert files
    assert sum(path.stat().st_size for path in files) <= 1024
    text = "".join(path.read_text(encoding="utf-8") for path in files)
    assert "not-persisted" not in text
    assert '"level": "ERROR"' in text


def test_runtime_log_cleanup_applies_age_and_total_size_caps(tmp_path: Path):
    now = datetime(2026, 11, 10, 12, 0, tzinfo=SHANGHAI)
    old = tmp_path / "runtime-errors-2026-10-20.jsonl"
    recent = tmp_path / "runtime-errors-2026-11-09.jsonl"
    today = tmp_path / "runtime-errors-2026-11-10.jsonl"
    old.write_text("old\n", encoding="utf-8")
    recent.write_text("r" * 700, encoding="utf-8")
    today.write_text("t" * 700, encoding="utf-8")

    removed = cleanup_runtime_logs(
        tmp_path,
        now=now,
        retention_days=14,
        total_max_bytes=1000,
    )

    assert removed == 2
    assert not old.exists()
    assert not recent.exists()
    assert today.exists()
    assert sum(path.stat().st_size for path in tmp_path.iterdir()) <= 1000


def test_runtime_log_total_cap_is_enforced_during_continuous_writes(tmp_path: Path):
    handler = make_handler(
        tmp_path,
        max_bytes=4096,
        total_max_bytes=2500,
    )
    logger = make_logger(handler)

    for index in range(100):
        logger.error("failure-%s-%s", index, "x" * 100)
    handler.close()

    files = list(tmp_path.glob("runtime-errors-*.jsonl"))
    assert files
    assert sum(path.stat().st_size for path in files) <= 2500


def _add_admin(client: TestClient, username: str = "10000001") -> None:
    with client.app.state.db_session_factory() as session:
        session.add(
            User(
                username=username,
                password_hash=hash_password("Password1"),
                recovery_question="问题",
                recovery_answer_hash=hash_password("答案"),
                role="admin",
                is_active=True,
            )
        )
        session.commit()


def _add_user(client: TestClient, username: str = "10000002") -> None:
    with client.app.state.db_session_factory() as session:
        session.add(
            User(
                username=username,
                password_hash=hash_password("Password1"),
                recovery_question="问题",
                recovery_answer_hash=hash_password("答案"),
                role="user",
                is_active=True,
            )
        )
        session.commit()


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Password1"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_admin_can_list_and_download_runtime_errors(tmp_path: Path):
    runtime_dir = tmp_path / "logs" / "runtime-errors"
    runtime_dir.mkdir(parents=True)
    day = "2026-11-10"
    path = runtime_dir / f"runtime-errors-{day}.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-11-10T01:00:00+00:00",
                        "level": "ERROR",
                        "message": "one",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-11-10T02:00:00+00:00",
                        "level": "WARNING",
                        "message": "two",
                    }
                ),
                "{corrupt-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        temp_root=tmp_path / "storage",
        log_dir=tmp_path / "logs",
        runtime_log_dir=runtime_dir,
        cleanup_interval_seconds=3600,
    )

    with TestClient(create_app(settings)) as client:
        Base.metadata.create_all(client.app.state.db_engine)
        _add_admin(client)
        headers = _login(client, "10000001")

        listed = client.get(
            "/api/v1/admin/runtime-errors",
            params={"date": day, "page": 1, "page_size": 1},
            headers=headers,
        )
        assert listed.status_code == 200, listed.text
        payload = listed.json()["data"]
        assert payload["total"] == 2
        assert len(payload["items"]) == 1
        assert payload["items"][0]["message"] == "two"

        download = client.get(
            "/api/v1/admin/runtime-errors/download",
            params={"date": day},
            headers=headers,
        )
        assert download.status_code == 200
        assert download.content == path.read_bytes()
        assert f'runtime-errors-{day}.jsonl' in download.headers["content-disposition"]

        audit = client.get("/api/v1/admin/audit-logs", headers=headers).json()["data"]["items"]
        events = {item["event"] for item in audit}
        assert "admin.runtime_errors.list.success" in events
        assert "admin.runtime_errors.download.success" in events


def test_runtime_log_endpoints_are_admin_only_and_reject_invalid_dates(tmp_path: Path):
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        temp_root=tmp_path / "storage",
        log_dir=tmp_path / "logs",
        runtime_log_dir=tmp_path / "logs" / "runtime-errors",
    )

    with TestClient(create_app(settings)) as client:
        Base.metadata.create_all(client.app.state.db_engine)
        _add_admin(client)
        _add_user(client)
        headers = _login(client, "10000001")
        user_headers = _login(client, "10000002")

        no_token = client.get("/api/v1/admin/runtime-errors", params={"date": "2026-11-10"})
        assert no_token.status_code == 401
        forbidden = client.get(
            "/api/v1/admin/runtime-errors",
            params={"date": "2026-11-10"},
            headers=user_headers,
        )
        assert forbidden.status_code == 403
        invalid = client.get(
            "/api/v1/admin/runtime-errors",
            params={"date": "../../etc/passwd"},
            headers=headers,
        )
        assert invalid.status_code == 422
        missing = client.get(
            "/api/v1/admin/runtime-errors/download",
            params={"date": "2026-11-10"},
            headers=headers,
        )
        assert missing.status_code == 404
        audit = client.get("/api/v1/admin/audit-logs", headers=headers).json()["data"]["items"]
        assert "admin.runtime_errors.download.failure" in {
            item["event"] for item in audit
        }


def test_runtime_log_list_failure_is_audited(tmp_path: Path, monkeypatch):
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        temp_root=tmp_path / "storage",
        log_dir=tmp_path / "logs",
        runtime_log_dir=tmp_path / "logs" / "runtime-errors",
    )

    def fail_list(self, *_args, **_kwargs):
        raise OSError("disk read failed")

    monkeypatch.setattr("app.services.runtime_logs.RuntimeLogService.list_errors", fail_list)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        Base.metadata.create_all(client.app.state.db_engine)
        _add_admin(client)
        headers = _login(client, "10000001")
        response = client.get(
            "/api/v1/admin/runtime-errors",
            params={"date": "2026-11-10"},
            headers=headers,
        )
        assert response.status_code == 500
        audit = client.get("/api/v1/admin/audit-logs", headers=headers).json()["data"]["items"]
        assert "admin.runtime_errors.list.failure" in {
            item["event"] for item in audit
        }
