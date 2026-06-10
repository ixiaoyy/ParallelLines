from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ApiResponse


class TimePayload(BaseModel):
    """Small response payload used to verify API envelope datetime serialization."""

    created_at: datetime


def test_api_response_serializes_naive_datetimes_as_shanghai_time() -> None:
    """Verify API envelopes emit explicit Asia/Shanghai offsets for database datetimes."""

    response = ApiResponse(data=TimePayload(created_at=datetime(2026, 6, 10, 2, 16, 6)))

    assert response.model_dump(mode="json")["data"]["created_at"] == (
        "2026-06-10T10:16:06+08:00"
    )
