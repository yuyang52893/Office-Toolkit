import json

from fastapi.testclient import TestClient

from app.common.alerts import WebhookAlerter
from app.config import Settings
from app.main import create_app


def test_webhook_alert_is_disabled_without_url():
    sent: list[bytes] = []
    alerter = WebhookAlerter(
        Settings(app_env="test", alert_webhook_url=""),
        sender=lambda _url, body: sent.append(body),
    )

    assert alerter.send_server_error(request_id="req-1", path="/api/v1/fail") is False
    assert sent == []


def test_webhook_alert_respects_cooldown():
    now = 100.0
    sent: list[bytes] = []
    settings = Settings(
        app_env="test",
        alert_webhook_url="https://alerts.example/hook",
        alert_cooldown_seconds=60,
    )
    alerter = WebhookAlerter(
        settings,
        sender=lambda _url, body: sent.append(body),
        clock=lambda: now,
    )

    assert alerter.send_server_error(request_id="req-1", path="/api/v1/fail") is True
    assert alerter.send_server_error(request_id="req-2", path="/api/v1/fail") is False
    now = 161.0
    assert alerter.send_server_error(request_id="req-3", path="/api/v1/fail") is True
    assert len(sent) == 2


def test_unhandled_error_triggers_safe_webhook_payload(test_settings):
    settings = test_settings.model_copy(
        update={"alert_webhook_url": "https://alerts.example/hook"}
    )
    sent: list[bytes] = []
    app = create_app(settings)
    app.state.alerter = WebhookAlerter(
        settings,
        sender=lambda _url, body: sent.append(body),
    )

    @app.get("/api/v1/test-unhandled")
    def fail():
        raise RuntimeError("sensitive-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/test-unhandled",
            headers={"X-Request-ID": "alert-request"},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload == {
        "event": "server_error",
        "service": settings.app_name,
        "request_id": "alert-request",
        "path": "/api/v1/test-unhandled",
        "message": "服务处理失败，请稍后重试",
    }
    assert "sensitive-secret" not in sent[0].decode()
