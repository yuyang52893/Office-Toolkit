from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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
