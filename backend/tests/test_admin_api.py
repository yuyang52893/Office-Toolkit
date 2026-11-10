from fastapi.testclient import TestClient

from app.db.models import User
from app.security.passwords import hash_password


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_user(client: TestClient, username: str, role: str = "user") -> int:
    app = client.app
    with app.state.db_session_factory() as session:
        user = User(
            username=username,
            password_hash=hash_password("Password1"),
            recovery_question="问题",
            recovery_answer_hash=hash_password("答案"),
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()
        return user.id


def login(client: TestClient, username: str, password: str = "Password1") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def test_admin_routes_require_authentication(client):
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_regular_user_cannot_access_admin_routes(client):
    add_user(client, "00123456")
    token = login(client, "00123456")
    response = client.get("/api/v1/admin/users", headers=bearer(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_users_without_secrets(client):
    admin_id = add_user(client, "10000001", role="admin")
    user_id = add_user(client, "20000001")
    token = login(client, "10000001")

    response = client.get("/api/v1/admin/users", headers=bearer(token))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert [item["id"] for item in payload["items"]] == [admin_id, user_id]
    for item in payload["items"]:
        assert "password_hash" not in item
        assert "recovery_answer_hash" not in item


def test_last_active_admin_cannot_be_disabled(client):
    admin_id = add_user(client, "10000001", role="admin")
    token = login(client, "10000001")
    response = client.patch(
        f"/api/v1/admin/users/{admin_id}/status",
        json={"is_active": False},
        headers=bearer(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_ADMIN_REQUIRED"


def test_second_admin_allows_first_to_be_disabled(client):
    first_id = add_user(client, "10000001", role="admin")
    add_user(client, "10000002", role="admin")
    token = login(client, "10000002")
    response = client.patch(
        f"/api/v1/admin/users/{first_id}/status",
        json={"is_active": False},
        headers=bearer(token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


def test_last_active_admin_cannot_be_demoted(client):
    admin_id = add_user(client, "10000001", role="admin")
    token = login(client, "10000001")
    response = client.patch(
        f"/api/v1/admin/users/{admin_id}/role",
        json={"role": "user"},
        headers=bearer(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_ADMIN_REQUIRED"


def test_force_logout_invalidates_user_token(client):
    add_user(client, "10000001", role="admin")
    add_user(client, "20000001")
    user_token = login(client, "20000001")
    admin_token = login(client, "10000001")

    response = client.post(
        "/api/v1/admin/users/2/logout",
        headers=bearer(admin_token),
    )
    assert response.status_code == 200
    me = client.get("/api/v1/auth/me", headers=bearer(user_token))
    assert me.status_code == 401


def test_admin_reset_password_returns_temporary_password_once(client):
    add_user(client, "10000001", role="admin")
    add_user(client, "20000001")
    admin_token = login(client, "10000001")

    response = client.post(
        "/api/v1/admin/users/2/reset-password",
        headers=bearer(admin_token),
    )
    assert response.status_code == 200
    temporary = response.json()["data"]["temporary_password"]
    assert 8 <= len(temporary) <= 18

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "20000001", "password": temporary},
    )
    assert login_response.status_code == 200
    assert login_response.json()["data"]["user"]["must_change_password"] is True


def test_must_change_password_blocks_admin_features_until_change(client):
    add_user(client, "10000001", role="admin")
    add_user(client, "20000001")
    admin_token = login(client, "10000001")
    temporary = client.post(
        "/api/v1/admin/users/2/reset-password",
        headers=bearer(admin_token),
    ).json()["data"]["temporary_password"]
    user_token = login(client, "20000001", temporary)

    blocked = client.get("/api/v1/admin/users", headers=bearer(user_token))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    me = client.get("/api/v1/auth/me", headers=bearer(user_token))
    assert me.status_code == 200

    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temporary, "new_password": "NewPassword1"},
        headers=bearer(user_token),
    )
    assert changed.status_code == 200
    assert (
        client.get(
            "/api/v1/auth/me",
            headers=bearer(changed.json()["data"]["access_token"]),
        ).status_code
        == 200
    )
