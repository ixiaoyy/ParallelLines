from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from app.db.base import as_shanghai_datetime


def serialize_api_datetime(value: datetime) -> str:
    """Format API datetimes as explicit Asia/Shanghai ISO-8601 strings.

    Key parameter `value` is a Python datetime from service or ORM layers. The return value is
    an ISO string with `+08:00`; side effect is none.
    """

    return as_shanghai_datetime(value).isoformat()


def serialize_api_datetimes(value: Any) -> Any:
    """Recursively normalize datetimes inside API response payloads.

    Key parameter `value` may be a nested dict/list/scalar produced by Pydantic serialization.
    The return value preserves the original shape while replacing datetimes with Shanghai-time
    strings; side effect is none.
    """

    if isinstance(value, datetime):
        return serialize_api_datetime(value)
    if isinstance(value, BaseModel):
        return serialize_api_datetimes(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        return {key: serialize_api_datetimes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_api_datetimes(item) for item in value]
    if isinstance(value, tuple):
        return tuple(serialize_api_datetimes(item) for item in value)
    return value


class ApiResponse[T](BaseModel):
    data: T
    meta: dict[str, object] = Field(default_factory=dict)

    @model_serializer(mode="plain")
    def serialize_with_shanghai_datetimes(
        self,
    ) -> dict[str, object]:
        """Serialize response envelopes with explicit Asia/Shanghai datetimes.

        Return value is the same response shape with datetimes normalized; side effect is none.
        """

        return {
            "data": serialize_api_datetimes(self.data),
            "meta": serialize_api_datetimes(self.meta),
        }


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, object] = {}


class ErrorResponse(BaseModel):
    error: ErrorPayload


class CursorPageMeta(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, coerce_numbers_to_str=True)
