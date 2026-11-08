from typing import Literal

from pydantic import BaseModel, Field


class QRGenerateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    size: int = Field(default=512, ge=128, le=2048)
    mode: Literal["text", "mac"] = "text"


class MacParseRequest(BaseModel):
    value: str = Field(min_length=1, max_length=100)

