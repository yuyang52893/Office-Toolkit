import contextlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.config import Settings
from app.db.models import User, UserHistory
from app.repositories import history as history_repository
from app.repositories.history_storage import HistoryStorage
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoryResult:
    source_path: Path
    filename: str
    size_bytes: int
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoryCapture:
    saved: bool
    history_id: str | None = None
    notice: str | None = None
    evicted_count: int = 0


@dataclass(frozen=True)
class CleanupSummary:
    expired_count: int
    purged_count: int


# ponytail: process-local per-user locks; replace with DB/queue locks for multi-instance.
_LOCKS_GUARD = threading.Lock()
_USER_LOCKS: dict[int, threading.Lock] = {}
_DELETE_FAILURE_AUDITED: set[str] = set()


def _user_lock(user_id: int) -> threading.Lock:
    with _LOCKS_GUARD:
        return _USER_LOCKS.setdefault(user_id, threading.Lock())


def _db_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class HistoryService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        storage: HistoryStorage,
        audit: AuditService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage
        self.audit = audit or AuditService(session)

    def capture_result(
        self,
        *,
        user: User,
        tool: str,
        operation: str,
        result: HistoryResult,
        now: datetime | None = None,
        request_id: str = "history-service",
        ip: str = "",
    ) -> HistoryCapture:
        current = _db_time(now or datetime.now(UTC))
        if result.size_bytes > self.settings.history_max_bytes:
            return HistoryCapture(
                saved=False,
                notice="结果过大，未保存到历史",
            )

        with _user_lock(user.id):
            self._expire_active(
                self.session,
                user_id=user.id,
                current=current,
                request_id=request_id,
                ip=ip,
            )
            active = history_repository.active_ordered(self.session, user.id)
            evicted: list[tuple[UserHistory, str]] = []

            while len(active) >= self.settings.history_max_items:
                evicted.append((active.pop(0), "quota_count"))

            active_size = sum(item.size_bytes for item in active)
            while active and active_size + result.size_bytes > self.settings.history_max_bytes:
                item = active.pop(0)
                evicted.append((item, "quota_size"))
                active_size -= item.size_bytes

            for item, reason in evicted:
                item.status = "expired"
                item.expired_at = current
                item.purge_after = current + timedelta(
                    hours=self.settings.history_placeholder_hours
                )
                item.expire_reason = reason

            history_id = uuid4().hex
            try:
                stored_name = self.storage.write(
                    user_id=user.id,
                    history_id=history_id,
                    source_path=result.source_path,
                    filename=result.filename,
                )
                record = UserHistory(
                    id=history_id,
                    user_id=user.id,
                    tool=tool,
                    operation=operation,
                    result_filename=Path(result.filename).name,
                    storage_key=stored_name,
                    size_bytes=result.size_bytes,
                    summary=result.summary,
                    status="active",
                    completed_at=current,
                    expires_at=current
                    + timedelta(minutes=self.settings.history_retention_minutes),
                )
                history_repository.add(self.session, record)
                self.audit.record(
                    event="history.saved",
                    outcome="success",
                    request_id=request_id,
                    actor_user_id=user.id,
                    target_user_id=user.id,
                    ip=ip,
                    details={
                        "history_id": history_id,
                        "tool": tool,
                        "operation": operation,
                        "size_bytes": result.size_bytes,
                    },
                    commit=False,
                )
                for item, reason in evicted:
                    self.audit.record(
                        event="history.evicted",
                        outcome="success",
                        request_id=request_id,
                        actor_user_id=user.id,
                        target_user_id=user.id,
                        ip=ip,
                        details={"history_id": item.id, "reason": reason},
                        commit=False,
                    )
                self.session.commit()
            except Exception:
                self.session.rollback()
                self.storage.delete_history_dir(user.id, history_id)
                with contextlib.suppress(Exception):
                    self.audit.record(
                        event="history.save_failed",
                        outcome="failure",
                        request_id=request_id,
                        actor_user_id=user.id,
                        target_user_id=user.id,
                        ip=ip,
                        details={"tool": tool, "operation": operation, "reason": "save_failed"},
                    )
                logger.exception("History capture failed; current download remains available")
                return HistoryCapture(saved=False, notice="历史保存失败，当前结果仍可下载")

            for item, _reason in evicted:
                self.storage.delete_history_dir(user.id, item.id)

        notice = None
        if len(evicted) == 1:
            notice = "已自动清理 1 条最早记录"
        elif len(evicted) > 1:
            notice = f"已自动清理 {len(evicted)} 条最早记录"
        return HistoryCapture(
            saved=True,
            history_id=history_id,
            notice=notice,
            evicted_count=len(evicted),
        )

    def list_for_user(
        self,
        user_id: int,
        *,
        now: datetime | None = None,
        request_id: str = "history-service",
        ip: str = "",
    ) -> list[UserHistory]:
        self._expire_active(
            self.session,
            user_id=user_id,
            current=_db_time(now or datetime.now(UTC)),
            request_id=request_id,
            ip=ip,
        )
        return history_repository.list_for_user(self.session, user_id)

    def resolve_download(
        self,
        user_id: int,
        history_id: str,
        *,
        now: datetime | None = None,
        request_id: str = "history-service",
        ip: str = "",
    ) -> tuple[Path, UserHistory]:
        current = _db_time(now or datetime.now(UTC))
        item = history_repository.get_for_user(self.session, user_id, history_id)
        if item is None:
            self._record_download_failure(user_id, history_id, "not_found", request_id, ip)
            raise AppError("HISTORY_NOT_FOUND", "历史记录不存在", status_code=404)
        if item.status == "active" and item.expires_at <= current:
            self._expire_items(
                [item],
                current,
                request_id=request_id,
                ip=ip,
            )
        if item.status != "active":
            self._record_download_failure(user_id, history_id, "expired", request_id, ip)
            raise AppError("HISTORY_EXPIRED", "该历史文件已过期", status_code=410)
        try:
            path = self.storage.resolve(user_id, history_id, item.storage_key)
        except FileNotFoundError as exc:
            self._record_download_failure(
                user_id,
                history_id,
                "file_missing",
                request_id,
                ip,
            )
            raise AppError("HISTORY_NOT_FOUND", "历史记录不存在", status_code=404) from exc
        self.audit.record(
            event="history.download",
            outcome="success",
            request_id=request_id,
            actor_user_id=user_id,
            target_user_id=user_id,
            ip=ip,
            details={"history_id": history_id, "size_bytes": item.size_bytes},
        )
        return path, item

    def cleanup(self, *, now: datetime | None = None) -> CleanupSummary:
        current = _db_time(now or datetime.now(UTC))
        expiring = history_repository.active_expiring(self.session, current)
        for item in expiring:
            item.status = "expired"
            item.expired_at = current
            item.purge_after = current + timedelta(hours=self.settings.history_placeholder_hours)
            item.expire_reason = "timeout"
            self.audit.record(
                event="history.timeout",
                outcome="success",
                request_id="history-cleanup",
                actor_user_id=None,
                target_user_id=item.user_id,
                ip="system",
                details={"history_id": item.id, "reason": "timeout"},
                commit=False,
            )
        self.session.commit()

        purged = 0
        for item in history_repository.all_expired(self.session):
            deleted = self.storage.delete_history_dir(item.user_id, item.id)
            if not deleted:
                self._record_delete_failure(item)
                continue
            with _LOCKS_GUARD:
                _DELETE_FAILURE_AUDITED.discard(item.id)
            if item.purge_after is not None and item.purge_after <= current:
                self.session.delete(item)
                self.audit.record(
                    event="history.purged",
                    outcome="success",
                    request_id="history-cleanup",
                    actor_user_id=None,
                    target_user_id=item.user_id,
                    ip="system",
                    details={"history_id": item.id, "reason": "placeholder_purged"},
                    commit=False,
                )
                purged += 1
        self.session.commit()
        return CleanupSummary(expired_count=len(expiring), purged_count=purged)

    def _expire_active(
        self,
        session: Session,
        *,
        user_id: int,
        current: datetime,
        request_id: str,
        ip: str,
    ) -> int:
        items = [
            item
            for item in history_repository.active_ordered(session, user_id)
            if item.expires_at <= current
        ]
        return self._expire_items(
            items,
            current,
            request_id=request_id,
            ip=ip,
        )

    def _expire_items(
        self,
        items: list[UserHistory],
        current: datetime,
        *,
        request_id: str,
        ip: str,
    ) -> int:
        if not items:
            return 0
        for item in items:
            item.status = "expired"
            item.expired_at = current
            item.purge_after = current + timedelta(hours=self.settings.history_placeholder_hours)
            item.expire_reason = "timeout"
            self.audit.record(
                event="history.timeout",
                outcome="success",
                request_id=request_id,
                actor_user_id=None,
                target_user_id=item.user_id,
                ip=ip,
                details={"history_id": item.id, "reason": "timeout"},
                commit=False,
            )
        self.session.commit()
        for item in items:
            if not self.storage.delete_history_dir(item.user_id, item.id):
                self._record_delete_failure(item)
        return len(items)

    def _record_download_failure(
        self,
        user_id: int,
        history_id: str,
        reason: str,
        request_id: str,
        ip: str,
    ) -> None:
        self.audit.record(
            event="history.download_failed",
            outcome="failure",
            request_id=request_id,
            actor_user_id=user_id,
            target_user_id=user_id,
            ip=ip,
            details={"history_id": history_id, "reason": reason},
        )

    def _record_delete_failure(self, item: UserHistory) -> None:
        with _LOCKS_GUARD:
            if item.id in _DELETE_FAILURE_AUDITED:
                return
            _DELETE_FAILURE_AUDITED.add(item.id)
        self.audit.record(
            event="history.delete_failed",
            outcome="failure",
            request_id="history-cleanup",
            actor_user_id=None,
            target_user_id=item.user_id,
            ip="system",
            details={"history_id": item.id, "reason": "file_delete_failed"},
        )
