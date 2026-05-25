from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DraftSaveRequest(BaseModel):
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str = Field(default="", max_length=36)
    draft_type: str = Field(min_length=1, max_length=32)
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)


class DraftResponse(ORMModel):
    id: str
    user_id: str
    target_type: str
    target_id: str
    draft_type: str
    data: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
