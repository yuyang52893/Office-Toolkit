import io

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

