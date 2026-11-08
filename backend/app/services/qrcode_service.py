import io
import re

import qrcode
import zxingcpp
from PIL import Image, UnidentifiedImageError
from qrcode.constants import ERROR_CORRECT_M

from app.common.errors import AppError
from app.config import Settings
from app.schemas.qrcode import QRGenerateRequest

_HEX_MAC = re.compile(r"^[0-9A-Fa-f]{12}$")
_MAC_SEPARATORS = re.compile(r"[:.\-\s]")
_SUPPORTED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}


class QRCodeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: QRGenerateRequest) -> tuple[bytes, str]:
        content = request.content
        normalized_mac = ""
        if request.mode == "mac":
            mac = self.parse_mac(content)
            normalized_mac = mac["canonical"]
            content = normalized_mac
        elif not content.strip():
            raise AppError("EMPTY_CONTENT", "请输入二维码内容")

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=1,
            border=4,
        )
        try:
            qr.add_data(content)
            qr.make(fit=True)
            image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        except (ValueError, qrcode.exceptions.DataOverflowError) as exc:
            raise AppError(
                "QR_CONTENT_TOO_LONG",
                "内容过长，无法生成二维码，请缩短后重试",
            ) from exc

        image = image.resize(
            (request.size, request.size),
            Image.Resampling.NEAREST,
        )
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue(), normalized_mac

    def decode(self, data: bytes) -> list[dict[str, object]]:
        if not data:
            raise AppError("EMPTY_FILE", "请选择二维码图片")
        if len(data) > self.settings.qr_max_bytes:
            raise AppError(
                "IMAGE_TOO_LARGE",
                f"图片不能超过 {self.settings.qr_max_mb}MB",
                status_code=413,
            )
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in _SUPPORTED_IMAGE_FORMATS:
                    raise AppError("UNSUPPORTED_IMAGE", "仅支持 PNG、JPEG 和 WebP 图片")
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > self.settings.qr_max_pixels:
                    raise AppError("IMAGE_TOO_LARGE", "图片像素尺寸超过安全限制")
                image.load()
                barcodes = zxingcpp.read_barcodes(image)
        except AppError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise AppError("INVALID_IMAGE", "图片损坏或格式无法识别") from exc

        items: list[dict[str, object]] = []
        seen: set[str] = set()
        for barcode in barcodes:
            if getattr(barcode, "format", None) != zxingcpp.BarcodeFormat.QRCode:
                continue
            text = str(getattr(barcode, "text", "") or "")
            if not text or text in seen:
                continue
            seen.add(text)
            item: dict[str, object] = {"text": text, "kind": "text"}
            try:
                mac = self.parse_mac(text)
                item["kind"] = "mac"
                item["mac"] = mac
            except AppError:
                pass
            items.append(item)
        if not items:
            raise AppError("QR_NOT_FOUND", "未在图片中识别到二维码", status_code=422)
        return items

    @staticmethod
    def parse_mac(value: str) -> dict[str, object]:
        compact = _MAC_SEPARATORS.sub("", value.strip())
        if not _HEX_MAC.fullmatch(compact):
            raise AppError(
                "INVALID_MAC",
                "MAC 地址应为 12 位十六进制字符，例如 AA:BB:CC:DD:EE:FF",
            )
        compact = compact.upper()
        octets = [compact[index : index + 2] for index in range(0, 12, 2)]
        first_octet = int(octets[0], 16)
        return {
            "canonical": ":".join(octets),
            "hyphenated": "-".join(octets),
            "plain": compact,
            "cisco": ".".join("".join(octets[index : index + 2]) for index in range(0, 6, 2)),
            "multicast": bool(first_octet & 0x01),
            "locally_administered": bool(first_octet & 0x02),
        }

