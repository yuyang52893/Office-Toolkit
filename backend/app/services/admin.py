import random
import secrets
import string
import threading

from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.db.models import User
from app.repositories import users
from app.security.passwords import hash_password
from app.services import auth as auth_service


class AdminMutationLock:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> "AdminMutationLock":
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._lock.release()


_admin_mutation_lock = AdminMutationLock()


def public_user(user: User) -> dict:
    return auth_service.public_user(user)


def generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]
    password.extend(secrets.choice(alphabet) for _ in range(9))
    random.SystemRandom().shuffle(password)
    return "".join(password)


def _target_for_update(session: Session, user_id: int) -> User:
    user = users.get_by_id_for_update(session, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "目标用户不存在", status_code=404)
    return user


def _ensure_last_admin(session: Session, user: User, *, deactivating: bool) -> None:
    if user.role != "admin" or not user.is_active or not deactivating:
        return
    if users.count_active_admins(session) <= 1:
        raise AppError(
            "LAST_ADMIN_REQUIRED",
            "系统必须保留至少一个启用的管理员",
            status_code=409,
        )


def list_users(session: Session) -> list[User]:
    return users.list_users(session)


def set_status(
    session: Session,
    user_id: int,
    is_active: bool,
    *,
    commit: bool = True,
) -> User:
    with _admin_mutation_lock:
        user = _target_for_update(session, user_id)
        deactivating = user.is_active and not is_active
        _ensure_last_admin(session, user, deactivating=deactivating)
        user.is_active = is_active
        user.session_version += 1
        if commit:
            session.commit()
        return user


def set_role(
    session: Session,
    user_id: int,
    role: str,
    *,
    commit: bool = True,
) -> User:
    with _admin_mutation_lock:
        user = _target_for_update(session, user_id)
        demoting = user.role == "admin" and role == "user"
        _ensure_last_admin(session, user, deactivating=demoting)
        user.role = role
        user.session_version += 1
        if commit:
            session.commit()
        return user


def force_logout(session: Session, user_id: int, *, commit: bool = True) -> User:
    user = _target_for_update(session, user_id)
    user.session_version += 1
    if commit:
        session.commit()
    return user


def reset_password(
    session: Session,
    user_id: int,
    *,
    commit: bool = True,
) -> tuple[str, User]:
    user = _target_for_update(session, user_id)
    temporary_password = generate_temporary_password()
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.session_version += 1
    if commit:
        session.commit()
    return temporary_password, user


def create_admin(
    session: Session,
    username: str,
    password: str,
    recovery_question: str,
    recovery_answer: str,
) -> User:
    from app.security.passwords import normalize_recovery_answer

    if users.get_by_username(session, username) is not None:
        raise AppError("USERNAME_TAKEN", "该用户名已被使用", status_code=409)

    user = User(
        username=username,
        password_hash=hash_password(password),
        recovery_question=recovery_question.strip(),
        recovery_answer_hash=hash_password(normalize_recovery_answer(recovery_answer)),
        role="admin",
        is_active=True,
        session_version=0,
        must_change_password=False,
    )
    session.add(user)
    session.commit()
    return user
