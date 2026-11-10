from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserHistory


def active_ordered(session: Session, user_id: int) -> list[UserHistory]:
    return list(
        session.scalars(
            select(UserHistory)
            .where(UserHistory.user_id == user_id, UserHistory.status == "active")
            .order_by(UserHistory.completed_at.asc(), UserHistory.id.asc())
        )
    )


def list_for_user(session: Session, user_id: int) -> list[UserHistory]:
    return list(
        session.scalars(
            select(UserHistory)
            .where(UserHistory.user_id == user_id)
            .order_by(UserHistory.completed_at.desc(), UserHistory.id.desc())
        )
    )


def get_for_user(session: Session, user_id: int, history_id: str) -> UserHistory | None:
    return session.scalar(
        select(UserHistory).where(
            UserHistory.user_id == user_id,
            UserHistory.id == history_id,
        )
    )


def active_expiring(session: Session, now: datetime) -> list[UserHistory]:
    return list(
        session.scalars(
            select(UserHistory).where(
                UserHistory.status == "active",
                UserHistory.expires_at <= now,
            )
        )
    )


def expired_placeholders(session: Session, now: datetime) -> list[UserHistory]:
    return list(
        session.scalars(
            select(UserHistory).where(
                UserHistory.status == "expired",
                UserHistory.purge_after <= now,
            )
        )
    )


def add(session: Session, item: UserHistory) -> UserHistory:
    session.add(item)
    session.flush()
    return item
