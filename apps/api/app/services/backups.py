from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.db.base import Base, utcnow
from app.models.backup import BackupArtifact
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.backups import (
    BackupArtifactResponse,
    BackupCreateRequest,
    BackupRestoreRequest,
    BackupRestoreResponse,
)
from app.services.background_jobs import BackgroundJobService

SENSITIVE_COLUMN_NAMES = {
    "hashed_password",
    "two_factor_secret",
    "refresh_token_hash",
    "token_hash",
    "code_hash",
}
SENSITIVE_KEY_FRAGMENTS = ("password", "token", "secret", "code")


@dataclass(frozen=True)
class BackupFile:
    path: Path
    filename: str
    sha256: str


@dataclass(frozen=True)
class ExportArchive:
    content: bytes
    filename: str
    sha256: str


class BackupService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def create_site_backup(
        self,
        current_user: User,
        payload: BackupCreateRequest,
    ) -> BackupArtifactResponse:
        self._require_admin(current_user)
        backup_id_suffix = utcnow().strftime("%Y%m%d%H%M%S")
        artifact = BackupArtifact(
            kind="site_backup",
            status="queued",
            filename=f"parallellines-backup-{backup_id_suffix}.zip",
            storage_backend="local",
            artifact_metadata={
                "include_uploads": payload.include_uploads,
                "backup_storage_path": self.settings.backup_storage_path,
                "requested_at": utcnow().isoformat(),
                "version": "0.1.0",
            },
            created_by_id=current_user.id,
        )
        self.session.add(artifact)
        await self.session.flush()
        self._add_audit_log(
            actor_id=current_user.id,
            action="backup_requested",
            target_type="backup_artifact",
            target_id=artifact.id,
            data={"include_uploads": payload.include_uploads},
        )
        await BackgroundJobService(self.session).enqueue(
            "create_site_backup",
            queue="maintenance",
            payload={"backup_id": artifact.id},
            idempotency_key=f"backup:{artifact.id}",
            priority=60,
            max_attempts=1,
            commit=False,
        )
        await self.session.commit()
        artifact = await self._require_artifact(artifact.id)
        return BackupArtifactResponse.from_model(artifact)

    async def run_site_backup(self, backup_id: str) -> dict[str, object]:
        artifact = await self._require_artifact(backup_id)
        if artifact.kind != "site_backup":
            raise ValidationError("backup_invalid_kind", "Artifact is not a site backup")
        if artifact.status == "succeeded" and artifact.storage_key:
            return {
                "backup_id": artifact.id,
                "filename": artifact.filename,
                "byte_size": artifact.byte_size or 0,
                "sha256": artifact.sha256 or "",
            }

        artifact.status = "running"
        artifact.failure_reason = None
        await self.session.flush()

        try:
            include_uploads = artifact.artifact_metadata.get("include_uploads") is not False
            archive_path, metadata = await self._write_site_backup_archive(
                artifact,
                include_uploads=include_uploads,
            )
            artifact.status = "succeeded"
            artifact.storage_key = archive_path.name
            artifact.byte_size = archive_path.stat().st_size
            artifact.sha256 = file_sha256(archive_path)
            artifact.completed_at = utcnow()
            artifact.artifact_metadata = {
                **artifact.artifact_metadata,
                **metadata,
                "completed_at": artifact.completed_at.isoformat(),
            }
            await self.session.flush()
            return {
                "backup_id": artifact.id,
                "filename": artifact.filename,
                "byte_size": artifact.byte_size,
                "sha256": artifact.sha256,
            }
        except Exception as exc:
            artifact.status = "failed"
            artifact.failure_reason = (str(exc) or type(exc).__name__)[:1000]
            artifact.completed_at = utcnow()
            await self.session.commit()
            raise

    async def list_backups(
        self,
        current_user: User,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[BackupArtifactResponse]:
        self._require_admin(current_user)
        statement = (
            select(BackupArtifact)
            .options(selectinload(BackupArtifact.created_by))
            .order_by(desc(BackupArtifact.created_at))
            .limit(limit)
        )
        if status:
            statement = statement.where(BackupArtifact.status == status)
        artifacts = list(await self.session.scalars(statement))
        return [BackupArtifactResponse.from_model(artifact) for artifact in artifacts]

    async def get_backup(self, backup_id: str, current_user: User) -> BackupArtifactResponse:
        self._require_admin(current_user)
        return BackupArtifactResponse.from_model(await self._require_artifact(backup_id))

    async def backup_file(self, backup_id: str, current_user: User) -> BackupFile:
        self._require_admin(current_user)
        artifact = await self._require_artifact(backup_id)
        if artifact.status != "succeeded" or not artifact.storage_key or not artifact.sha256:
            raise ValidationError("backup_not_ready", "Backup artifact is not ready")
        path = self._artifact_path(artifact)
        if not path.is_file():
            raise NotFoundError("backup_file_not_found", "Backup file not found")
        return BackupFile(path=path, filename=artifact.filename, sha256=artifact.sha256)

    async def delete_backup(self, backup_id: str, current_user: User) -> BackupArtifactResponse:
        self._require_admin(current_user)
        artifact = await self._require_artifact(backup_id)
        if artifact.storage_key:
            path = self._artifact_path(artifact)
            if path.exists():
                path.unlink()
        artifact.status = "deleted"
        artifact.failure_reason = None
        artifact.completed_at = artifact.completed_at or utcnow()
        self._add_audit_log(
            actor_id=current_user.id,
            action="backup_deleted",
            target_type="backup_artifact",
            target_id=artifact.id,
            data={"filename": artifact.filename},
        )
        await self.session.commit()
        artifact = await self._require_artifact(backup_id)
        return BackupArtifactResponse.from_model(artifact)

    async def validate_restore(
        self,
        backup_id: str,
        payload: BackupRestoreRequest,
        current_user: User,
    ) -> BackupRestoreResponse:
        self._require_admin(current_user)
        artifact = await self._require_artifact(backup_id)
        expected_confirmation = f"RESTORE {artifact.id}"
        if payload.confirmation != expected_confirmation:
            raise ValidationError(
                "invalid_restore_confirmation",
                f"Confirmation must be exactly: {expected_confirmation}",
            )
        if self.settings.environment == "production":
            raise PermissionDeniedError(
                "restore_forbidden_in_production",
                "Restore validation is disabled in production",
            )
        if artifact.status != "succeeded" or not artifact.storage_key or not artifact.sha256:
            raise ValidationError("backup_not_ready", "Backup artifact is not ready")

        path = self._artifact_path(artifact)
        if not path.is_file():
            raise NotFoundError("backup_file_not_found", "Backup file not found")
        verified = file_sha256(path) == artifact.sha256
        if not verified:
            raise ValidationError("backup_checksum_mismatch", "Backup checksum does not match")

        self._add_audit_log(
            actor_id=current_user.id,
            action="backup_restore_validated",
            target_type="backup_artifact",
            target_id=artifact.id,
            data={"filename": artifact.filename, "sha256": artifact.sha256},
        )
        await self.session.commit()
        return BackupRestoreResponse(
            backup_id=artifact.id,
            status="validated",
            restore_supported=False,
            verified_checksum=True,
            message=(
                "Archive checksum verified. Destructive restore is intentionally not automated."
            ),
        )

    async def build_user_export(self, current_user: User) -> ExportArchive:
        archive = await self._build_user_export_archive(current_user)
        return archive

    async def build_site_export(self, current_user: User) -> ExportArchive:
        self._require_admin(current_user)
        content = await self._build_site_export_bytes()
        filename = f"parallellines-site-export-{utcnow().strftime('%Y%m%d%H%M%S')}.zip"
        self._add_audit_log(
            actor_id=current_user.id,
            action="site_export_downloaded",
            target_type="site_export",
            target_id=current_user.id,
            data={"filename": filename},
        )
        await self.session.commit()
        return ExportArchive(content=content, filename=filename, sha256=bytes_sha256(content))

    async def _write_site_backup_archive(
        self,
        artifact: BackupArtifact,
        *,
        include_uploads: bool,
    ) -> tuple[Path, dict[str, object]]:
        root = self._backup_root(artifact)
        root.mkdir(parents=True, exist_ok=True)
        archive_path = (root / artifact.filename).resolve()
        self._ensure_under_root(archive_path, root)
        temporary_path = archive_path.with_name(f"{archive_path.name}.tmp")
        if temporary_path.exists():
            temporary_path.unlink()

        database_snapshot = await self._database_snapshot()
        upload_count = 0
        with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED) as archive:
            manifest = {
                "id": artifact.id,
                "kind": artifact.kind,
                "created_at": utcnow().isoformat(),
                "created_by_id": artifact.created_by_id,
                "include_uploads": include_uploads,
                "version": "0.1.0",
                "tables": {table_name: len(rows) for table_name, rows in database_snapshot.items()},
                "redaction": "password/token/secret/code fields are redacted",
            }
            archive.writestr("metadata.json", json_bytes(manifest))
            for table_name, rows in database_snapshot.items():
                archive.writestr(f"database/{table_name}.json", json_bytes(rows))
            if include_uploads:
                upload_count = self._write_upload_files(archive)
        temporary_path.replace(archive_path)
        return archive_path, {
            "table_count": len(database_snapshot),
            "upload_file_count": upload_count,
        }

    async def _build_user_export_archive(self, user: User) -> ExportArchive:
        payload = {
            "profile": public_user_export(user),
            "topics": await self._table_rows("topics", user_id=user.id),
            "posts": await self._table_rows("posts", user_id=user.id),
            "bookmarks": await self._table_rows("bookmarks", user_id=user.id),
            "reactions": await self._table_rows("reactions", user_id=user.id),
            "notifications": await self._table_rows("notifications", user_id=user.id),
        }
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(
                "metadata.json",
                json_bytes(
                    {
                        "kind": "user_export",
                        "user_id": user.id,
                        "created_at": utcnow().isoformat(),
                        "version": "0.1.0",
                        "redaction": "password/token/secret/code fields are not exported",
                    }
                ),
            )
            for name, value in payload.items():
                archive.writestr(f"{name}.json", json_bytes(value))
        content = buffer.getvalue()
        filename = (
            f"parallellines-user-export-{user.username}-{utcnow().strftime('%Y%m%d%H%M%S')}.zip"
        )
        return ExportArchive(content=content, filename=filename, sha256=bytes_sha256(content))

    async def _build_site_export_bytes(self) -> bytes:
        database_snapshot = await self._database_snapshot()
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(
                "metadata.json",
                json_bytes(
                    {
                        "kind": "site_export",
                        "created_at": utcnow().isoformat(),
                        "version": "0.1.0",
                        "tables": {
                            table_name: len(rows) for table_name, rows in database_snapshot.items()
                        },
                        "redaction": "password/token/secret/code fields are redacted",
                    }
                ),
            )
            for table_name, rows in database_snapshot.items():
                archive.writestr(f"database/{table_name}.json", json_bytes(rows))
        return buffer.getvalue()

    async def _database_snapshot(self) -> dict[str, list[dict[str, object]]]:
        snapshot: dict[str, list[dict[str, object]]] = {}
        for table in Base.metadata.sorted_tables:
            result = await self.session.execute(select(table))
            rows = [serialize_mapping(row) for row in result.mappings()]
            snapshot[table.name] = rows
        return snapshot

    async def _table_rows(self, table_name: str, **filters: str) -> list[dict[str, object]]:
        table = Base.metadata.tables[table_name]
        statement = select(table)
        for column_name, value in filters.items():
            statement = statement.where(table.c[column_name] == value)
        result = await self.session.execute(statement)
        return [serialize_mapping(row) for row in result.mappings()]

    def _write_upload_files(self, archive: ZipFile) -> int:
        upload_root = self._upload_root()
        if not upload_root.exists():
            return 0
        count = 0
        for path in upload_root.rglob("*"):
            if not path.is_file():
                continue
            resolved_path = path.resolve()
            self._ensure_under_root(resolved_path, upload_root)
            archive.write(
                resolved_path,
                f"uploads/{resolved_path.relative_to(upload_root).as_posix()}",
            )
            count += 1
        return count

    async def _require_artifact(self, backup_id: str) -> BackupArtifact:
        artifact = await self.session.scalar(
            select(BackupArtifact)
            .options(selectinload(BackupArtifact.created_by))
            .where(BackupArtifact.id == backup_id)
        )
        if artifact is None:
            raise NotFoundError("backup_not_found", "Backup artifact not found")
        return artifact

    def _artifact_path(self, artifact: BackupArtifact) -> Path:
        if not artifact.storage_key:
            raise NotFoundError("backup_file_not_found", "Backup file not found")
        root = self._backup_root(artifact)
        path = (root / artifact.storage_key).resolve()
        self._ensure_under_root(path, root)
        return path

    def _backup_root(self, artifact: BackupArtifact | None = None) -> Path:
        configured_path = self.settings.backup_storage_path
        if artifact is not None:
            artifact_path = artifact.artifact_metadata.get("backup_storage_path")
            if isinstance(artifact_path, str) and artifact_path:
                configured_path = artifact_path
        root = Path(configured_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        return root.resolve()

    def _upload_root(self) -> Path:
        root = Path(self.settings.upload_storage_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        return root.resolve()

    def _ensure_under_root(self, path: Path, root: Path) -> None:
        if path != root and root not in path.parents:
            raise NotFoundError("backup_file_not_found", "Backup file not found")

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _add_audit_log(
        self,
        *,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                board_id=None,
                data=data,
                created_at=utcnow(),
            )
        )


def serialize_mapping(row: object) -> dict[str, object]:
    mapping = dict(row)
    return {str(key): sanitize_export_value(str(key), value) for key, value in mapping.items()}


def sanitize_export_value(key: str, value: object) -> object:
    lowered = key.lower()
    if key in SENSITIVE_COLUMN_NAMES or any(
        fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS
    ):
        return "***redacted***"
    return to_jsonable(value)


def to_jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): sanitize_export_value(str(key), child_value)
            for key, child_value in value.items()
        }
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def public_user_export(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "level": user.level,
        "status": user.status,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        "two_factor_enabled": user.two_factor_enabled,
    }


def json_bytes(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
