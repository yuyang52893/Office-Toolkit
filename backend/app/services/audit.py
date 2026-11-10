import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.db.models import AuditLog, User, utc_now
from app.repositories import audit as audit_repository

logger = logging.getLogger(__name__)

_SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
_RETENTION_DAYS = 30
_EXPORT_MAX_ROWS = 100_000
_ALLOWED_DETAIL_KEYS = {
    "date",
    "format",
    "from_role",
    "is_active",
    "page",
    "page_size",
    "reason",
    "to_role",
    "username",
}


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        event: str,
        outcome: str,
        request_id: str,
        actor_user_id: int | None,
        target_user_id: int | None,
        ip: str,
        details: dict | None = None,
        commit: bool = True,
    ) -> AuditLog:
        log = AuditLog(
            request_id=request_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            event=event,
            outcome=outcome,
            ip=ip[:45],
            details=self._sanitize_details(details or {}),
            created_at=utc_now(),
        )
        audit_repository.add_log(self.session, log)
        if commit:
            self.session.commit()
        return log

    def list_logs(
        self,
        *,
        day: date | None,
        event: str | None,
        outcome: str | None,
        request_id: str | None,
        username: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        if page < 1 or page_size < 1 or page_size > 100:
            raise AppError("INVALID_PAGINATION", "分页参数不正确", status_code=422)
        start, end = self._day_bounds(day)
        logs, total = audit_repository.list_logs(
            self.session,
            start=start,
            end=end,
            event=event,
            outcome=outcome,
            request_id=request_id,
            username=username,
            page=page,
            page_size=page_size,
        )
        usernames = self._usernames(logs)
        return {
            "items": [
                self._serialize(
                    log,
                    usernames.get(log.actor_user_id),
                    usernames.get(log.target_user_id),
                )
                for log in logs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def iter_logs(
        self,
        *,
        day: date | None,
        event: str | None,
        outcome: str | None,
        request_id: str | None,
        username: str | None,
    ) -> Iterator[dict]:
        page = 1
        page_size = 100
        while True:
            data = self.list_logs(
                day=day,
                event=event,
                outcome=outcome,
                request_id=request_id,
                username=username,
                page=page,
                page_size=page_size,
            )
            total = data["total"]
            yield from data["items"]
            if page * page_size >= total:
                return
            page += 1

    def ensure_export_allowed(
        self,
        *,
        day: date | None,
        event: str | None,
        outcome: str | None,
        request_id: str | None,
        username: str | None,
    ) -> None:
        start, end = self._day_bounds(day)
        _, total = audit_repository.list_logs(
            self.session,
            start=start,
            end=end,
            event=event,
            outcome=outcome,
            request_id=request_id,
            username=username,
            page=1,
            page_size=1,
        )
        if total > _EXPORT_MAX_ROWS:
            raise AppError(
                "EXPORT_TOO_LARGE",
                f"一次最多导出 {_EXPORT_MAX_ROWS} 条审计日志，请缩小筛选范围",
                status_code=413,
            )

    def purge_expired(self, now: datetime) -> int:
        now_utc = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
        cutoff = (now_utc - timedelta(days=_RETENTION_DAYS)).replace(tzinfo=None)
        removed = audit_repository.delete_older_than(self.session, cutoff)
        self.session.commit()
        return removed

    def _sanitize_details(self, details: dict) -> dict:
        sanitized = {}
        for key, value in details.items():
            if key not in _ALLOWED_DETAIL_KEYS:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[key] = value
        return sanitized

    def _day_bounds(self, day: date | None) -> tuple[datetime | None, datetime | None]:
        if day is None:
            return None, None
        start = datetime.combine(day, time.min, tzinfo=_SHANGHAI)
        end = start + timedelta(days=1)
        return (
            start.astimezone(UTC).replace(tzinfo=None),
            end.astimezone(UTC).replace(tzinfo=None),
        )

    def _usernames(self, logs: list[AuditLog]) -> dict[int, str]:
        ids = {log.actor_user_id for log in logs if log.actor_user_id is not None}
        ids.update(log.target_user_id for log in logs if log.target_user_id is not None)
        if not ids:
            return {}
        return {
            user.id: user.username
            for user in self.session.scalars(select(User).where(User.id.in_(ids)))
        }

    @staticmethod
    def _serialize(log: AuditLog, actor_username: str | None, target_username: str | None) -> dict:
        return {
            "id": log.id,
            "request_id": log.request_id,
            "event": log.event,
            "outcome": log.outcome,
            "actor_user_id": log.actor_user_id,
            "target_user_id": log.target_user_id,
            "actor_username": actor_username,
            "target_username": target_username,
            "ip": log.ip,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
