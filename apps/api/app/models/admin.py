from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User

SiteSettingValue = dict[str, object] | list[object] | str | int | float | bool | None


class SiteSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "site_settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_site_settings_key"),
        Index("ix_site_settings_category", "category"),
    )

    key: Mapped[str] = mapped_column(String(96), nullable=False)
    value: Mapped[SiteSettingValue] = mapped_column(JSON, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    updated_by: Mapped[User | None] = relationship("User", lazy="selectin")
