from pydantic import BaseModel, ConfigDict, Field


class ApiResponse[T](BaseModel):
    data: T
    meta: dict[str, object] = Field(default_factory=dict)


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
