from sqlalchemy import select
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
