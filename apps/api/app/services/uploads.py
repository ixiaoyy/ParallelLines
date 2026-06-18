from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import or_, select
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
CDN_OBJECT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~!$&'()*+,;=:@/%-]*$")
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
    content: bytes


@dataclass(frozen=True)
class UploadThumbnail:
    upload: Upload
    content: bytes
    media_type: str = THUMBNAIL_MEDIA_TYPE


@dataclass(frozen=True)
class UploadReferences:
    """Upload references extracted from one Markdown body.

    Key fields are API upload IDs and CDN storage keys. Return value is immutable
    data for attachment binding. Side effect: none.
    """

    ids: list[str]
    storage_keys: list[str]

    def count(self) -> int:
        """Return the number of distinct upload references found in Markdown.

        Key parameters: none. Return value is the unique ID/key count. Side
        effect: none.
        """
        return len(self.ids) + len(self.storage_keys)


class LocalUploadStorage:
    """Read and write upload objects on the configured local filesystem."""

    def __init__(self, settings: Settings) -> None:
        """Create a local storage adapter for one settings object.

        Key parameter is the loaded runtime settings. Return value is none. Side
        effect: stores settings for later path resolution.
        """
        self.settings = settings

    def write(self, key: str, content: bytes, media_type: str) -> None:
        """Persist one upload object under `key`.

        Key parameters are the relative object key, raw bytes, and media type for
        interface parity with S3. Return value is none. Side effect: creates parent
        directories and writes/replaces the local file.
        """
        path = self.path_for(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as exc:
            raise storage_unavailable_error() from exc

    def read(self, key: str) -> bytes:
        """Load one upload object from local storage.

        Key parameter is the relative storage key. Return value is the file bytes.
        Side effect: validates path containment and raises `upload_not_found` when
        the object is missing.
        """
        path = self.path_for(key)
        if not path.is_file():
            raise NotFoundError("upload_not_found", "Upload not found")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise storage_unavailable_error() from exc

    def delete(self, key: str) -> None:
        """Delete one local upload object when it exists.

        Key parameter is the relative storage key. Return value is none. Side effect:
        removes the file after validating it remains inside the upload root.
        """
        path = self.path_for(key)
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            raise storage_unavailable_error() from exc

    def path_for(self, key: str) -> Path:
        """Resolve a relative object key to an absolute local path.

        Key parameter is a database `storage_key`. Return value is an absolute path
        inside the configured upload root. Side effect: raises `upload_not_found`
        when the key would escape the storage root.
        """
        root = self.root()
        path = (root / key).resolve()
        if root not in path.parents:
            raise NotFoundError("upload_not_found", "Upload not found")
        return path

    def root(self) -> Path:
        """Return the absolute local upload root.

        Key parameters: none. Return value is the resolved configured upload
        directory. Side effect: none.
        """
        root = Path(self.settings.upload_storage_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        return root.resolve()


class S3UploadStorage:
    """Minimal S3-compatible upload storage client for Cloudflare R2."""

    def __init__(self, settings: Settings) -> None:
        """Create an S3-compatible storage adapter for one settings object.

        Key parameter is the loaded runtime settings. Return value is none. Side
        effect: validates required R2/S3 configuration without making a network call.
        """
        self.settings = settings
        self.bucket = self._require_config("UPLOAD_S3_BUCKET", settings.upload_s3_bucket)
        self.region = settings.upload_s3_region or "auto"
        self.endpoint_url = self._require_config(
            "UPLOAD_S3_ENDPOINT_URL",
            settings.upload_s3_endpoint_url,
        ).rstrip("/")
        self.access_key = self._require_config(
            "UPLOAD_S3_ACCESS_KEY_ID",
            settings.upload_s3_access_key_id,
        )
        self.secret_key = self._require_config(
            "UPLOAD_S3_SECRET_ACCESS_KEY",
            settings.upload_s3_secret_access_key,
        )
        self.timeout = settings.upload_s3_request_timeout_seconds
        self.endpoint = urlsplit(self.endpoint_url)
        if (
            not self.endpoint.scheme
            or not self.endpoint.netloc
            or self.endpoint.query
            or self.endpoint.fragment
        ):
            raise AppError(
                "upload_storage_backend_unavailable",
                "Upload storage backend is not configured",
                status_code=503,
            )

    def write(self, key: str, content: bytes, media_type: str) -> None:
        """Persist one object through an S3-compatible PUT request.

        Key parameters are the storage key, raw bytes, and media type. Return value
        is none. Side effect: sends a signed PUT request to the configured bucket.
        """
        self._request("PUT", key, body=content, content_type=media_type)

    def read(self, key: str) -> bytes:
        """Load one object through an S3-compatible GET request.

        Key parameter is the storage key. Return value is the object bytes. Side
        effect: sends a signed GET request and maps 404 to `upload_not_found`.
        """
        return self._request("GET", key)

    def delete(self, key: str) -> None:
        """Delete one object through an S3-compatible DELETE request.

        Key parameter is the storage key. Return value is none. Side effect: sends a
        signed DELETE request; missing objects are treated as already deleted.
        """
        self._request("DELETE", key)

    def _request(
        self,
        method: str,
        key: str,
        *,
        body: bytes = b"",
        content_type: str | None = None,
    ) -> bytes:
        """Send one signed S3 request and return the response body.

        Key parameters are the HTTP method, object key, optional request body, and
        optional content type. Return value is response bytes. Side effect: performs
        blocking network I/O with a bounded timeout.
        """
        url = self._object_url(key)
        headers = self._signed_headers(method, url, body, content_type=content_type)
        request = UrlRequest(
            url,
            data=body if method in {"PUT", "POST"} else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code == 404:
                if method == "DELETE":
                    return b""
                raise NotFoundError("upload_not_found", "Upload not found") from exc
            raise storage_unavailable_error({"status_code": exc.code}) from exc
        except (TimeoutError, URLError, OSError) as exc:
            raise storage_unavailable_error() from exc

    def _object_url(self, key: str) -> str:
        """Build a path-style object URL for the configured bucket.

        Key parameter is the storage key. Return value is a fully qualified URL.
        Side effect: none.
        """
        base_path = self.endpoint.path.rstrip("/")
        bucket = quote(self.bucket, safe="")
        object_key = quote(key, safe="/-_.~")
        object_path = f"{base_path}/{bucket}/{object_key}"
        return urlunsplit((self.endpoint.scheme, self.endpoint.netloc, object_path, "", ""))

    def _signed_headers(
        self,
        method: str,
        url: str,
        body: bytes,
        *,
        content_type: str | None,
    ) -> dict[str, str]:
        """Create AWS SigV4 headers for one S3-compatible request.

        Key parameters are the method, URL, request body, and optional content type.
        Return value is the signed HTTP header mapping. Side effect: none.
        """
        parsed = urlsplit(url)
        payload_hash = hashlib.sha256(body).hexdigest()
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        canonical_headers = {
            "host": parsed.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            canonical_headers["content-type"] = content_type
        signed_header_names = sorted(canonical_headers)
        canonical_header_text = "".join(
            f"{name}:{canonical_headers[name].strip()}\n" for name in signed_header_names
        )
        signed_headers = ";".join(signed_header_names)
        canonical_request = "\n".join(
            [
                method,
                parsed.path or "/",
                parsed.query,
                canonical_header_text,
                signed_headers,
                payload_hash,
            ]
        )
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Host": parsed.netloc,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
            **({"Content-Type": content_type} if content_type else {}),
        }

    def _signing_key(self, date_stamp: str) -> bytes:
        """Derive the AWS SigV4 signing key for one date.

        Key parameter is the YYYYMMDD date stamp. Return value is raw HMAC key
        bytes. Side effect: none.
        """
        date_key = hmac.new(
            f"AWS4{self.secret_key}".encode(),
            date_stamp.encode(),
            hashlib.sha256,
        ).digest()
        region_key = hmac.new(date_key, self.region.encode(), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

    def _require_config(self, env_name: str, value: str | None) -> str:
        """Return a required S3 config value or raise a safe service error.

        Key parameters are the environment variable name and loaded value. Return
        value is the non-empty string. Side effect: raises without exposing secrets.
        """
        if value:
            return value
        raise AppError(
            "upload_storage_backend_unavailable",
            "Upload storage backend is not configured",
            status_code=503,
            details={"missing": env_name},
        )


def storage_unavailable_error(details: dict[str, object] | None = None) -> AppError:
    """Build a safe storage service error without leaking provider credentials.

    Key parameter is optional non-secret diagnostic details. Return value is an
    `AppError` suitable for API responses. Side effect: none.
    """
    return AppError(
        "upload_storage_unavailable",
        "Upload storage is temporarily unavailable",
        status_code=503,
        details=details,
    )


class UploadService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Create an upload service bound to one database session.

        Key parameters are the async session and optional settings override. Return
        value is none. Side effect: stores collaborators for later upload work.
        """
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
        upload_refs = extract_upload_references(
            raw_md,
            cdn_base_url=self.settings.upload_cdn_base_url,
        )
        if upload_refs.count() > self.settings.upload_max_files_per_post:
            raise ValidationError(
                "upload_count_exceeded",
                "Too many uploads referenced by this post",
                {"max_files": self.settings.upload_max_files_per_post},
            )
        if upload_refs.count() == 0:
            return

        predicates = []
        if upload_refs.ids:
            predicates.append(Upload.id.in_(upload_refs.ids))
        if upload_refs.storage_keys:
            predicates.append(Upload.storage_key.in_(upload_refs.storage_keys))
        result = await self.session.scalars(select(Upload).where(or_(*predicates)))
        uploads_by_id = {upload.id: upload for upload in result}
        uploads_by_key = {upload.storage_key: upload for upload in uploads_by_id.values()}
        missing_ids = [upload_id for upload_id in upload_refs.ids if upload_id not in uploads_by_id]
        missing_keys = [
            storage_key
            for storage_key in upload_refs.storage_keys
            if storage_key not in uploads_by_key
        ]
        if missing_ids or missing_keys:
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
        upload = await self.get_upload_for_delivery(upload_id, current_user)
        return await self.read_upload_content(upload)

    async def get_upload_for_delivery(
        self,
        upload_id: str,
        current_user: User | None,
    ) -> Upload:
        """Load one upload row after applying its read-access policy.

        Key parameters are the upload ID and optional current user. Return value is
        the upload model with attachment relationships loaded. Side effect: raises
        not-found for deleted or unauthorized objects.
        """
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

        return upload

    async def read_upload_content(self, upload: Upload) -> UploadContent:
        """Read original upload bytes from the row's configured storage backend.

        Key parameter is an already authorized upload row. Return value combines
        metadata and bytes. Side effect: performs storage I/O in a worker thread.
        """
        storage = self._storage_for_upload(upload)
        content = await asyncio.to_thread(storage.read, upload.storage_key)
        return UploadContent(upload=upload, content=content)

    async def get_upload_thumbnail(
        self,
        upload_id: str,
        current_user: User | None,
    ) -> UploadThumbnail:
        """Return or lazily generate a small WebP thumbnail for an uploaded image.

        Key parameters mirror `get_upload_content`, including ACL checks. Return value
        is thumbnail bytes plus upload metadata. Side effect: writes a cached
        thumbnail object under the upload storage backend when missing.
        """
        content = await self.get_upload_content(upload_id, current_user)
        if not content.upload.is_image:
            raise NotFoundError("upload_not_found", "Upload not found")

        storage = self._storage_for_upload(content.upload)
        thumbnail_key = self.thumbnail_key_for(content.upload)
        try:
            thumbnail_content = await asyncio.to_thread(storage.read, thumbnail_key)
        except NotFoundError:
            thumbnail_content = self._generate_thumbnail(content.content)
            await asyncio.to_thread(
                storage.write,
                thumbnail_key,
                thumbnail_content,
                THUMBNAIL_MEDIA_TYPE,
            )
        return UploadThumbnail(upload=content.upload, content=thumbnail_content)

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
            await asyncio.to_thread(self.delete_upload_files, upload)
        await self.session.commit()
        return len(uploads)

    def thumbnail_key_for(self, upload: Upload) -> str:
        """Return the cached thumbnail object key for an upload.

        Key parameter is an upload model with a `storage_key`. Return value is the
        relative WebP sidecar key. Side effect: none.
        """
        return f"{THUMBNAIL_DIRECTORY}/{upload.storage_key}.webp"

    def public_upload_url(self, upload: Upload, *, thumbnail: bool = False) -> str | None:
        """Return the public CDN URL for an S3-backed upload when configured.

        Key parameters are the upload row and whether the cached thumbnail object
        should be addressed. Return value is an absolute CDN URL or none. Side
        effect: none.
        """
        if upload.storage_backend != "s3" or not self.settings.upload_cdn_base_url:
            return None
        storage_key = self.thumbnail_key_for(upload) if thumbnail else upload.storage_key
        return public_storage_url(self.settings.upload_cdn_base_url, storage_key)

    def local_path_for(self, upload: Upload) -> Path:
        """Return the absolute local path for an upload storage key.

        Key parameter: `upload` supplies the stored relative key. Return value is an
        absolute path inside the configured upload root. Side effect: validates path
        containment and raises `upload_not_found` on traversal.
        """
        return LocalUploadStorage(self.settings).path_for(upload.storage_key)

    def thumbnail_path_for(self, upload: Upload) -> Path:
        """Return the absolute cached thumbnail path for an upload.

        Key parameter: `upload` supplies the stored relative key. Return value is a
        WebP sidecar path under `_thumbnails/`. Side effect: validates containment
        before callers create or read the file.
        """
        return LocalUploadStorage(self.settings).path_for(self.thumbnail_key_for(upload))

    def delete_upload_files(self, upload: Upload) -> None:
        """Delete the original object and cached thumbnail for one upload.

        Key parameter is the upload model whose `storage_backend` and `storage_key`
        identify stored objects. Return value is none. Side effect: removes objects
        from local storage or S3-compatible storage.
        """
        storage = self._storage_for_upload(upload)
        storage.delete(upload.storage_key)
        storage.delete(self.thumbnail_key_for(upload))

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
        storage = self._storage_for_backend(upload.storage_backend)
        await asyncio.to_thread(storage.write, upload.storage_key, content, media_type)
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

    def _storage_for_upload(self, upload: Upload) -> LocalUploadStorage | S3UploadStorage:
        """Return the storage adapter recorded on an upload row.

        Key parameter is the upload model. Return value is a local or S3-compatible
        storage adapter. Side effect: validates backend configuration as needed.
        """
        return self._storage_for_backend(upload.storage_backend)

    def _storage_for_backend(self, backend: str) -> LocalUploadStorage | S3UploadStorage:
        """Return a storage adapter for a backend name.

        Key parameter is the backend string from settings or the database. Return
        value is a storage adapter. Side effect: raises a safe service error for
        unsupported or unconfigured backends.
        """
        if backend == "local":
            return LocalUploadStorage(self.settings)
        if backend == "s3":
            return S3UploadStorage(self.settings)
        raise AppError(
            "upload_storage_backend_unavailable",
            "Upload storage backend is not available",
            status_code=503,
        )

    def _storage_root(self) -> Path:
        """Return the absolute local upload root for legacy callers.

        Key parameters: none. Return value is a resolved local path. Side effect:
        none.
        """
        return LocalUploadStorage(self.settings).root()

    def _generate_thumbnail(self, source_content: bytes) -> bytes:
        """Generate a constrained WebP thumbnail for stored image bytes.

        Key parameter is the original image content. Return value is WebP bytes.
        Side effect: none beyond PIL decoding and encoding in memory.
        """
        try:
            with Image.open(BytesIO(source_content)) as source_image:
                image = ImageOps.exif_transpose(source_image)
                image.thumbnail(THUMBNAIL_MAX_SIZE, Image.Resampling.LANCZOS)
                image = self._to_thumbnail_rgb(image)
                output = BytesIO()
                image.save(output, "WEBP", quality=82, method=4)
                return output.getvalue()
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

def extract_upload_ids(raw_md: str) -> list[str]:
    """Return API upload IDs referenced by Markdown upload URLs.

    Key parameter is raw Markdown. Return value preserves first-seen order and
    removes duplicates. Side effect: none.
    """
    return extract_upload_references(raw_md).ids


def extract_upload_references(raw_md: str, *, cdn_base_url: str | None = None) -> UploadReferences:
    """Return upload IDs and configured CDN storage keys referenced by Markdown.

    Key parameters are raw Markdown and the optional public CDN base URL. Return
    value keeps unique references in first-seen order. Side effect: none.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for match in UPLOAD_REFERENCE_PATTERN.finditer(raw_md):
        upload_id = match.group(1).lower()
        if upload_id not in seen:
            seen.add(upload_id)
            ordered.append(upload_id)
    storage_keys = extract_cdn_storage_keys(raw_md, cdn_base_url=cdn_base_url)
    return UploadReferences(ids=ordered, storage_keys=storage_keys)


def extract_cdn_storage_keys(raw_md: str, *, cdn_base_url: str | None = None) -> list[str]:
    """Return storage keys referenced through the configured CDN domain.

    Key parameters are raw Markdown and optional CDN base URL. Return value is a
    unique ordered list of object keys. Side effect: none.
    """
    normalized_base = normalized_cdn_base_url(cdn_base_url)
    if not normalized_base:
        return []
    prefix = f"{re.escape(normalized_base)}/"
    pattern = re.compile(rf"{prefix}(?P<key>[^\s\]\"'<>?#)]+)")
    seen: set[str] = set()
    keys: list[str] = []
    for match in pattern.finditer(raw_md):
        storage_key = unquote(match.group("key")).lstrip("/")
        if (
            storage_key.startswith(f"{THUMBNAIL_DIRECTORY}/")
            or not CDN_OBJECT_KEY_PATTERN.fullmatch(storage_key)
            or storage_key in seen
        ):
            continue
        seen.add(storage_key)
        keys.append(storage_key)
    return keys


def public_storage_url(cdn_base_url: str, storage_key: str) -> str:
    """Build an absolute public CDN URL for one upload storage key.

    Key parameters are the CDN base URL and storage key. Return value is a URL with
    the key safely path-encoded. Side effect: none.
    """
    return f"{cdn_base_url.rstrip('/')}/{quote(storage_key, safe='/-_.~')}"


def normalized_cdn_base_url(cdn_base_url: str | None) -> str | None:
    """Normalize a CDN base URL before matching Markdown references.

    Key parameter is an optional configured base URL. Return value is the normalized
    URL without query, fragment, or trailing slash. Side effect: none.
    """
    if not cdn_base_url:
        return None
    parsed = urlsplit(cdn_base_url.rstrip("/"))
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


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
