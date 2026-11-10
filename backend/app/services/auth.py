import unicodedata

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.config import Settings
from app.db.models import User, utc_now
from app.repositories import users
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RecoveryQuestionRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.security.passwords import (
    hash_password,
    normalize_recovery_answer,
    verify_password,
)
from app.security.tokens import create_access_token

_RECOVERY_PROMPT = "请输入注册时设置的找回问题和答案"
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-missing-users")
_DUMMY_RECOVERY_HASH = hash_password("dummy-answer-for-missing-users")


def _normalize_recovery_question(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


def register(session: Session, payload: RegisterRequest) -> User:
    if users.get_by_username(session, payload.username) is not None:
        raise AppError("USERNAME_TAKEN", "该用户名已被使用", status_code=409)

    try:
        user = users.add_user(
            session,
            User(
                username=payload.username,
                password_hash=hash_password(payload.password),
                recovery_question=_normalize_recovery_question(payload.recovery_question),
                recovery_answer_hash=hash_password(
                    normalize_recovery_answer(payload.recovery_answer)
                ),
                role="user",
                is_active=True,
                session_version=0,
                must_change_password=False,
            ),
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError("USERNAME_TAKEN", "该用户名已被使用", status_code=409) from exc
    return user


def login(session: Session, payload: LoginRequest, settings: Settings) -> tuple[str, User]:
    user = users.get_by_username(session, payload.username)
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, password_hash)
    if (
        user is None
        or not user.is_active
        or not password_matches
    ):
        raise AppError("INVALID_CREDENTIALS", "用户名或密码错误", status_code=401)

    user.last_login_at = utc_now()
    session.commit()
    return create_access_token(user.id, user.role, user.session_version, settings), user


def recovery_question(session: Session, payload: RecoveryQuestionRequest) -> str:
    del payload
    return _RECOVERY_PROMPT


def reset_password(session: Session, payload: ResetPasswordRequest) -> None:
    user = users.get_by_username(session, payload.username)
    question_matches = (
        user is not None
        and _normalize_recovery_question(payload.recovery_question) == user.recovery_question
    )
    answer_hash = (
        user.recovery_answer_hash if user is not None else _DUMMY_RECOVERY_HASH
    )
    answer_matches = verify_password(
        normalize_recovery_answer(payload.recovery_answer),
        answer_hash,
    )
    if not question_matches or not answer_matches:
        raise AppError("INVALID_RECOVERY", "找回答案不正确", status_code=401)

    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    user.must_change_password = False
    session.commit()


def change_password(
    session: Session,
    user: User,
    payload: ChangePasswordRequest,
    settings: Settings,
) -> str:
    if not verify_password(payload.current_password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "当前密码不正确", status_code=401)

    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    user.must_change_password = False
    session.commit()
    return create_access_token(user.id, user.role, user.session_version, settings)


def logout(session: Session, user: User) -> None:
    user.session_version += 1
    session.commit()
