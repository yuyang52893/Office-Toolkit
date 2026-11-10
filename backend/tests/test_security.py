import time

import pytest

from app.config import Settings
from app.security.passwords import (
    hash_password,
    normalize_recovery_answer,
    verify_password,
)
from app.security.tokens import (
    InvalidTokenError,
    TokenClaims,
    create_access_token,
    decode_access_token,
)


@pytest.fixture
def security_settings() -> Settings:
    return Settings(
        app_env="test",
        jwt_secret="test-secret-that-is-at-least-32-characters",
        jwt_expire_minutes=720,
    )


def test_password_hash_is_irreversible_and_verifiable():
    value = "Strong-Pass-1"
    hashed = hash_password(value)

    assert value not in hashed
    assert verify_password(value, hashed) is True
    assert verify_password("wrong-pass", hashed) is False


def test_jwt_contains_required_claims(security_settings):
    before = int(time.time())
    token = create_access_token(1, "user", 3, security_settings)
    claims = decode_access_token(token, security_settings)

    assert isinstance(claims, TokenClaims)
    assert claims.sub == 1
    assert claims.role == "user"
    assert claims.sv == 3
    assert claims.iat >= before
    assert claims.exp > claims.iat
    assert claims.jti


def test_jwt_rejects_tampered_token(security_settings):
    token = create_access_token(1, "user", 3, security_settings)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-1] + "x", security_settings)


def test_jwt_rejects_wrong_secret(security_settings):
    token = create_access_token(1, "user", 3, security_settings)
    other = security_settings.model_copy(
        update={"jwt_secret": "another-secret-that-is-at-least-32-characters"}
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, other)


def test_jwt_rejects_expired_token(security_settings, monkeypatch):
    past = int(time.time()) - 24 * 60 * 60
    monkeypatch.setattr("app.security.tokens.time.time", lambda: past)
    token = create_access_token(1, "user", 3, security_settings)
    monkeypatch.undo()

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, security_settings)


def test_recovery_answer_is_normalized():
    assert normalize_recovery_answer("  Ａbc  ") == "abc"
    assert normalize_recovery_answer("答案  ａ") == "答案  a"
