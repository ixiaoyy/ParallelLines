from datetime import datetime
from typing import Literal

from pydantic import BaseModel

FableSpaceAccessLevel = Literal["access", "creator", "operator", "admin"]


class FableSpaceAccessGrantUpdateRequest(BaseModel):
    access_level: FableSpaceAccessLevel
    expires_at: datetime | None = None


class FableSpaceAdminAccessRow(BaseModel):
    user_id: str
    username: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    forum_role: str
    account_status: str
    access_allowed: bool
    access_level: FableSpaceAccessLevel | None = None
    capabilities: list[str]
    authorization_version: int
    granted_by_id: str | None = None
    granted_by_name: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FableSpaceAccessStatusResponse(BaseModel):
    access_allowed: bool
    capabilities: list[str]
    access_level: FableSpaceAccessLevel | None = None
    expires_at: datetime | None = None
    authorization_version: int
