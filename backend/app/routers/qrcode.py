from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response

from app.common.responses import success_response
from app.schemas.qrcode import MacParseRequest, QRGenerateRequest

router = APIRouter(prefix="/qrcode", tags=["qrcode"])


@router.post("/generate")
async def generate_qrcode(request: Request, payload: QRGenerateRequest):
    service = request.app.state.qrcode_service
    image, normalized_mac = service.generate(payload)
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": 'inline; filename="qrcode.png"',
    }
    if normalized_mac:
        headers["X-MAC-Normalized"] = normalized_mac
    return Response(content=image, media_type="image/png", headers=headers)


@router.post("/decode")
async def decode_qrcode(
    request: Request,
    file: Annotated[UploadFile, File(description="包含二维码的图片")],
):
    service = request.app.state.qrcode_service
    data = await file.read(service.settings.qr_max_bytes + 1)
    items = service.decode(data)
    return success_response(request, {"items": items, "count": len(items)})


@router.post("/mac/parse")
async def parse_mac(request: Request, payload: MacParseRequest):
    result = request.app.state.qrcode_service.parse_mac(payload.value)
    return success_response(request, result)

