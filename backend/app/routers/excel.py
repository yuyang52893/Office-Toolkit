from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.common.rate_limit import resolve_client_ip
from app.common.responses import success_response
from app.dependencies.auth import OptionalCurrentUser
from app.dependencies.history import HistoryServiceDep
from app.schemas.excel import MergeRequest, SplitRequest

router = APIRouter(prefix="/excel", tags=["excel"])
result_router = APIRouter(tags=["excel"])


@router.post("/inspect")
async def inspect_files(
    request: Request,
    files: Annotated[list[UploadFile], File(description="xlsx、xls 或 csv 文件")],
):
    result = await run_in_threadpool(request.app.state.excel_service.inspect, files)
    return success_response(request, result)


@router.post("/split")
async def split_excel(
    request: Request,
    payload: SplitRequest,
    user: OptionalCurrentUser,
    history: HistoryServiceDep,
):
    result = await run_in_threadpool(request.app.state.excel_service.split, payload)
    await _attach_history(
        request,
        user,
        history,
        result,
        operation=payload.mode,
        summary={
            "mode": payload.mode,
            "has_header": payload.has_header,
            "remove_empty_rows": payload.remove_empty_rows,
            "remove_duplicates": payload.remove_duplicates,
            "output_count": result["output_count"],
        },
    )
    return success_response(request, result)


@router.post("/merge")
async def merge_excel(
    request: Request,
    payload: MergeRequest,
    user: OptionalCurrentUser,
    history: HistoryServiceDep,
):
    result = await run_in_threadpool(request.app.state.excel_service.merge, payload)
    await _attach_history(
        request,
        user,
        history,
        result,
        operation="merge",
        summary={
            "mode": "merge",
            "has_header": payload.has_header,
            "remove_empty_rows": payload.remove_empty_rows,
            "remove_duplicates": payload.remove_duplicates,
            "header_strategy": payload.header_strategy,
            "row_count": result.get("row_count", 0),
        },
    )
    return success_response(request, result)


async def _attach_history(
    request: Request,
    user: Any,
    history: Any,
    result: dict[str, Any],
    *,
    operation: str,
    summary: dict[str, Any],
) -> None:
    if user is None:
        return
    capture = await run_in_threadpool(
        history.capture_result_id,
        user=user,
        tool="excel",
        operation=operation,
        result_id=result["result_id"],
        temp_storage=request.app.state.storage,
        summary=summary,
        request_id=request.state.request_id,
        ip=resolve_client_ip(
            request,
            trust_proxy_headers=request.app.state.settings.trust_proxy_headers,
        ),
    )
    result["history"] = asdict(capture)


@result_router.get("/results/{result_id}")
async def download_result(request: Request, result_id: str):
    path, metadata = request.app.state.storage.resolve_result(result_id)
    filename = metadata["filename"]
    return FileResponse(
        path,
        filename=filename,
        media_type=(
            "application/zip"
            if filename.lower().endswith(".zip")
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": _attachment_header(filename),
        },
    )


def _attachment_header(filename: str) -> str:
    from urllib.parse import quote

    safe_ascii = filename.encode("ascii", "ignore").decode() or "download"
    return f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{quote(filename)}"

