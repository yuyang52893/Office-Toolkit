from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.common.responses import error_response, success_response
from app.dependencies.auth import DbSession, get_current_user
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RecoveryQuestionRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
CurrentUser = Annotated[object, Depends(get_current_user)]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _rate_limited(request: Request, limiter_name: str, key: str, limit: int):
    limiter = getattr(request.app.state, limiter_name)
    result = limiter.check(f"{key}:{_client_ip(request)}", limit)
    if result.allowed:
        return None
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


@router.post("/register")
def register(request: Request, payload: RegisterRequest, session: DbSession):
    user = auth_service.register(session, payload)
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
    token, user = auth_service.login(session, payload, settings)
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
    auth_service.reset_password(session, payload)
    return success_response(request)


@router.post("/change-password")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    session: DbSession,
    user: CurrentUser,
):
    settings = request.app.state.settings
    token = auth_service.change_password(session, user, payload, settings)
    return success_response(request, {"access_token": token})
