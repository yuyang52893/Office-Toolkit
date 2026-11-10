from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.common.responses import success_response
from app.dependencies.auth import DbSession, require_admin
from app.schemas.admin import AdminRoleRequest, AdminStatusRequest
from app.services import admin as admin_service

router = APIRouter(prefix="/admin/users", tags=["admin"])
AdminUser = Annotated[object, Depends(require_admin)]


@router.get("")
def list_users(request: Request, session: DbSession, _admin: AdminUser):
    users = admin_service.list_users(session)
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
    user = admin_service.set_status(session, user_id, payload.is_active)
    return success_response(request, admin_service.public_user(user))


@router.patch("/{user_id}/role")
def update_role(
    request: Request,
    user_id: int,
    payload: AdminRoleRequest,
    session: DbSession,
    _admin: AdminUser,
):
    user = admin_service.set_role(session, user_id, payload.role)
    return success_response(request, admin_service.public_user(user))


@router.post("/{user_id}/logout")
def force_logout(
    request: Request,
    user_id: int,
    session: DbSession,
    _admin: AdminUser,
):
    user = admin_service.force_logout(session, user_id)
    return success_response(request, admin_service.public_user(user))


@router.post("/{user_id}/reset-password")
def reset_password(
    request: Request,
    user_id: int,
    session: DbSession,
    _admin: AdminUser,
):
    temporary_password, user = admin_service.reset_password(session, user_id)
    return success_response(
        request,
        {
            "temporary_password": temporary_password,
            "user": admin_service.public_user(user),
        },
    )
