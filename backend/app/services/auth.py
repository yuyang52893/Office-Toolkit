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

    user = users.add_user(
        session,
        User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            recovery_question=payload.recovery_question.strip(),
            recovery_answer_hash=hash_password(normalize_recovery_answer(payload.recovery_answer)),
            role="user",
            is_active=True,
            session_version=0,
            must_change_password=False,
        ),
    )
    session.commit()
    return user


def login(session: Session, payload: LoginRequest, settings: Settings) -> tuple[str, User]:
    user = users.get_by_username(session, payload.username)
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise AppError("INVALID_CREDENTIALS", "用户名或密码错误", status_code=401)

    user.last_login_at = utc_now()
    session.commit()
    return create_access_token(user.id, user.role, user.session_version, settings), user


def recovery_question(session: Session, payload: RecoveryQuestionRequest) -> str:
    user = users.get_by_username(session, payload.username)
    if user is None:
        return "请回答注册时设置的找回问题"
    return user.recovery_question


def reset_password(session: Session, payload: ResetPasswordRequest) -> None:
    user = users.get_by_username(session, payload.username)
    answer_matches = user is not None and verify_password(
        normalize_recovery_answer(payload.recovery_answer),
        user.recovery_answer_hash,
    )
    if not answer_matches:
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
