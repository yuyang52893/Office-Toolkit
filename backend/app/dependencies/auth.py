from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.config import Settings
from app.repositories import users
from app.security.tokens import InvalidTokenError, decode_access_token


def get_db(request: Request) -> Iterator[Session]:
    factory = request.app.state.db_session_factory
    with factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


def _decode_optional(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> tuple[int, int] | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    settings: Settings = request.app.state.settings
    try:
        claims = decode_access_token(token, settings)
    except InvalidTokenError:
        return None
    return claims.sub, claims.sv


def get_optional_user(
    request: Request,
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
):
    decoded = _decode_optional(request, authorization)
    if decoded is None:
        return None
    user = users.get_by_id(session, decoded[0])
    if user is None or not user.is_active or user.session_version != decoded[1]:
        return None
    return user


def get_current_user(
    request: Request,
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
):
    if not authorization:
        raise AppError("AUTH_REQUIRED", "此功能仅登录用户可用", status_code=401)

    decoded = _decode_optional(request, authorization)
    if decoded is None:
        raise AppError("AUTH_INVALID", "登录凭证无效或已过期", status_code=401)

    user = users.get_by_id(session, decoded[0])
    if user is None or not user.is_active or user.session_version != decoded[1]:
        raise AppError("AUTH_INVALID", "登录凭证无效或已过期", status_code=401)
    return user


def require_admin(user: Annotated[object, Depends(get_current_user)]):
    if getattr(user, "role", "") != "admin":
        raise AppError("FORBIDDEN", "需要管理员权限", status_code=403)
    return user
