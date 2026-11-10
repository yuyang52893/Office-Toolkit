from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User


def make_user(username: str) -> User:
    now = datetime.now(UTC)
    return User(
        username=username,
        password_hash="password-hash",
        recovery_question="找回问题",
        recovery_answer_hash="answer-hash",
        created_at=now,
        updated_at=now,
    )


def test_database_defines_required_tables_and_indexes(db_session: Session):
    bind = db_session.get_bind()
    inspector = inspect(bind)

    assert {"users", "user_history", "audit_logs"} <= set(inspector.get_table_names())

    history_indexes = inspector.get_indexes("user_history")
    history_index_columns = {tuple(index["column_names"]) for index in history_indexes}
    assert ("user_id", "status", "expires_at") in history_index_columns
    assert ("purge_after",) in history_index_columns

    audit_indexes = inspector.get_indexes("audit_logs")
    audit_index_columns = {tuple(index["column_names"]) for index in audit_indexes}
    assert ("created_at",) in audit_index_columns


def test_username_is_unique(db_session: Session):
    db_session.add(make_user(username="00123456"))
    db_session.commit()

    db_session.add(make_user(username="00123456"))
    with pytest.raises(IntegrityError):
        db_session.commit()
