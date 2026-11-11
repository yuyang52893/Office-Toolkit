from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.common.rate_limit import resolve_client_ip
from app.common.responses import success_response
from app.dependencies.auth import OptionalCurrentUser
from app.dependencies.history import HistoryServiceDep
from app.schemas.qrcode import MacParseRequest, QRGenerateRequest

router = APIRouter(prefix="/qrcode", tags=["qrcode"])


@router.post("/generate")
async def generate_qrcode(
    request: Request,
    payload: QRGenerateRequest,
    user: OptionalCurrentUser,
    history: HistoryServiceDep,
):
    service = request.app.state.qrcode_service
    image, normalized_mac = await run_in_threadpool(service.generate, payload)
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": 'inline; filename="qrcode.png"',
    }
    if normalized_mac:
        headers["X-MAC-Normalized"] = normalized_mac
    if user is not None:
        suffix = "mac-qrcode.png" if payload.mode == "mac" else "qrcode.png"
        metadata, _path = await run_in_threadpool(
            request.app.state.storage.create_result,
            suffix,
            lambda target: target.write_bytes(image),
        )
        capture = await run_in_threadpool(
            history.capture_result_id,
            user=user,
            tool="mac" if payload.mode == "mac" else "qrcode",
            operation="generate",
            result_id=metadata["result_id"],
            temp_storage=request.app.state.storage,
            summary={"mode": payload.mode, "size": payload.size},
            request_id=request.state.request_id,
            ip=resolve_client_ip(
                request,
                trust_proxy_headers=request.app.state.settings.trust_proxy_headers,
            ),
        )
        headers["X-History-Status"] = "saved" if capture.saved else "not_saved"
        if capture.history_id:
            headers["X-History-Id"] = capture.history_id
        if capture.notice:
            headers["X-History-Notice"] = quote(capture.notice)
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

