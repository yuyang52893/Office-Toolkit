import asyncio
import contextlib
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.alerts import WebhookAlerter
from app.common.errors import AppError
from app.common.logging import configure_logging
from app.common.rate_limit import RateLimiter, RateLimitResult, resolve_client_ip
from app.common.responses import error_response
from app.config import Settings
from app.routers import health

logger = logging.getLogger(__name__)
request_logger = logging.getLogger("app.request")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    configure_logging(runtime_settings)
    cors_origins = runtime_settings.cors_origin_list

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.db.session import build_engine, build_session_factory
        from app.repositories.temp_storage import TempStorage
        from app.services.excel_service import ExcelService
        from app.services.qrcode_service import QRCodeService

        engine = build_engine(runtime_settings.database_url)
        storage = TempStorage(runtime_settings)
        app.state.settings = runtime_settings
        app.state.db_engine = engine
        app.state.db_session_factory = build_session_factory(engine)
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
            engine.dispose()

    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if runtime_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.rate_limiter = RateLimiter(
        window_seconds=runtime_settings.rate_limit_window_seconds,
        max_entries=runtime_settings.rate_limit_max_entries,
    )
    app.state.auth_login_limiter = RateLimiter(
        window_seconds=runtime_settings.rate_limit_window_seconds,
        max_entries=runtime_settings.rate_limit_max_entries,
    )
    app.state.auth_recovery_question_limiter = RateLimiter(
        window_seconds=runtime_settings.rate_limit_window_seconds,
        max_entries=runtime_settings.rate_limit_max_entries,
    )
    app.state.auth_recovery_password_limiter = RateLimiter(
        window_seconds=runtime_settings.auth_recovery_password_window_seconds,
        max_entries=runtime_settings.rate_limit_max_entries,
    )
    app.state.alerter = WebhookAlerter(runtime_settings)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID", "Retry-After"],
            max_age=600,
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else uuid4().hex
        request.state.request_id = request_id
        limited = _check_rate_limit(request, runtime_settings)
        if limited:
            request.state.error_code = "RATE_LIMITED"
            response = error_response(
                request,
                code="RATE_LIMITED",
                message="请求过于频繁，请稍后重试",
                status_code=429,
                headers={
                    "Retry-After": str(limited.retry_after),
                    "X-RateLimit-Limit": str(limited.limit),
                    "X-RateLimit-Remaining": str(limited.remaining),
                },
            )
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        request_logger.info(
            "http_request",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": resolve_client_ip(
                    request,
                    trust_proxy_headers=runtime_settings.trust_proxy_headers,
                ),
                "error_code": getattr(request.state, "error_code", ""),
            },
        )
        return response

    def _check_rate_limit(request: Request, settings: Settings) -> RateLimitResult | None:
        path = request.url.path
        health_path = f"{settings.api_prefix}/health"
        if (
            request.method == "OPTIONS"
            or not path.startswith(settings.api_prefix)
            or path == health_path
        ):
            return None

        client_ip = resolve_client_ip(request, trust_proxy_headers=settings.trust_proxy_headers)
        general = request.app.state.rate_limiter.check(
            f"general:{client_ip}",
            settings.rate_limit_per_minute,
        )
        if not general.allowed:
            return general

        excel_paths = {
            f"{settings.api_prefix}/excel/inspect",
            f"{settings.api_prefix}/excel/split",
            f"{settings.api_prefix}/excel/merge",
        }
        if path in excel_paths:
            excel = request.app.state.rate_limiter.check(
                f"excel:{client_ip}",
                settings.excel_rate_limit_per_minute,
            )
            return None if excel.allowed else excel
        return None

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request.state.error_code = exc.code
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        request.state.error_code = "VALIDATION_ERROR"
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
        request.state.error_code = code
        return error_response(
            request,
            code=code,
            message=message,
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "")
        request.state.error_code = "INTERNAL_ERROR"
        logger.exception(
            "Unhandled request error",
            exc_info=exc,
            extra={
                "event": "application_error",
                "request_id": request_id,
                "path": request.url.path,
            },
        )
        alerter = request.app.state.alerter
        return error_response(
            request,
            code="INTERNAL_ERROR",
            message="服务处理失败，请稍后重试",
            status_code=500,
            background=(
                BackgroundTask(
                    alerter.send_server_error,
                    request_id=request_id,
                    path=request.url.path,
                )
                if alerter.enabled
                else None
            ),
        )

    app.include_router(health.router, prefix=runtime_settings.api_prefix)

    try:
        from app.routers import auth, excel, qrcode

        app.include_router(auth.router, prefix=runtime_settings.api_prefix)
        app.include_router(excel.router, prefix=runtime_settings.api_prefix)
        app.include_router(excel.result_router, prefix=runtime_settings.api_prefix)
        app.include_router(qrcode.router, prefix=runtime_settings.api_prefix)
    except ImportError:
        logger.warning("Tool routers are not installed yet")

    return app


app = create_app()

