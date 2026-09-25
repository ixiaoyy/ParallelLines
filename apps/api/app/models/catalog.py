from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type, utcnow


class CatalogCategory(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_catalog_categories_slug"),
        Index("ix_catalog_categories_visible_order", "is_visible", "sort_order"),
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon_upload_id: Mapped[str | None] = mapped_column(
        id_column_type(), ForeignKey("uploads.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    projects: Mapped[list[CatalogProject]] = relationship(
        "CatalogProject", back_populates="category", lazy="selectin"
    )


class CatalogProject(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_projects"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_catalog_projects_slug"),
        CheckConstraint(
            "destination_kind IN ('external', 'internal')",
            name="ck_catalog_projects_destination_kind",
        ),
        Index(
            "ix_catalog_projects_category_visible_order", "category_id", "is_visible", "sort_order"
        ),
    )

    category_id: Mapped[str] = mapped_column(
        id_column_type(), ForeignKey("catalog_categories.id", ondelete="RESTRICT"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    destination_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="external")
    description: Mapped[str | None] = mapped_column(String(300))
    author_name: Mapped[str | None] = mapped_column(String(120))
    author_url: Mapped[str | None] = mapped_column(String(2048))
    icon_upload_id: Mapped[str | None] = mapped_column(
        id_column_type(), ForeignKey("uploads.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[CatalogCategory] = relationship("CatalogCategory", back_populates="projects")


class CatalogRating(IntegerPrimaryKeyMixin, Base):
    __tablename__ = "catalog_ratings"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_catalog_ratings_score"),
        UniqueConstraint("project_id", "ip_digest", name="uq_catalog_ratings_project_ip"),
        Index("ix_catalog_ratings_project", "project_id"),
    )

    project_id: Mapped[str] = mapped_column(
        id_column_type(), ForeignKey("catalog_projects.id", ondelete="CASCADE"), nullable=False
    )
    ip_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


# 游客投稿在审核前独立保存；只有审核通过后才创建公开目录项目。
class CatalogSubmission(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_catalog_submissions_status",
        ),
        UniqueConstraint("pending_url_digest", name="uq_catalog_submissions_pending_url_digest"),
        Index("ix_catalog_submissions_status_created_id", "status", "created_at", "id"),
        Index("ix_catalog_submissions_ip_created", "submitter_ip_digest", "created_at"),
    )

    category_name: Mapped[str] = mapped_column(String(120), nullable=False)
    project_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(120))
    contact: Mapped[str | None] = mapped_column(String(200))
    submitter_ip_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    pending_url_digest: Mapped[str | None] = mapped_column(CHAR(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    project_id: Mapped[str | None] = mapped_column(
        id_column_type(), ForeignKey("catalog_projects.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        id_column_type(), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
