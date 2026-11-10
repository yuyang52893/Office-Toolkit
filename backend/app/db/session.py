import re
from collections.abc import Callable

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if database_url.endswith(":memory:"):
            options["poolclass"] = StaticPool
    engine = create_engine(database_url, **options)
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _register_sqlite_regexp)
    return engine


def _register_sqlite_regexp(dbapi_connection, _connection_record) -> None:
    def regexp(pattern: str, value: object) -> bool:
        if value is None:
            return False
        return re.search(pattern, str(value)) is not None

    dbapi_connection.create_function("regexp", 2, regexp)


def build_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
