from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.models import AuditLog, User


def add_log(session: Session, log: AuditLog) -> AuditLog:
    session.add(log)
    session.flush()
    return log


def list_logs(
    session: Session,
    *,
    start: datetime | None,
    end: datetime | None,
    event: str | None,
    outcome: str | None,
    request_id: str | None,
    username: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AuditLog], int]:
    actor = aliased(User)
    target = aliased(User)
    statement = (
        select(AuditLog)
        .outerjoin(actor, AuditLog.actor_user_id == actor.id)
        .outerjoin(target, AuditLog.target_user_id == target.id)
    )
    if start is not None:
        statement = statement.where(AuditLog.created_at >= start)
    if end is not None:
        statement = statement.where(AuditLog.created_at < end)
    if event:
        statement = statement.where(AuditLog.event == event)
    if outcome:
        statement = statement.where(AuditLog.outcome == outcome)
    if request_id:
        statement = statement.where(AuditLog.request_id == request_id)
    if username:
        statement = statement.where(
            or_(actor.username == username, target.username == username)
        )

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(session.scalar(count_statement) or 0)
    items = list(
        session.scalars(
            statement.order_by(AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return items, total


def delete_older_than(session: Session, cutoff: datetime) -> int:
    result = session.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    return int(result.rowcount or 0)
