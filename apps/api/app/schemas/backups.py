from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.backup import BackupArtifact
from app.schemas.common import ORMModel


class BackupCreateRequest(BaseModel):
    include_uploads: bool = True


class BackupRestoreRequest(BaseModel):
    confirmation: str


class BackupArtifactResponse(ORMModel):
    id: str
    kind: str
    status: str
    filename: str
    storage_backend: str
    storage_key: str | None = None
    byte_size: int | None = None
    sha256: str | None = None
    metadata: dict[str, object]
    failure_reason: str | None = None
    created_by_id: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_model(cls, artifact: BackupArtifact) -> "BackupArtifactResponse":
        return cls(
            id=artifact.id,
            kind=artifact.kind,
            status=artifact.status,
            filename=artifact.filename,
            storage_backend=artifact.storage_backend,
            storage_key=artifact.storage_key,
            byte_size=artifact.byte_size,
            sha256=artifact.sha256,
            metadata=artifact.artifact_metadata,
            failure_reason=artifact.failure_reason,
            created_by_id=artifact.created_by_id,
            created_by_name=artifact.created_by.username if artifact.created_by else None,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
            completed_at=artifact.completed_at,
        )


class BackupRestoreResponse(BaseModel):
    backup_id: str
    status: Literal["validated"]
    restore_supported: bool
    verified_checksum: bool
    message: str
