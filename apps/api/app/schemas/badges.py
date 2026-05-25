from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.badge import BadgeDefinition, UserBadge
from app.schemas.common import ORMModel


class BadgeResponse(ORMModel):
    id: str
    slug: str
    name: str
    description: str
    category: str
    icon: str
    trust_level_required: int
    active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, badge: BadgeDefinition) -> BadgeResponse:
        return cls(
            id=badge.id,
            slug=badge.slug,
            name=badge.name,
            description=badge.description,
            category=badge.category,
            icon=badge.icon,
            trust_level_required=badge.trust_level_required,
            active=badge.active,
            created_at=badge.created_at,
            updated_at=badge.updated_at,
        )


class UserBadgeResponse(ORMModel):
    id: str
    badge_id: str
    badge_slug: str
    name: str
    description: str
    category: str
    icon: str
    source_type: str
    source_id: str | None = None
    granted_by_id: str | None = None
    granted_at: datetime
    revoked_at: datetime | None = None
    revoked_by_id: str | None = None
    revoke_reason: str | None = None
    note: str | None = None

    @classmethod
    def from_model(cls, user_badge: UserBadge) -> UserBadgeResponse:
        badge = user_badge.badge
        return cls(
            id=user_badge.id,
            badge_id=user_badge.badge_id,
            badge_slug=badge.slug,
            name=badge.name,
            description=badge.description,
            category=badge.category,
            icon=badge.icon,
            source_type=user_badge.source_type,
            source_id=user_badge.source_id,
            granted_by_id=user_badge.granted_by_id,
            granted_at=user_badge.created_at,
            revoked_at=user_badge.revoked_at,
            revoked_by_id=user_badge.revoked_by_id,
            revoke_reason=user_badge.revoke_reason,
            note=user_badge.note,
        )


class BadgeGrantRequest(BaseModel):
    badge_slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    note: str | None = Field(default=None, max_length=500)


class BadgeRevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
