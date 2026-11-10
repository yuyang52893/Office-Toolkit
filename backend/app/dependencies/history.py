from typing import Annotated

from fastapi import Depends, Request

from app.dependencies.auth import DbSession
from app.services.history import HistoryService


def get_history_service(request: Request, session: DbSession) -> HistoryService:
    return HistoryService(
        session=session,
        settings=request.app.state.settings,
        storage=request.app.state.history_storage,
    )


HistoryServiceDep = Annotated[HistoryService, Depends(get_history_service)]
