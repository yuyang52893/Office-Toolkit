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


def _user_lock(user_id: int) -> threading.Lock:
    with _LOCKS_GUARD:
        return _USER_LOCKS.setdefault(user_id, threading.Lock())


class HistoryService:
    def __init__(self, *, session: Session, settings: Settings, storage: HistoryStorage) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage

    def capture_result(
        self,
        *,
        user: User,
        tool: str,
        operation: str,
        result: HistoryResult,
        now: datetime | None = None,
    ) -> HistoryCapture:
        current = now or datetime.now(UTC)
        if result.size_bytes > self.settings.history_max_bytes:
            return HistoryCapture(
                saved=False,
                notice="结果过大，未保存到历史",
            )

        with _user_lock(user.id):
            active = history_repository.active_ordered(self.session, user.id)
            evicted: list[UserHistory] = []
            reason_count = 0
            reason_size = 0

            while len(active) >= self.settings.history_max_items:
                evicted.append(active.pop(0))
                reason_count += 1

            active_size = sum(item.size_bytes for item in active)
            while active and active_size + result.size_bytes > self.settings.history_max_bytes:
                item = active.pop(0)
                evicted.append(item)
                active_size -= item.size_bytes
                reason_size += 1

            for index, item in enumerate(evicted):
                item.status = "expired"
                item.expired_at = current
                item.purge_after = current + timedelta(
                    hours=self.settings.history_placeholder_hours
                )
                item.expire_reason = (
                    "quota_count" if index < reason_count else "quota_size"
                )

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
                self.session.commit()
            except Exception:
                self.session.rollback()
                self.storage.delete_history_dir(user.id, history_id)
                logger.exception("History capture failed; current download remains available")
                return HistoryCapture(saved=False, notice="历史保存失败，当前结果仍可下载")

            for item in evicted:
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

    def list_for_user(self, user_id: int) -> list[UserHistory]:
        return history_repository.list_for_user(self.session, user_id)

    def resolve_download(self, user_id: int, history_id: str) -> tuple[Path, UserHistory]:
        item = history_repository.get_for_user(self.session, user_id, history_id)
        if item is None:
            raise AppError("HISTORY_NOT_FOUND", "历史记录不存在", status_code=404)
        if item.status != "active":
            raise AppError("HISTORY_EXPIRED", "该历史文件已过期", status_code=410)
        try:
            path = self.storage.resolve(user_id, history_id, item.storage_key)
        except FileNotFoundError as exc:
            raise AppError("HISTORY_NOT_FOUND", "历史记录不存在", status_code=404) from exc
        return path, item

    def cleanup(self, *, now: datetime | None = None) -> CleanupSummary:
        current = now or datetime.now(UTC)
        expiring = history_repository.active_expiring(self.session, current)
        for item in expiring:
            item.status = "expired"
            item.expired_at = current
            item.purge_after = current + timedelta(hours=self.settings.history_placeholder_hours)
            item.expire_reason = "timeout"
        self.session.commit()

        for item in expiring:
            self.storage.delete_history_dir(item.user_id, item.id)

        purged = 0
        for item in history_repository.expired_placeholders(self.session, current):
            if self.storage.delete_history_dir(item.user_id, item.id):
                self.session.delete(item)
                purged += 1
        self.session.commit()
        return CleanupSummary(expired_count=len(expiring), purged_count=purged)
