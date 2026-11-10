import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.db.models import User
from app.security.passwords import hash_password
from app.services import audit as audit_service

REGISTER = {
    "username": "00123456",
    "password": "Password1",
    "recovery_question": "我的验证问题",
    "recovery_answer": "我的答案",
}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_user(client: TestClient, username: str, role: str = "user") -> int:
    with client.app.state.db_session_factory() as session:
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


def admin_headers(client: TestClient, username: str = "10000001") -> dict[str, str]:
    add_user(client, username, role="admin")
    return bearer(login(client, username))


def test_password_is_never_stored_in_audit_details(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    client.post(
        "/api/v1/auth/login",
        json={"username": REGISTER["username"], "password": "Super-Secret-1"},
    )

    headers = admin_headers(client)
    rows = client.get("/api/v1/admin/audit-logs", headers=headers).json()["data"]["items"]
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "Super-Secret-1" not in serialized
    assert "Password1" not in serialized


def test_admin_actions_are_audited(client):
    headers = admin_headers(client)
    target_id = add_user(client, "20000001")

    disabled = client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert disabled.status_code == 200

    reset = client.post(
        f"/api/v1/admin/users/{target_id}/reset-password",
        headers=headers,
    )
    assert reset.status_code == 200
    temporary_password = reset.json()["data"]["temporary_password"]

    logs = client.get("/api/v1/admin/audit-logs", headers=headers).json()["data"]
    events = {item["event"] for item in logs["items"]}
    assert "admin.user.status.success" in events
    assert "admin.user.reset_password.success" in events
    serialized = json.dumps(logs["items"], ensure_ascii=False)
    assert temporary_password not in serialized


def test_regular_user_cannot_view_audit_logs(client):
    add_user(client, "20000001")
    token = login(client, "20000001")
    response = client.get("/api/v1/admin/audit-logs", headers=bearer(token))
    assert response.status_code == 403


def test_audit_logs_can_be_downloaded_as_csv_and_json(client):
    headers = admin_headers(client)
    client.post(
        "/api/v1/auth/login",
        json={"username": "99999999", "password": "Wrong-Password1"},
    )

    csv = client.get(
        "/api/v1/admin/audit-logs/download",
        params={"format": "csv"},
        headers=headers,
    )
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert "auth.login.failure" in csv.text

    payload = client.get(
        "/api/v1/admin/audit-logs/download",
        params={"format": "json"},
        headers=headers,
    ).json()
    assert any(item["event"] == "auth.login.failure" for item in payload)


def test_audit_logs_purge_older_than_thirty_days(client):
    headers = admin_headers(client)
    with client.app.state.db_session_factory() as session:
        audit = audit_service.AuditService(session)
        audit.record(
            event="auth.login.failure",
            outcome="failure",
            request_id="old-request",
            actor_user_id=None,
            target_user_id=None,
            ip="127.0.0.1",
            details={"reason": "test"},
        )

    removed = client.app.state.db_session_factory()
    with removed as session:
        purged = audit_service.AuditService(session).purge_expired(
            datetime.now(UTC) + timedelta(days=31)
        )

    assert purged >= 1
    rows = client.get("/api/v1/admin/audit-logs", headers=headers).json()["data"]["items"]
    assert all(item["request_id"] != "old-request" for item in rows)
