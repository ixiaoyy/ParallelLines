from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.upload import Upload

UploadKind = Literal["post_attachment", "avatar"]


class UploadResponse(BaseModel):
    id: str
    url: str
    original_filename: str
    media_type: str
    byte_size: int
    kind: str
    status: str
    is_image: bool
    created_at: datetime

    @classmethod
    def from_model(cls, upload: Upload) -> "UploadResponse":
        return cls(
            id=upload.id,
            url=f"/uploads/{upload.id}/content",
            original_filename=upload.original_filename,
            media_type=upload.media_type,
            byte_size=upload.byte_size,
            kind=upload.kind,
            status=upload.status,
            is_image=upload.is_image,
            created_at=upload.created_at,
        )
