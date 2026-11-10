from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.common.time import format_utc
from app.config import Settings
from app.db.models import User
from app.main import create_app
from app.security.passwords import hash_password


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


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Password1"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


@pytest.mark.parametrize(
    ("database_url", "jwt_secret"),
    [
        (
            "mysql+pymysql://office_tools:replace-with-a-strong-password@mysql:3306/db",
            "x" * 40,
        ),
        (
            "mysql+pymysql://office:strongpass@db:3306/db?charset=utf8mb4",
            "replace-with-at-least-32-random-characters",
        ),
    ],
)
def test_production_rejects_public_example_secrets(database_url: str, jwt_secret: str):
    with pytest.raises(ValueError, match="生产环境"):
        Settings(
            app_env="production",
            database_url=database_url,
            jwt_secret=jwt_secret,
        )


def test_cors_preflight_allows_bearer_patch(test_settings):
    settings = test_settings.model_copy(update={"cors_origins": "https://allowed.example"})
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/api/v1/admin/users/1/role",
            headers={
                "Origin": "https://allowed.example",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

    assert response.status_code == 200
    assert "PATCH" in response.headers["Access-Control-Allow-Methods"]
    assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()


def test_utc_formatting_adds_z_for_naive_and_aware_values():
    naive = datetime(2026, 11, 11, 8, 30, 0)
    aware = datetime(2026, 11, 11, 8, 30, 0, tzinfo=UTC)

    assert format_utc(naive) == "2026-11-11T08:30:00Z"
    assert format_utc(aware) == "2026-11-11T08:30:00Z"


def test_two_admins_cannot_concurrently_remove_each_other(client: TestClient):
    first_id = add_user(client, "10000001", role="admin")
    second_id = add_user(client, "10000002", role="admin")
    first_token = login(client, "10000001")
    second_token = login(client, "10000002")

    def disable(target_id: int, token: str):
        return client.patch(
            f"/api/v1/admin/users/{target_id}/status",
            json={"is_active": False},
            headers=bearer(token),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda args: disable(*args),
                [(second_id, first_token), (first_id, second_token)],
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    with client.app.state.db_session_factory() as session:
        active_admins = (
            session.query(User)
            .filter(User.role == "admin", User.is_active.is_(True))
            .count()
        )
    assert active_admins == 1
