from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError, ValidationError
from app.db.base import new_random_suffix, utcnow
from app.models.forum import Board, BoardMember, Post, Topic
from app.models.upload import Upload
from app.models.user import User
from app.services.admin import SiteSettingService
from app.services.spam import SpamPreventionService

UPLOAD_REFERENCE_PATTERN = re.compile(
    r"(?:/api/v1)?/uploads/("
    r"[1-9][0-9]*|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r")/content"
)
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
IMAGE_MEDIA_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
THUMBNAIL_DIRECTORY = "_thumbnails"
THUMBNAIL_MAX_SIZE = (360, 520)
THUMBNAIL_MEDIA_TYPE = "image/webp"
ALLOWED_BINARY_SIGNATURES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".gif": ("image/gif", (b"GIF87a", b"GIF89a")),
    ".webp": ("image/webp", (b"RIFF",)),
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".zip": ("application/zip", (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")),
}
ALLOWED_TEXT_EXTENSIONS = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".log": "text/plain",
}
DISALLOWED_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".html",
    ".htm",
    ".js",
    ".mjs",
    ".php",
    ".ps1",
    ".sh",
    ".svg",
}


@dataclass(frozen=True)
class UploadContent:
    upload: Upload
    path: Path


@dataclass(frozen=True)
class UploadThumbnail:
    upload: Upload
    path: Path
    media_type: str = THUMBNAIL_MEDIA_TYPE


class UploadService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def create_post_upload(
        self,
        file: UploadFile,
        current_user: User,
        request: Request | None = None,
    ) -> Upload:
        return await self._create_upload(
            file, current_user, kind="post_attachment", request=request
        )

    async def update_avatar(
        self,
        file: UploadFile,
        current_user: User,
        request: Request | None = None,
    ) -> Upload:
        upload = await self._create_upload(file, current_user, kind="avatar", request=request)
        upload.status = "avatar"
        current_user.avatar_url = f"/uploads/{upload.id}/content"
        await self.session.commit()
        return upload

    async def attach_uploads_to_post(
        self,
        raw_md: str,
        *,
        post: Post,
        topic: Topic,
        board: Board,
        current_user: User,
    ) -> None:
        upload_ids = extract_upload_ids(raw_md)
        if len(upload_ids) > self.settings.upload_max_files_per_post:
            raise ValidationError(
                "upload_count_exceeded",
                "Too many uploads referenced by this post",
                {"max_files": self.settings.upload_max_files_per_post},
            )
        if not upload_ids:
            return

        result = await self.session.scalars(select(Upload).where(Upload.id.in_(upload_ids)))
        uploads_by_id = {upload.id: upload for upload in result}
        missing_ids = [upload_id for upload_id in upload_ids if upload_id not in uploads_by_id]
        if missing_ids:
            raise NotFoundError("upload_not_found", "Upload not found")

        for upload in uploads_by_id.values():
            if upload.kind != "post_attachment":
                raise ValidationError("upload_invalid_kind", "Upload cannot be attached to a post")
            if upload.deleted_at is not None or upload.status == "deleted":
                raise NotFoundError("upload_not_found", "Upload not found")
            if upload.user_id != current_user.id and upload.post_id != post.id:
                raise PermissionDeniedError("upload_forbidden", "Upload permission required")
            if upload.post_id and upload.post_id != post.id:
                raise ValidationError(
                    "upload_already_attached",
                    "Upload is attached to another post",
                )

            upload.board_id = board.id
            upload.topic_id = topic.id
            upload.post_id = post.id
            upload.status = "attached"
            upload.expires_at = None

    async def get_upload_content(
        self,
        upload_id: str,
        current_user: User | None,
    ) -> UploadContent:
        upload = await self.session.scalar(
            select(Upload)
            .options(
                selectinload(Upload.post).selectinload(Post.topic).selectinload(Topic.board),
                selectinload(Upload.board),
            )
            .where(Upload.id == upload_id)
        )
        if not upload or upload.deleted_at is not None or upload.status == "deleted":
            raise NotFoundError("upload_not_found", "Upload not found")

        if upload.kind != "avatar":
            await self._require_attachment_access(upload, current_user)

        path = self.local_path_for(upload)
        if not path.is_file():
            raise NotFoundError("upload_not_found", "Upload not found")
        return UploadContent(upload=upload, path=path)

    async def get_upload_thumbnail(
        self,
        upload_id: str,
        current_user: User | None,
    ) -> UploadThumbnail:
        """Return or lazily generate a small WebP thumbnail for an uploaded image.

        Key parameters mirror `get_upload_content`, including ACL checks. Return value
        is a local thumbnail path plus upload metadata. Side effect: writes a cached
        thumbnail file under the upload root when missing or stale.
        """
        content = await self.get_upload_content(upload_id, current_user)
        if not content.upload.is_image:
            raise NotFoundError("upload_not_found", "Upload not found")

        thumbnail_path = self.thumbnail_path_for(content.upload)
        if self._thumbnail_needs_refresh(thumbnail_path, content.path):
            self._generate_thumbnail(content.path, thumbnail_path)
        return UploadThumbnail(upload=content.upload, path=thumbnail_path)

    async def cleanup_expired_temporary_uploads(self) -> int:
        now = utcnow()
        result = await self.session.scalars(
            select(Upload).where(
                Upload.status == "temporary",
                Upload.expires_at.is_not(None),
                Upload.expires_at < now,
            )
        )
        uploads = list(result)
        for upload in uploads:
            upload.status = "deleted"
            upload.deleted_at = now
            path = self.local_path_for(upload)
            if path.exists():
                path.unlink()
            thumbnail_path = self.thumbnail_path_for(upload)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
        await self.session.commit()
        return len(uploads)

    def local_path_for(self, upload: Upload) -> Path:
        """Return the absolute local path for an upload storage key.

        Key parameter: `upload` supplies the stored relative key. Return value is an
        absolute path inside the configured upload root. Side effect: validates path
        containment and raises `upload_not_found` on traversal.
        """
        root = self._storage_root()
        path = (root / upload.storage_key).resolve()
        if root not in path.parents:
            raise NotFoundError("upload_not_found", "Upload not found")
        return path

    def thumbnail_path_for(self, upload: Upload) -> Path:
        """Return the absolute cached thumbnail path for an upload.

        Key parameter: `upload` supplies the stored relative key. Return value is a
        WebP sidecar path under `_thumbnails/`. Side effect: validates containment
        before callers create or read the file.
        """
        root = self._storage_root()
        path = (root / THUMBNAIL_DIRECTORY / f"{upload.storage_key}.webp").resolve()
        if root not in path.parents:
            raise NotFoundError("upload_not_found", "Upload not found")
        return path

    async def _create_upload(
        self,
        file: UploadFile,
        current_user: User,
        *,
        kind: str,
        request: Request | None = None,
    ) -> Upload:
        await SpamPreventionService(self.session, self.settings).enforce_upload(
            request,
            current_user=current_user,
        )
        self._require_local_backend()
        max_bytes = (
            self.settings.upload_max_avatar_bytes
            if kind == "avatar"
            else self.settings.upload_max_bytes
        )
        max_bytes = await SiteSettingService(self.session, self.settings).upload_limit_bytes(
            kind=kind,
            fallback=max_bytes,
        )
        content = await self._read_limited(file, max_bytes)
        filename = sanitize_filename(file.filename or "upload")
        media_type = sniff_media_type(
            content,
            filename=filename,
            declared_media_type=file.content_type,
        )
        if kind == "avatar" and media_type not in IMAGE_MEDIA_TYPES:
            raise ValidationError("avatar_must_be_image", "Avatar upload must be an image")
        sha256 = hashlib.sha256(content).hexdigest()
        extension = extension_for_media_type(media_type, filename)
        upload = Upload(
            user_id=current_user.id,
            original_filename=filename,
            storage_backend=self.settings.upload_storage_backend,
            storage_key=storage_key_for(f"pending-{new_random_suffix(8)}", extension),
            media_type=media_type,
            byte_size=len(content),
            sha256=sha256,
            kind=kind,
            status="temporary",
            is_image=media_type in IMAGE_MEDIA_TYPES,
            expires_at=(
                utcnow() + timedelta(hours=self.settings.upload_temporary_ttl_hours)
                if kind == "post_attachment"
                else None
            ),
        )
        self.session.add(upload)
        await self.session.flush()
        upload.storage_key = storage_key_for(upload.id, extension)
        path = self.local_path_for(upload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        await self.session.flush()
        return upload

    async def _read_limited(self, file: UploadFile, max_bytes: int) -> bytes:
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValidationError(
                "upload_too_large",
                "Upload file is too large",
                {"max_bytes": max_bytes},
            )
        if not content:
            raise ValidationError("upload_empty", "Upload file is empty")
        return content

    async def _require_attachment_access(
        self,
        upload: Upload,
        current_user: User | None,
    ) -> None:
        if upload.status == "temporary" or upload.post_id is None:
            if current_user is None or current_user.id != upload.user_id:
                raise NotFoundError("upload_not_found", "Upload not found")
            return

        post = upload.post
        if not post or post.deleted_at is not None:
            raise NotFoundError("upload_not_found", "Upload not found")
        topic = post.topic
        if not topic or topic.deleted_at is not None:
            raise NotFoundError("upload_not_found", "Upload not found")
        if not await self._can_access_board(topic.board, current_user):
            raise NotFoundError("upload_not_found", "Upload not found")

    def _storage_root(self) -> Path:
        self._require_local_backend()
        root = Path(self.settings.upload_storage_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        return root.resolve()

    def _thumbnail_needs_refresh(self, thumbnail_path: Path, source_path: Path) -> bool:
        """Check whether a thumbnail is missing or older than its source image.

        Key parameters are the thumbnail and source paths. Return value is true when
        regeneration is required. Side effect: none.
        """
        return (
            not thumbnail_path.is_file()
            or thumbnail_path.stat().st_mtime < source_path.stat().st_mtime
        )

    def _generate_thumbnail(self, source_path: Path, thumbnail_path: Path) -> None:
        """Generate a constrained WebP thumbnail for a stored image.

        Key parameters are the source and destination paths. Return value is none.
        Side effect: creates parent directories and writes/replaces the thumbnail file.
        """
        try:
            with Image.open(source_path) as source_image:
                image = ImageOps.exif_transpose(source_image)
                image.thumbnail(THUMBNAIL_MAX_SIZE, Image.Resampling.LANCZOS)
                thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                image = self._to_thumbnail_rgb(image)
                image.save(thumbnail_path, "WEBP", quality=82, method=4)
        except (OSError, UnidentifiedImageError) as exc:
            raise NotFoundError("upload_not_found", "Upload not found") from exc

    def _to_thumbnail_rgb(self, image: Image.Image) -> Image.Image:
        """Convert an image to a WebP-safe RGB thumbnail canvas.

        Key parameter: `image` is a PIL image already resized for thumbnail use.
        Return value: RGB image with transparent pixels composited on white.
        Side effect: none.
        """
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            return background.convert("RGB")
        return image.convert("RGB")

    async def _can_access_board(self, board: Board, current_user: User | None) -> bool:
        if board.visibility == "public":
            return True
        if current_user is None:
            return False
        if board.owner_id == current_user.id:
            return True
        member = await self.session.scalar(
            select(BoardMember.id).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id == current_user.id,
            )
        )
        return member is not None

    def _require_local_backend(self) -> None:
        if self.settings.upload_storage_backend != "local":
            raise AppError(
                "upload_storage_backend_unavailable",
                "Upload storage backend is not available",
                status_code=503,
            )


def extract_upload_ids(raw_md: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in UPLOAD_REFERENCE_PATTERN.finditer(raw_md):
        upload_id = match.group(1).lower()
        if upload_id not in seen:
            seen.add(upload_id)
            ordered.append(upload_id)
    return ordered


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name.strip().strip(".")
    sanitized = SAFE_FILENAME_PATTERN.sub("-", name)[:255].strip("-._")
    return sanitized or "upload"


def storage_key_for(upload_id: str, extension: str, now: datetime | None = None) -> str:
    safe_extension = extension if extension.startswith(".") else f".{extension}"
    stored_at = now or utcnow()
    return f"{stored_at:%Y/%m}/{upload_id}{safe_extension}"


def sniff_media_type(
    content: bytes,
    *,
    filename: str,
    declared_media_type: str | None,
) -> str:
    extension = Path(filename).suffix.lower()
    if extension in DISALLOWED_EXTENSIONS:
        raise ValidationError("upload_type_not_allowed", "This file type is not allowed")

    media_type = sniff_by_extension(content, extension)
    if media_type is None:
        raise ValidationError("upload_type_not_allowed", "This file type is not allowed")

    declared = (declared_media_type or "").split(";", 1)[0].strip().lower()
    if (
        declared
        and declared != "application/octet-stream"
        and not declared_matches(declared, media_type)
    ):
        raise ValidationError(
            "upload_mime_mismatch",
            "Upload file content does not match its declared MIME type",
            {"declared": declared, "detected": media_type},
        )
    return media_type


def sniff_by_extension(content: bytes, extension: str) -> str | None:
    if extension in ALLOWED_BINARY_SIGNATURES:
        media_type, signatures = ALLOWED_BINARY_SIGNATURES[extension]
        if extension == ".webp":
            if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
                return media_type
            return None
        if any(content.startswith(signature) for signature in signatures):
            return media_type
        return None

    if extension in ALLOWED_TEXT_EXTENSIONS:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return ALLOWED_TEXT_EXTENSIONS[extension]

    return None


def declared_matches(declared: str, detected: str) -> bool:
    if declared == detected:
        return True
    if declared == "image/jpg" and detected == "image/jpeg":
        return True
    if declared == "text/plain" and detected in {"text/markdown", "text/csv"}:
        return True
    if declared == "application/x-zip-compressed" and detected == "application/zip":
        return True
    return False


def extension_for_media_type(media_type: str, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension and extension not in DISALLOWED_EXTENSIONS:
        return extension
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "text/markdown": ".md",
        "text/csv": ".csv",
        "text/plain": ".txt",
    }
    return mapping.get(media_type, ".bin")


def content_disposition(filename: str, *, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    return f"{disposition}; filename*=UTF-8''{quote(filename)}"
