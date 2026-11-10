from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from app.common.time import format_utc


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool: str
    operation: str
    result_filename: str
    size_bytes: int
    summary: dict[str, Any]
    status: str
    completed_at: datetime
    expires_at: datetime
    expired_at: datetime | None
    expire_reason: str | None
    purge_after: datetime | None

    @field_serializer(
        "completed_at",
        "expires_at",
        "expired_at",
        "purge_after",
        when_used="json",
    )
    def serialize_utc(self, value: datetime | None) -> str | None:
        return format_utc(value)
