import time
import uuid
from dataclasses import dataclass

import jwt
from jwt import PyJWTError

from app.config import Settings


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing claims, expired, or has an invalid signature."""


@dataclass(frozen=True)
class TokenClaims:
    sub: int
    role: str
    sv: int
    iat: int
    exp: int
    jti: str


def _secret(settings: Settings) -> str:
    if len(settings.jwt_secret) < 32:
        raise ValueError("JWT_SECRET 至少需要 32 个字符")
    return settings.jwt_secret


def create_access_token(
    user_id: int,
    role: str,
    session_version: int,
    settings: Settings,
) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": role,
        "sv": session_version,
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _secret(settings), algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            _secret(settings),
            algorithms=["HS256"],
            options={
                "require": ["sub", "role", "sv", "iat", "exp", "jti"],
                "verify_exp": True,
            },
        )
        user_id = int(payload["sub"])
        role = payload["role"]
        session_version = int(payload["sv"])
        if role not in {"user", "admin"} or session_version < 0:
            raise ValueError
        return TokenClaims(
            sub=user_id,
            role=role,
            sv=session_version,
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
            jti=str(payload["jti"]),
        )
    except (PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("无效或已过期的登录凭证") from exc
