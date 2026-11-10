from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import User


def get_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username))


def get_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def add_user(session: Session, user: User) -> User:
    session.add(user)
    session.flush()
    return user


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.id)))


def get_by_id_for_update(session: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id).with_for_update()
    return session.scalar(statement)


def count_active_admins(session: Session) -> int:
    statement = (
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.is_active.is_(True))
    )
    return int(session.scalar(statement) or 0)
