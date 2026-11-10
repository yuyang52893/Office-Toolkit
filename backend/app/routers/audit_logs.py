import csv
import io
import json
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.common.rate_limit import resolve_client_ip
from app.common.responses import success_response
from app.db.models import User
from app.dependencies.auth import DbSession, require_admin
from app.services.audit import AuditService
from app.services.runtime_logs import RuntimeLogService

router = APIRouter(prefix="/admin/audit-logs", tags=["admin"])
runtime_router = APIRouter(prefix="/admin/runtime-errors", tags=["admin"])
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
    AuditService(session).record(
        event=event,
        outcome=outcome,
        request_id=request.state.request_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        ip=_client_ip(request),
        details=details,
    )


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
    format: Annotated[Literal["json", "csv"], Query()] = "json",
):
    audit = AuditService(session)
    audit.ensure_export_allowed(
        day=date,
        event=event,
        outcome=outcome,
        request_id=request_id,
        username=username,
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

    def serialize_csv_row(item: dict) -> list[str]:
        return [
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

    if format == "csv":
        def csv_rows():
            yield [
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
            for item in audit.iter_logs(
                day=date,
                event=event,
                outcome=outcome,
                request_id=request_id,
                username=username,
            ):
                yield serialize_csv_row(item)

        def csv_stream():
            yield "\ufeff"
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            for row in csv_rows():
                buffer.seek(0)
                buffer.truncate(0)
                writer.writerow(row)
                yield buffer.getvalue()

        return StreamingResponse(
            csv_stream(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="audit-{suffix}.csv"'},
        )

    def json_stream():
        yield "["
        first = True
        for item in audit.iter_logs(
            day=date,
            event=event,
            outcome=outcome,
            request_id=request_id,
            username=username,
        ):
            if not first:
                yield ","
            yield json.dumps(item, ensure_ascii=False)
            first = False
        yield "]"

    return StreamingResponse(
        json_stream(),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="audit-{suffix}.json"'},
    )


@runtime_router.get("")
def list_runtime_errors(
    request: Request,
    session: DbSession,
    _admin: Admin,
    date: Annotated[date, Query()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    data = RuntimeLogService(request.app.state.settings).list_errors(
        date,
        page=page,
        page_size=page_size,
    )
    _record(
        request,
        session,
        event="admin.runtime_errors.list.success",
        outcome="success",
        actor_user_id=_admin.id,
        details={"date": date.isoformat(), "page": page, "page_size": page_size},
    )
    return success_response(request, data)


@runtime_router.get("/download")
def download_runtime_errors(
    request: Request,
    session: DbSession,
    _admin: Admin,
    date: Annotated[date, Query()],
):
    path = RuntimeLogService(request.app.state.settings).resolve_download(date)
    _record(
        request,
        session,
        event="admin.runtime_errors.download.success",
        outcome="success",
        actor_user_id=_admin.id,
        details={"date": date.isoformat()},
    )
    return FileResponse(
        path,
        media_type="application/x-ndjson",
        filename=path.name,
    )
