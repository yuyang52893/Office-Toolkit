import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.common.rate_limit import resolve_client_ip
from app.common.responses import success_response
from app.db.models import User
from app.dependencies.auth import DbSession, require_admin
from app.schemas.admin import AdminRoleRequest, AdminStatusRequest
from app.services import admin as admin_service
from app.services.audit import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/users", tags=["admin"])
AdminUser = Annotated[User, Depends(require_admin)]


def _record(
    request: Request,
    session: Session,
    *,
    event: str,
    outcome: str,
    actor_user_id: int | None,
    target_user_id: int | None = None,
    details: dict | None = None,
) -> None:
    AuditService(session).record(
        event=event,
        outcome=outcome,
        request_id=request.state.request_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        ip=resolve_client_ip(
            request,
            trust_proxy_headers=request.app.state.settings.trust_proxy_headers,
        ),
        details=details,
    )


def _record_best_effort(
    request: Request,
    session: Session,
    *,
    event: str,
    outcome: str,
    actor_user_id: int | None,
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
            ip=resolve_client_ip(
                request,
                trust_proxy_headers=request.app.state.settings.trust_proxy_headers,
            ),
            details=details,
        )
    except Exception:
        logger.warning("Audit event recording failed", exc_info=True)


@router.get("")
def list_users(request: Request, session: DbSession, _admin: AdminUser):
    users = admin_service.list_users(session)
    _record(
        request,
        session,
        event="admin.users.list.success",
        outcome="success",
        actor_user_id=_admin.id,
    )
    return success_response(
        request,
        {"items": [admin_service.public_user(user) for user in users]},
    )


@router.patch("/{user_id}/status")
def update_status(
    request: Request,
    user_id: int,
    payload: AdminStatusRequest,
    session: DbSession,
    _admin: AdminUser,
):
    try:
        user = admin_service.set_status(
            session,
            user_id,
            payload.is_active,
            commit=False,
        )
    except Exception:
        session.rollback()
        _record_best_effort(
            request,
            session,
            event="admin.user.status.failure",
            outcome="failure",
            actor_user_id=_admin.id,
            target_user_id=user_id,
            details={"is_active": payload.is_active},
        )
        raise
    _record(
        request,
        session,
        event="admin.user.status.success",
        outcome="success",
        actor_user_id=_admin.id,
        target_user_id=user_id,
        details={"is_active": payload.is_active},
    )
    return success_response(request, admin_service.public_user(user))


@router.patch("/{user_id}/role")
def update_role(
    request: Request,
    user_id: int,
    payload: AdminRoleRequest,
    session: DbSession,
    _admin: AdminUser,
):
    try:
        user = admin_service.set_role(
            session,
            user_id,
            payload.role,
            commit=False,
        )
    except Exception:
        session.rollback()
        _record_best_effort(
            request,
            session,
            event="admin.user.role.failure",
            outcome="failure",
            actor_user_id=_admin.id,
            target_user_id=user_id,
            details={"to_role": payload.role},
        )
        raise
    _record(
        request,
        session,
        event="admin.user.role.success",
        outcome="success",
        actor_user_id=_admin.id,
        target_user_id=user_id,
        details={"to_role": payload.role},
    )
    return success_response(request, admin_service.public_user(user))


@router.post("/{user_id}/logout")
def force_logout(
    request: Request,
    user_id: int,
    session: DbSession,
    _admin: AdminUser,
):
    try:
        user = admin_service.force_logout(session, user_id, commit=False)
    except Exception:
        session.rollback()
        _record_best_effort(
            request,
            session,
            event="admin.user.force_logout.failure",
            outcome="failure",
            actor_user_id=_admin.id,
            target_user_id=user_id,
            details={"reason": "user_not_found_or_mutation_failed"},
        )
        raise
    _record(
        request,
        session,
        event="admin.user.force_logout.success",
        outcome="success",
        actor_user_id=_admin.id,
        target_user_id=user_id,
    )
    return success_response(request, admin_service.public_user(user))


@router.post("/{user_id}/reset-password")
def reset_password(
    request: Request,
    user_id: int,
    session: DbSession,
    _admin: AdminUser,
):
    try:
        temporary_password, user = admin_service.reset_password(
            session,
            user_id,
            commit=False,
        )
    except Exception:
        session.rollback()
        _record_best_effort(
            request,
            session,
            event="admin.user.reset_password.failure",
            outcome="failure",
            actor_user_id=_admin.id,
            target_user_id=user_id,
            details={"reason": "user_not_found_or_reset_failed"},
        )
        raise
    _record(
        request,
        session,
        event="admin.user.reset_password.success",
        outcome="success",
        actor_user_id=_admin.id,
        target_user_id=user_id,
    )
    return success_response(
        request,
        {
            "temporary_password": temporary_password,
            "user": admin_service.public_user(user),
        },
    )
