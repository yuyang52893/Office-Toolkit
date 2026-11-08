from fastapi import APIRouter, Request

from app.common.responses import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    return success_response(
        request,
        {
            "status": "ok",
            "service": request.app.state.settings.app_name,
        },
    )

