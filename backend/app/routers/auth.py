import logging

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.common.rate_limit import resolve_client_ip
from app.common.responses import error_response, success_response
from app.dependencies.auth import CurrentUserUnrestricted, DbSession
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RecoveryQuestionRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services import auth as auth_service
from app.services.audit import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
CurrentUser = CurrentUserUnrestricted


def _client_ip(request: Request) -> str:
    settings = request.app.state.settings
    return resolve_client_ip(
        request,
        trust_proxy_headers=settings.trust_proxy_headers,
    )


def _rate_limited(request: Request, limiter_name: str, key: str, limit: int):
    limiter = getattr(request.app.state, limiter_name)
    result = limiter.check(f"{key}:{_client_ip(request)}", limit)
    if result.allowed:
        return None
    request.state.error_code = "RATE_LIMITED"
    return error_response(
        request,
        code="RATE_LIMITED",
        message="请求过于频繁，请稍后重试",
        status_code=429,
        headers={
            "Retry-After": str(result.retry_after),
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
        },
    )


def _record(
    request: Request,
    session: Session,
    *,
    event: str,
    outcome: str,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    details: dict | None = None,
) -> None:
    try:
        AuditService(session).record(
            event=event,
            outcome=outcome,
            request_id=request.state.request_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            ip=_client_ip(request),
            details=details,
        )
    except Exception:
        logger.warning("Audit event recording failed", exc_info=True)


@router.post("/register")
def register(request: Request, payload: RegisterRequest, session: DbSession):
    try:
        user = auth_service.register(session, payload)
    except Exception:
        _record(request, session, event="auth.register.failure", outcome="failure")
        raise
    _record(
        request,
        session,
        event="auth.register.success",
        outcome="success",
        actor_user_id=user.id,
        target_user_id=user.id,
        details={"username": user.username},
    )
    return success_response(request, auth_service.public_user(user), status_code=201)


@router.post("/login")
def login(request: Request, payload: LoginRequest, session: DbSession):
    settings = request.app.state.settings
    limited = _rate_limited(
        request,
        "auth_login_limiter",
        "login",
        settings.auth_login_per_minute,
    )
    if limited is not None:
        return limited
    try:
        token, user = auth_service.login(session, payload, settings)
    except Exception:
        _record(
            request,
            session,
            event="auth.login.failure",
            outcome="failure",
            details={"reason": "invalid_credentials"},
        )
        raise
    _record(
        request,
        session,
        event="auth.login.success",
        outcome="success",
        actor_user_id=user.id,
    )
    return success_response(
        request,
        {"access_token": token, "user": auth_service.public_user(user)},
    )


@router.post("/logout")
def logout(
    request: Request,
    session: DbSession,
    user: CurrentUser,
):
    auth_service.logout(session, user)
    _record(
        request,
        session,
        event="auth.logout.success",
        outcome="success",
        actor_user_id=user.id,
    )
    return success_response(request)


@router.get("/me")
def me(request: Request, user: CurrentUser):
    return success_response(request, auth_service.public_user(user))


@router.post("/recovery-question")
def recovery_question(request: Request, payload: RecoveryQuestionRequest, session: DbSession):
    settings = request.app.state.settings
    limited = _rate_limited(
        request,
        "auth_recovery_question_limiter",
        "recovery-question",
        settings.auth_recovery_question_per_minute,
    )
    if limited is not None:
        return limited
    question = auth_service.recovery_question(session, payload)
    _record(
        request,
        session,
        event="auth.recovery_question.success",
        outcome="success",
        details={"reason": "generic_prompt"},
    )
    return success_response(request, {"recovery_question": question})


@router.post("/reset-password")
def reset_password(request: Request, payload: ResetPasswordRequest, session: DbSession):
    settings = request.app.state.settings
    limited = _rate_limited(
        request,
        "auth_recovery_password_limiter",
        "reset-password",
        settings.auth_recovery_password_per_minute,
    )
    if limited is not None:
        return limited
    try:
        auth_service.reset_password(session, payload)
    except Exception:
        _record(
            request,
            session,
            event="auth.reset_password.failure",
            outcome="failure",
            details={"reason": "invalid_recovery"},
        )
        raise
    _record(
        request,
        session,
        event="auth.reset_password.success",
        outcome="success",
    )
    return success_response(request)


@router.post("/change-password")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    session: DbSession,
    user: CurrentUser,
):
    settings = request.app.state.settings
    try:
        token = auth_service.change_password(session, user, payload, settings)
    except Exception:
        _record(
            request,
            session,
            event="auth.change_password.failure",
            outcome="failure",
            actor_user_id=user.id,
            details={"reason": "invalid_current_password"},
        )
        raise
    _record(
        request,
        session,
        event="auth.change_password.success",
        outcome="success",
        actor_user_id=user.id,
    )
    return success_response(request, {"access_token": token})
