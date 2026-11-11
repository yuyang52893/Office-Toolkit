from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.config import Settings
from app.db.models import AuditLog, User, UserHistory
from app.repositories.history_storage import HistoryStorage
from app.services.history import HistoryResult, HistoryService

BASE_TIME = datetime(2026, 11, 10, 4, 0, 0, tzinfo=UTC)


def make_user(username: str = "00123456") -> User:
    return User(
        username=username,
        password_hash="hash",
        recovery_question="问题",
        recovery_answer_hash="answer-hash",
        role="user",
        is_active=True,
        session_version=0,
    )


def make_result(tmp_path: Path, index: int, size_bytes: int) -> HistoryResult:
    source = tmp_path / f"source-{index}.bin"
    source.write_bytes(b"x" * min(size_bytes, 1024))
    return HistoryResult(
        source_path=source,
        filename=f"result-{index}.bin",
        size_bytes=size_bytes,
        summary={"index": index},
    )


def make_service(
    session: Session,
    settings: Settings,
    storage: HistoryStorage,
) -> HistoryService:
    return HistoryService(session=session, settings=settings, storage=storage)


@pytest.fixture
def history_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        temp_root=tmp_path / "storage",
        history_root=tmp_path / "history",
        log_dir=tmp_path / "logs",
        cleanup_interval_seconds=3600,
    )


def test_eleventh_history_file_evicts_oldest(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)

    for index in range(10):
        result = make_result(tmp_path, index, 10)
        capture = service.capture_result(
            user=user,
            tool="qrcode",
            operation="generate",
            result=result,
            now=BASE_TIME + timedelta(seconds=index),
        )
        assert capture.saved is True

    eleventh = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 10, 10),
        now=BASE_TIME + timedelta(seconds=20),
    )

    assert eleventh.saved is True
    assert eleventh.evicted_count == 1
    active = (
        db_session.query(UserHistory)
        .filter(UserHistory.user_id == user.id, UserHistory.status == "active")
        .count()
    )
    assert active == history_settings.history_max_items
    assert any(
        item.expire_reason == "quota_count"
        for item in db_session.query(UserHistory).filter(UserHistory.status == "expired")
    )


def test_size_limit_evicts_oldest_active_files(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    history_settings.history_max_bytes = 250
    user = make_user()
    db_session.add(user)
    db_session.commit()
    service = make_service(db_session, history_settings, HistoryStorage(history_settings))

    for index in range(3):
        service.capture_result(
            user=user,
            tool="qrcode",
            operation="generate",
            result=make_result(tmp_path, index, 100),
            now=BASE_TIME + timedelta(seconds=index),
        )

    active = (
        db_session.query(UserHistory)
        .filter(UserHistory.user_id == user.id, UserHistory.status == "active")
        .all()
    )
    assert len(active) == 2
    assert sum(item.size_bytes for item in active) <= history_settings.history_max_bytes
    assert any(
        item.expire_reason == "quota_size"
        for item in db_session.query(UserHistory).filter(UserHistory.status == "expired")
    )


def test_oversize_result_is_not_saved(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    service = make_service(db_session, history_settings, HistoryStorage(history_settings))

    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, history_settings.history_max_bytes + 1),
        now=BASE_TIME,
    )

    assert capture.saved is False
    assert "未保存到历史" in capture.notice
    assert db_session.query(UserHistory).count() == 0


def test_expiry_marks_placeholder_and_deletes_file(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
    )
    stored_path = storage.resolve(user.id, capture.history_id)

    cleanup = service.cleanup(now=BASE_TIME + timedelta(minutes=31))
    item = db_session.get(UserHistory, capture.history_id)

    assert cleanup.expired_count == 1
    assert item.status == "expired"
    assert item.expire_reason == "timeout"
    assert item.purge_after == item.expired_at + timedelta(hours=3)
    assert stored_path.exists() is False


def test_purge_removes_placeholder_after_three_hours(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    service = make_service(db_session, history_settings, HistoryStorage(history_settings))
    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
    )
    service.cleanup(now=BASE_TIME + timedelta(minutes=31))
    service.cleanup(now=BASE_TIME + timedelta(minutes=31, hours=3, seconds=1))

    assert db_session.get(UserHistory, capture.history_id) is None


def test_expired_placeholder_does_not_consume_quota(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    first = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
    )
    service.cleanup(now=BASE_TIME + timedelta(minutes=31))

    captures = []
    for index in range(10):
        captures.append(
            service.capture_result(
                user=user,
                tool="qrcode",
                operation="generate",
                result=make_result(tmp_path, index + 10, 10),
                now=BASE_TIME + timedelta(minutes=32, seconds=index),
            )
        )

    assert all(item.saved for item in captures)
    assert first.history_id not in {
        item.id
        for item in db_session.query(UserHistory)
        .filter(UserHistory.status == "active")
        .all()
    }


def test_download_checks_owner_and_status(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    owner = make_user("00123456")
    other = make_user("00123457")
    db_session.add_all([owner, other])
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    capture = service.capture_result(
        user=owner,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
    )

    with pytest.raises(AppError) as owner_error:
        service.resolve_download(other.id, capture.history_id)
    assert owner_error.value.code == "HISTORY_NOT_FOUND"

    service.cleanup(now=BASE_TIME + timedelta(minutes=31))
    with pytest.raises(AppError) as status_error:
        service.resolve_download(owner.id, capture.history_id)
    assert status_error.value.code == "HISTORY_EXPIRED"


def test_concurrent_captures_never_exceed_item_limit(
    tmp_path: Path,
    history_settings: Settings,
):
    from app.db.base import Base
    from app.db.session import build_engine, build_session_factory

    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'concurrent.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as setup:
        user = make_user()
        setup.add(user)
        setup.commit()
        user_id = user.id

    def capture(index: int):
        session = factory()
        try:
            service = HistoryService(
                session=session,
                settings=history_settings,
                storage=HistoryStorage(history_settings),
            )
            return service.capture_result(
                user=session.get(User, user_id),
                tool="qrcode",
                operation="generate",
                result=make_result(tmp_path, index, 10),
                now=BASE_TIME + timedelta(seconds=index),
            )
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(capture, range(20)))
    finally:
        engine.dispose()

    assert all(result.saved for result in results)
    verify = factory()
    try:
        active = (
            verify.query(UserHistory)
            .filter(UserHistory.user_id == user_id, UserHistory.status == "active")
            .count()
        )
    finally:
        verify.close()
    assert active == history_settings.history_max_items


def test_purge_retries_when_physical_delete_fails(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
    monkeypatch,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
    )
    service.cleanup(now=BASE_TIME + timedelta(minutes=31))

    monkeypatch.setattr(storage, "delete_history_dir", lambda *args: False)
    service.cleanup(now=BASE_TIME + timedelta(minutes=31, hours=3, seconds=1))

    assert db_session.get(UserHistory, capture.history_id) is not None


def test_download_lazily_expires_record_before_cleanup(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
        request_id="download-expiry",
        ip="203.0.113.20",
    )
    stored_path = storage.resolve(user.id, capture.history_id)

    with pytest.raises(AppError) as error:
        service.resolve_download(
            user.id,
            capture.history_id,
            now=BASE_TIME + timedelta(minutes=30, seconds=1),
            request_id="download-expiry",
            ip="203.0.113.20",
        )

    item = db_session.get(UserHistory, capture.history_id)
    assert error.value.code == "HISTORY_EXPIRED"
    assert item.status == "expired"
    assert item.expire_reason == "timeout"
    assert stored_path.exists() is False


def test_cleanup_retries_delete_each_cycle_before_placeholder_purge(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
    monkeypatch,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
    )
    stored_path = storage.resolve(user.id, capture.history_id)
    original_delete = storage.delete_history_dir
    attempts = 0

    def flaky_delete(user_id: int, history_id: str) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return False
        return original_delete(user_id, history_id)

    monkeypatch.setattr(storage, "delete_history_dir", flaky_delete)
    service.cleanup(now=BASE_TIME + timedelta(minutes=31))
    service.cleanup(now=BASE_TIME + timedelta(minutes=32))

    assert attempts == 2
    assert stored_path.exists() is False
    assert db_session.get(UserHistory, capture.history_id) is not None
    assert "history.delete_failed" in {
        item.event for item in db_session.query(AuditLog).all()
    }


def test_history_lifecycle_writes_sanitized_audit_events(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    history_settings.history_max_items = 1
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)

    first = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
        request_id="history-save-1",
        ip="203.0.113.30",
    )
    second = service.capture_result(
        user=user,
        tool="excel",
        operation="split",
        result=make_result(tmp_path, 1, 10),
        now=BASE_TIME + timedelta(seconds=1),
        request_id="history-save-2",
        ip="203.0.113.30",
    )
    assert first.saved is True
    assert second.saved is True

    with pytest.raises(AppError):
        service.resolve_download(
            user.id,
            first.history_id or "",
            now=BASE_TIME + timedelta(minutes=31),
            request_id="history-download-expired",
            ip="203.0.113.30",
        )
    service.cleanup(now=BASE_TIME + timedelta(minutes=32))

    events = {item.event for item in db_session.query(AuditLog).all()}
    assert {
        "history.saved",
        "history.evicted",
        "history.download_failed",
        "history.timeout",
    } <= events
    serialized = str(
        [(item.event, item.details) for item in db_session.query(AuditLog).all()]
    )
    assert ("x" * 10) not in serialized


def test_download_success_and_placeholder_purge_are_audited(
    tmp_path: Path,
    db_session: Session,
    history_settings: Settings,
):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    storage = HistoryStorage(history_settings)
    service = make_service(db_session, history_settings, storage)
    capture = service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(tmp_path, 0, 10),
        now=BASE_TIME,
        request_id="history-save",
        ip="203.0.113.40",
    )
    service.resolve_download(
        user.id,
        capture.history_id or "",
        now=BASE_TIME + timedelta(seconds=1),
        request_id="history-download",
        ip="203.0.113.40",
    )
    service.cleanup(now=BASE_TIME + timedelta(minutes=31))
    service.cleanup(now=BASE_TIME + timedelta(hours=3, minutes=31, seconds=1))

    events = {item.event for item in db_session.query(AuditLog).all()}
    assert {"history.download", "history.timeout", "history.purged"} <= events
