from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def success_response(
    request: Request,
    data: Any = None,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": jsonable_encoder(data),
            "error": None,
            "request_id": _request_id(request),
        },
    )


def error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
    background: BackgroundTask | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": jsonable_encoder(details),
            },
            "request_id": _request_id(request),
        },
        headers=headers,
        background=background,
    )

