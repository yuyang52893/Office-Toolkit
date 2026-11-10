from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class AuditLogQuery(BaseModel):
    date: date | None = None
    event: str | None = Field(default=None, max_length=64)
    outcome: Literal["success", "failure"] | None = None
    request_id: str | None = Field(default=None, max_length=64)
    username: str | None = Field(default=None, max_length=18)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
