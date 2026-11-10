import io
from urllib.parse import unquote

from conftest import authenticated_headers, history_count
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app


def test_generate_and_decode_qrcode(client: TestClient):
    text = "测试二维码 https://example.com"
    response = client.post(
        "/api/v1/qrcode/generate",
        json={"content": text, "size": 512, "mode": "text"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (512, 512)

    decoded = client.post(
        "/api/v1/qrcode/decode",
        files={"file": ("code.png", response.content, "image/png")},
    )
    assert decoded.status_code == 200, decoded.text
    payload = decoded.json()["data"]
    assert payload["count"] == 1
    assert payload["items"][0]["text"] == text


def test_mac_parse_and_generate(client: TestClient):
    parsed = client.post(
        "/api/v1/qrcode/mac/parse",
        json={"value": "aa-bb-cc-dd-ee-ff"},
    )
    assert parsed.status_code == 200, parsed.text
    mac = parsed.json()["data"]
    assert mac["canonical"] == "AA:BB:CC:DD:EE:FF"
    assert mac["plain"] == "AABBCCDDEEFF"
    assert mac["cisco"] == "AABB.CCDD.EEFF"

    generated = client.post(
        "/api/v1/qrcode/generate",
        json={"content": "aabb.ccdd.eeff", "size": 128, "mode": "mac"},
    )
    assert generated.status_code == 200
    assert generated.headers["x-mac-normalized"] == "AA:BB:CC:DD:EE:FF"
    decoded = client.post(
        "/api/v1/qrcode/decode",
        files={"file": ("mac.png", generated.content, "image/png")},
    )
    item = decoded.json()["data"]["items"][0]
    assert item["kind"] == "mac"
    assert item["mac"]["canonical"] == "AA:BB:CC:DD:EE:FF"


def test_invalid_mac_and_missing_qrcode(client: TestClient):
    invalid = client.post("/api/v1/qrcode/mac/parse", json={"value": "AA:BB"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_MAC"

    image = Image.new("RGB", (100, 100), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    response = client.post(
        "/api/v1/qrcode/decode",
        files={"file": ("blank.png", output.getvalue(), "image/png")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QR_NOT_FOUND"


def test_qrcode_validation_errors(client: TestClient):
    too_small = client.post(
        "/api/v1/qrcode/generate",
        json={"content": "hello", "size": 10},
    )
    assert too_small.status_code == 422
    assert too_small.json()["error"]["code"] == "VALIDATION_ERROR"

    empty = client.post(
        "/api/v1/qrcode/generate",
        json={"content": "   ", "size": 128, "mode": "text"},
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "EMPTY_CONTENT"


def test_qrcode_rejects_image_over_pixel_budget(test_settings):
    settings = Settings(
        app_env="test",
        temp_root=test_settings.temp_root / "qrcode-pixels",
        qr_max_pixels=1_000_000,
    )
    image = Image.new("RGB", (1001, 1000), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")

    with TestClient(create_app(settings)) as custom_client:
        response = custom_client.post(
            "/api/v1/qrcode/decode",
            files={"file": ("large.png", output.getvalue(), "image/png")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_logged_in_qrcode_result_returns_history_headers(client: TestClient):
    headers = authenticated_headers(client)
    response = client.post(
        "/api/v1/qrcode/generate",
        headers=headers,
        json={"content": "history qr", "size": 128, "mode": "text"},
    )
    assert response.status_code == 200
    assert response.headers["X-History-Status"] == "saved"
    assert response.headers["X-History-Id"]
    assert history_count(client) == 1


def test_logged_in_mac_result_returns_history_headers(client: TestClient):
    headers = authenticated_headers(client)
    response = client.post(
        "/api/v1/qrcode/generate",
        headers=headers,
        json={"content": "aa-bb-cc-dd-ee-ff", "size": 128, "mode": "mac"},
    )

    assert response.status_code == 200
    assert response.headers["X-MAC-Normalized"] == "AA:BB:CC:DD:EE:FF"
    assert response.headers["X-History-Status"] == "saved"
    assert response.headers["X-History-Id"]
    assert history_count(client) == 1


def test_qrcode_history_failure_returns_not_saved_headers(client: TestClient, monkeypatch):
    headers = authenticated_headers(client)

    def fail_history_write(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(client.app.state.history_storage, "write", fail_history_write)
    response = client.post(
        "/api/v1/qrcode/generate",
        headers=headers,
        json={"content": "history failure", "size": 128, "mode": "text"},
    )

    assert response.status_code == 200
    assert response.headers["X-History-Status"] == "not_saved"
    assert "仍可下载" in unquote(response.headers["X-History-Notice"])
    assert history_count(client) == 0


def test_anonymous_qrcode_and_logged_in_decode_do_not_save_decoded_text(client: TestClient):
    anonymous = client.post(
        "/api/v1/qrcode/generate",
        json={"content": "anonymous qr", "size": 128, "mode": "text"},
    )
    assert anonymous.status_code == 200
    assert history_count(client) == 0

    headers = authenticated_headers(client)
    generated = client.post(
        "/api/v1/qrcode/generate",
        headers=headers,
        json={"content": "decode-only", "size": 128, "mode": "text"},
    )
    decoded = client.post(
        "/api/v1/qrcode/decode",
        headers=headers,
        files={"file": ("code.png", generated.content, "image/png")},
    )
    assert decoded.status_code == 200
    assert history_count(client) == 1

