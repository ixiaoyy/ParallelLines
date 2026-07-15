from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type
from app.models.user import User


class ProductAccessGrant(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    """Persist one user's revocable access grant for an external product."""

    __tablename__ = "product_access_grants"
    __table_args__ = (
        UniqueConstraint("product", "user_id", name="uq_product_access_grants_product_user"),
        Index(
            "ix_product_access_grants_product_state",
            "product",
            "revoked_at",
            "expires_at",
        ),
        Index("ix_product_access_grants_user_product", "user_id", "product"),
    )

    product: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_level: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    authorization_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    granted_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[granted_by_id],
        lazy="selectin",
    )
    revoked_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[revoked_by_id],
        lazy="selectin",
    )
