from typing import Literal

from pydantic import BaseModel


class AdminStatusRequest(BaseModel):
    is_active: bool


class AdminRoleRequest(BaseModel):
    role: Literal["user", "admin"]
