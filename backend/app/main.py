import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.errors import AppError
from app.common.logging import configure_logging
from app.common.responses import error_response
from app.config import Settings
from app.routers import health

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    runtime_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.repositories.temp_storage import TempStorage
        from app.services.excel_service import ExcelService
        from app.services.qrcode_service import QRCodeService

        storage = TempStorage(runtime_settings)
        app.state.settings = runtime_settings
        app.state.storage = storage
        app.state.excel_service = ExcelService(runtime_settings, storage)
        app.state.qrcode_service = QRCodeService(runtime_settings)
        storage.prepare()

        async def cleanup_loop() -> None:
            while True:
                try:
                    await asyncio.to_thread(storage.cleanup_expired)
                except Exception:
                    logger.exception("Temporary file cleanup failed")
                await asyncio.sleep(runtime_settings.cleanup_interval_seconds)

        cleanup_task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup_task

    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if runtime_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if supplied.isalnum() and len(supplied) <= 64 else uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details: list[dict[str, Any]] = []
        for item in exc.errors():
            details.append(
                {
                    "field": ".".join(str(part) for part in item.get("loc", []) if part != "body"),
                    "message": item.get("msg", "参数不正确"),
                }
            )
        return error_response(
            request,
            code="VALIDATION_ERROR",
            message="请求参数不正确",
            status_code=422,
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        messages = {
            404: ("NOT_FOUND", "请求的接口不存在"),
            405: ("METHOD_NOT_ALLOWED", "请求方法不被允许"),
        }
        code, message = messages.get(exc.status_code, ("HTTP_ERROR", "请求未完成"))
        return error_response(
            request,
            code=code,
            message=message,
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled request error", exc_info=exc)
        return error_response(
            request,
            code="INTERNAL_ERROR",
            message="服务处理失败，请稍后重试",
            status_code=500,
        )

    app.include_router(health.router, prefix=runtime_settings.api_prefix)

    try:
        from app.routers import excel, qrcode

        app.include_router(excel.router, prefix=runtime_settings.api_prefix)
        app.include_router(excel.result_router, prefix=runtime_settings.api_prefix)
        app.include_router(qrcode.router, prefix=runtime_settings.api_prefix)
    except ImportError:
        logger.warning("Tool routers are not installed yet")

    return app


app = create_app()

