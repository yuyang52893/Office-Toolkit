import csv
import io
import json
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.common.rate_limit import resolve_client_ip
from app.common.responses import success_response
from app.db.models import User
from app.dependencies.auth import DbSession, require_admin
from app.services.audit import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/audit-logs", tags=["admin"])
Admin = Annotated[User, Depends(require_admin)]


def _client_ip(request: Request) -> str:
    return resolve_client_ip(
        request,
        trust_proxy_headers=request.app.state.settings.trust_proxy_headers,
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


@router.get("")
def list_logs(
    request: Request,
    session: DbSession,
    _admin: Admin,
    date: Annotated[date | None, Query()] = None,
    event: Annotated[str | None, Query(max_length=64)] = None,
    outcome: Annotated[str | None, Query()] = None,
    request_id: Annotated[str | None, Query(max_length=64)] = None,
    username: Annotated[str | None, Query(max_length=18)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    data = AuditService(session).list_logs(
        day=date,
        event=event,
        outcome=outcome,
        request_id=request_id,
        username=username,
        page=page,
        page_size=page_size,
    )
    _record(
        request,
        session,
        event="admin.audit_logs.list.success",
        outcome="success",
        actor_user_id=_admin.id,
        details={"page": page, "page_size": page_size, "date": str(date) if date else None},
    )
    return success_response(request, data)


@router.get("/download")
def download_logs(
    request: Request,
    session: DbSession,
    _admin: Admin,
    date: Annotated[date | None, Query()] = None,
    event: Annotated[str | None, Query(max_length=64)] = None,
    outcome: Annotated[str | None, Query()] = None,
    request_id: Annotated[str | None, Query(max_length=64)] = None,
    username: Annotated[str | None, Query(max_length=18)] = None,
    format: Annotated[str, Query()] = "json",
):
    data = AuditService(session).list_logs(
        day=date,
        event=event,
        outcome=outcome,
        request_id=request_id,
        username=username,
        page=1,
        page_size=100,
    )
    _record(
        request,
        session,
        event="admin.audit_logs.download.success",
        outcome="success",
        actor_user_id=_admin.id,
        details={"date": str(date) if date else None, "format": format},
    )
    suffix = date.isoformat() if date else "all"
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "created_at",
                "request_id",
                "event",
                "outcome",
                "actor_username",
                "target_username",
                "ip",
                "details",
            ]
        )
        for item in data["items"]:
            writer.writerow(
                [
                    item["id"],
                    item["created_at"],
                    item["request_id"],
                    item["event"],
                    item["outcome"],
                    item["actor_username"],
                    item["target_username"],
                    item["ip"],
                    json.dumps(item["details"], ensure_ascii=False),
                ]
            )
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="audit-{suffix}.csv"'},
        )

    return Response(
        content=json.dumps(data["items"], ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="audit-{suffix}.json"'},
    )
