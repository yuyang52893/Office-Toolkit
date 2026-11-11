import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.security.passwords import hash_password
from app.services import auth as auth_service

REGISTER = {
    "username": "00123456",
    "password": "Password1",
    "recovery_question": "我的验证问题",
    "recovery_answer": "我的答案",
}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    client = TestClient(app)
    client.__enter__()
    Base.metadata.create_all(app.state.db_engine)
    return client


def close_client(client: TestClient) -> None:
    client.__exit__(None, None, None)


def test_register_login_and_me(client):
    registered = client.post("/api/v1/auth/register", json=REGISTER)
    assert registered.status_code == 201

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER["username"], "password": REGISTER["password"]},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["data"]["access_token"]

    me = client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["data"]["username"] == REGISTER["username"]
    assert me.json()["data"]["role"] == "user"


@pytest.mark.parametrize(
    "username",
    [
        "1234567",
        "1234567890123456789",
        "12a45678",
        "-12345678",
        "1 OR 1=1",
    ],
)
def test_register_rejects_invalid_username(client, username):
    response = client.post("/api/v1/auth/register", json={**REGISTER, "username": username})
    assert response.status_code == 422


def test_register_allows_leading_zero_username(client):
    response = client.post("/api/v1/auth/register", json={**REGISTER, "username": "01234567"})
    assert response.status_code == 201


@pytest.mark.parametrize("password", ["short17", "x" * 19])
def test_register_rejects_invalid_password_length(client, password):
    response = client.post("/api/v1/auth/register", json={**REGISTER, "password": password})
    assert response.status_code == 422


def test_register_rejects_duplicate_username(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=REGISTER)
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recovery_question", "   "),
        ("recovery_answer", "   "),
    ],
)
def test_register_rejects_blank_recovery_fields(client, field, value):
    response = client.post("/api/v1/auth/register", json={**REGISTER, field: value})
    assert response.status_code == 422


def test_me_requires_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_tampered_token_is_rejected(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER["username"], "password": REGISTER["password"]},
    ).json()["data"]["access_token"]
    response = client.get("/api/v1/auth/me", headers=bearer(token[:-1] + "x"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_disabled_user_cannot_login(test_settings):
    app = create_app(test_settings)
    with TestClient(app) as client:
        Base.metadata.create_all(app.state.db_engine)
        with app.state.db_session_factory() as session:
            user = User(
                username="00123456",
                password_hash=hash_password("Password1"),
                recovery_question="问题",
                recovery_answer_hash=hash_password("答案"),
                role="user",
                is_active=True,
            )
            session.add(user)
            session.commit()
            user.is_active = False
            session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "00123456", "password": "Password1"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_recovery_question_does_not_reveal_account_existence(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    existing = client.post(
        "/api/v1/auth/recovery-question",
        json={"username": REGISTER["username"]},
    )
    missing = client.post(
        "/api/v1/auth/recovery-question",
        json={"username": "99999999"},
    )
    assert existing.status_code == 200
    assert missing.status_code == 200
    assert existing.json()["data"] == missing.json()["data"]
    assert REGISTER["recovery_question"] not in existing.text


def test_reset_requires_registered_recovery_question(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    missing_field = client.post(
        "/api/v1/auth/reset-password",
        json={
            "username": REGISTER["username"],
            "recovery_answer": REGISTER["recovery_answer"],
            "new_password": "NewPassword1",
        },
    )
    assert missing_field.status_code == 422

    wrong = client.post(
        "/api/v1/auth/reset-password",
        json={
            "username": REGISTER["username"],
            "recovery_question": "不是我的问题",
            "recovery_answer": REGISTER["recovery_answer"],
            "new_password": "NewPassword1",
        },
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_RECOVERY"


def test_reset_uses_registered_question_and_answer(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    wrong = client.post(
        "/api/v1/auth/reset-password",
        json={
            "username": REGISTER["username"],
            "recovery_question": REGISTER["recovery_question"],
            "recovery_answer": "错误答案",
            "new_password": "NewPassword1",
        },
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_RECOVERY"


def test_recovery_invalidates_old_token(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    old_token = client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER["username"], "password": REGISTER["password"]},
    ).json()["data"]["access_token"]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "username": REGISTER["username"],
            "recovery_question": REGISTER["recovery_question"],
            "recovery_answer": REGISTER["recovery_answer"],
            "new_password": "NewPassword1",
        },
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=bearer(old_token)).status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER["username"], "password": "NewPassword1"},
    )
    assert new_login.status_code == 200


def test_change_password_returns_new_token_and_revokes_old(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    old_token = client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER["username"], "password": REGISTER["password"]},
    ).json()["data"]["access_token"]

    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": REGISTER["password"], "new_password": "NewPassword1"},
        headers=bearer(old_token),
    )
    assert changed.status_code == 200
    new_token = changed.json()["data"]["access_token"]
    assert new_token != old_token
    assert client.get("/api/v1/auth/me", headers=bearer(old_token)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(new_token)).status_code == 200


def test_login_rate_limit(test_settings):
    settings = test_settings.model_copy(update={"auth_login_per_minute": 1})
    app = create_app(settings)
    with TestClient(app) as client:
        Base.metadata.create_all(app.state.db_engine)
        with app.state.db_session_factory() as session:
            session.add(
                User(
                    username="00123456",
                    password_hash=hash_password("Password1"),
                    recovery_question="问题",
                    recovery_answer_hash=hash_password("答案"),
                    role="user",
                    is_active=True,
                )
            )
            session.commit()

        first = client.post(
            "/api/v1/auth/login",
            json={"username": "00123456", "password": "Password1"},
        )
        second = client.post(
            "/api/v1/auth/login",
            json={"username": "00123456", "password": "Password1"},
        )
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "RATE_LIMITED"


def test_auth_rate_limit_uses_trusted_proxy_ip(test_settings):
    settings = test_settings.model_copy(
        update={"auth_login_per_minute": 1, "trust_proxy_headers": True}
    )
    app = create_app(settings)
    with TestClient(app) as client:
        Base.metadata.create_all(app.state.db_engine)
        with app.state.db_session_factory() as session:
            session.add(
                User(
                    username="00123456",
                    password_hash=hash_password("Password1"),
                    recovery_question="问题",
                    recovery_answer_hash=hash_password("答案"),
                    role="user",
                    is_active=True,
                )
            )
            session.commit()

        body = {"username": "00123456", "password": "Password1"}
        first_ip = client.post(
            "/api/v1/auth/login",
            json=body,
            headers={"X-Real-IP": "203.0.113.10"},
        )
        second_ip = client.post(
            "/api/v1/auth/login",
            json=body,
            headers={"X-Real-IP": "203.0.113.11"},
        )
        same_ip = client.post(
            "/api/v1/auth/login",
            json=body,
            headers={"X-Real-IP": "203.0.113.10"},
        )
        assert first_ip.status_code == 200
        assert second_ip.status_code == 200
        assert same_ip.status_code == 429


def test_concurrent_duplicate_registration_returns_409(client, monkeypatch):
    original_add = auth_service.users.add_user

    def add_then_conflict(session, user):
        result = original_add(session, user)
        if user.username == REGISTER["username"]:
            session.flush()
            raise IntegrityError("INSERT", {}, Exception("duplicate"))
        return result

    monkeypatch.setattr(auth_service.users, "add_user", add_then_conflict)
    response = client.post("/api/v1/auth/register", json=REGISTER)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_TAKEN"


def test_missing_user_login_still_verifies_password(client, monkeypatch):
    calls = []
    original_verify = auth_service.verify_password

    def counting_verify(value, password_hash):
        calls.append((value, password_hash))
        return original_verify(value, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", counting_verify)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "99999999", "password": "Password1"},
    )
    assert response.status_code == 401
    assert len(calls) == 1
