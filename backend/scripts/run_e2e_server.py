import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.db.base import Base
from app.db.models import User
from app.db.session import build_engine, build_session_factory
from app.security.passwords import hash_password, normalize_recovery_answer


def main() -> None:
    settings = Settings()
    if settings.app_env != "test" or not settings.database_url.startswith("sqlite"):
        raise RuntimeError("E2E seed server is restricted to APP_ENV=test with SQLite")

    settings.temp_root.mkdir(parents=True, exist_ok=True)
    settings.history_root.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.runtime_log_dir.mkdir(parents=True, exist_ok=True)

    engine = build_engine(settings.database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    sessions = build_session_factory(engine)
    with sessions() as session:
        accounts = [
            ("90000001", "AdminPass1", "管理员找回问题", "管理员答案", "admin"),
            ("80000001", "UserPass1", "用户找回问题", "用户答案", "user"),
        ]
        for username, password, question, answer, role in accounts:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    recovery_question=question,
                    recovery_answer_hash=hash_password(normalize_recovery_answer(answer)),
                    role=role,
                    is_active=True,
                )
            )
        session.commit()
    engine.dispose()

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("E2E_BACKEND_PORT", "8000")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
