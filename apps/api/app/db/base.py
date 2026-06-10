from datetime import UTC, datetime, timedelta, timezone
from secrets import token_hex

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class NumericStringId(TypeDecorator[str]):
    """Database BIGINT id that keeps API-facing Python values as strings."""

    impl = BigInteger
    cache_ok = True

    @property
    def python_type(self) -> type[str]:
        return str

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        return dialect.type_descriptor(BigInteger())

    def process_bind_param(self, value: object, dialect):  # type: ignore[no-untyped-def]
        if value is None or value == "":
            return None
        return int(value)

    def process_result_value(self, value: object, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return str(value)


def id_column_type() -> NumericStringId:
    return NumericStringId()


def new_random_suffix(byte_count: int = 4) -> str:
    return token_hex(byte_count)


def utcnow() -> datetime:
    return datetime.now(UTC)


SHANGHAI_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def as_shanghai_datetime(value: datetime) -> datetime:
    """Return a datetime normalized for API display in Asia/Shanghai.

    Key parameter `value` may be timezone-aware or a naive MySQL value. The return value is
    timezone-aware in Asia/Shanghai; side effect is none.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(SHANGHAI_TZ)


class Base(DeclarativeBase):
    pass


class IntegerPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(id_column_type(), primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
