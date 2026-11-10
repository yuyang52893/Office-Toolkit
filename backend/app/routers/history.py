from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.dependencies.auth import get_current_user, get_db
from app.schemas.history import HistoryItem
from app.services.history import HistoryService

router = APIRouter(prefix="/history", tags=["history"])
DbSession = Annotated[Session, Depends(get_db)]


def _service(request: Request, session: Session) -> HistoryService:
    return HistoryService(
        session=session,
        settings=request.app.state.settings,
        storage=request.app.state.history_storage,
    )


@router.get("")
def list_history(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: DbSession,
):
    service = _service(request, session)
    items = service.list_for_user(user.id)
    return {
        "items": [HistoryItem.model_validate(item).model_dump(mode="json") for item in items],
    }


@router.get("/{history_id}/download")
def download_history(
    history_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: DbSession,
):
    service = _service(request, session)
    path, item = service.resolve_download(user.id, history_id)
    return FileResponse(
        Path(path),
        filename=item.result_filename,
        media_type="application/octet-stream",
    )
