from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.models.upload import Upload
from app.services.uploads import THUMBNAIL_DIRECTORY, LocalUploadStorage, S3UploadStorage


@dataclass(slots=True)
class MigrationOptions:
    """Runtime switches for the local-to-S3 upload migration command."""

    apply: bool
    all_files: bool
    include_deleted: bool
    batch_size: int
    limit: int | None
    start_after_id: str | None
    no_verify: bool
    ignore_sha256_mismatch: bool
    stop_on_error: bool
    env_file: str | None
    local_root: str | None


@dataclass(slots=True)
class MigrationStats:
    """Counters printed at the end of one migration run."""

    candidates: int = 0
    migrated: int = 0
    dry_run_ready: int = 0
    skipped_missing_source: int = 0
    skipped_sha256_mismatch: int = 0
    thumbnails_migrated: int = 0
    thumbnails_missing: int = 0
    failed: int = 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the upload migration command.

    Key parameters: none. Return value is an argparse parser. Side effect: none.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Migrate local upload objects to the configured S3-compatible backend "
            "without changing public upload URLs."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Preview candidates without writing to S3 or updating database rows. "
            "This is the default."
        ),
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write objects to S3/R2 and mark migrated upload rows as storage_backend=s3.",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Migrate every local upload row instead of only image uploads.",
    )
    parser.add_argument(
        "--include-deleted",
        action="store_true",
        help="Include rows marked deleted. Usually leave this off.",
    )
    parser.add_argument("--batch-size", type=int, default=100, help="Rows to load per DB batch.")
    parser.add_argument("--limit", type=int, help="Stop after inspecting this many candidate rows.")
    parser.add_argument("--start-after-id", help="Resume after this upload id.")
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip read-after-write verification from S3/R2.",
    )
    parser.add_argument(
        "--ignore-sha256-mismatch",
        action="store_true",
        help="Upload even when local bytes do not match uploads.sha256.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Abort immediately on the first row that cannot be migrated.",
    )
    parser.add_argument(
        "--env-file",
        help="Optional env file path. Defaults to Settings' normal .env loading.",
    )
    parser.add_argument(
        "--local-root",
        help="Override UPLOAD_STORAGE_PATH for reading existing local files.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> MigrationOptions:
    """Parse command-line arguments into migration options.

    Key parameter is the optional argv list. Return value is `MigrationOptions`.
    Side effect: exits through argparse when arguments are invalid.
    """
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    return MigrationOptions(
        apply=bool(args.apply),
        all_files=bool(args.all_files),
        include_deleted=bool(args.include_deleted),
        batch_size=args.batch_size,
        limit=args.limit,
        start_after_id=args.start_after_id,
        no_verify=bool(args.no_verify),
        ignore_sha256_mismatch=bool(args.ignore_sha256_mismatch),
        stop_on_error=bool(args.stop_on_error),
        env_file=args.env_file,
        local_root=args.local_root,
    )


def load_settings(options: MigrationOptions) -> Settings:
    """Load runtime settings for database, local storage, and S3/R2 access.

    Key parameter is the parsed migration options. Return value is a `Settings`
    instance. Side effect: may read the configured env file.
    """
    settings = Settings(_env_file=options.env_file) if options.env_file else Settings()
    if options.local_root:
        settings.upload_storage_path = options.local_root
    return settings


def upload_filters(options: MigrationOptions) -> list[object]:
    """Return SQLAlchemy filters shared by count and batch upload queries.

    Key parameter is the parsed migration options. Return value is a list of SQL
    expressions. Side effect: none.
    """
    filters: list[object] = [Upload.storage_backend == "local"]
    if not options.all_files:
        filters.append(Upload.is_image.is_(True))
    if not options.include_deleted:
        filters.extend([Upload.status != "deleted", Upload.deleted_at.is_(None)])
    return filters


def count_statement(options: MigrationOptions) -> Select[tuple[int]]:
    """Build the candidate count query for a migration preview.

    Key parameter is the parsed migration options. Return value is a SQLAlchemy
    select statement. Side effect: none.
    """
    return select(func.count()).select_from(Upload).where(*upload_filters(options))


def batch_statement(
    options: MigrationOptions,
    last_id: str | None,
    remaining: int,
) -> Select[tuple[Upload]]:
    """Build one ordered upload batch query.

    Key parameters are migration options, the last processed id, and remaining row
    budget. Return value is a SQLAlchemy select statement. Side effect: none.
    """
    filters = upload_filters(options)
    if last_id:
        filters.append(Upload.id > last_id)
    return (
        select(Upload)
        .where(*filters)
        .order_by(Upload.id)
        .limit(min(options.batch_size, remaining))
    )


async def migrate_uploads(options: MigrationOptions) -> MigrationStats:
    """Run the upload migration using the configured database and storage backends.

    Key parameter is the parsed migration options. Return value is final migration
    counters. Side effects: in apply mode, writes objects to S3/R2 and updates DB rows.
    """
    settings = load_settings(options)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    local_storage = LocalUploadStorage(settings)
    s3_storage = S3UploadStorage(settings)

    if settings.upload_storage_backend != "s3":
        print(
            "warning: UPLOAD_STORAGE_BACKEND is not s3; migrated rows can still use S3, "
            "but new uploads will keep using the configured backend.",
            file=sys.stderr,
        )

    try:
        async with session_factory() as session:
            total = await session.scalar(count_statement(options))
            print(
                f"mode={'apply' if options.apply else 'dry-run'} "
                f"scope={'all-files' if options.all_files else 'images-only'} "
                f"candidate_rows={total}"
            )
            return await process_batches(session, local_storage, s3_storage, options)
    finally:
        await engine.dispose()


async def process_batches(
    session: AsyncSession,
    local_storage: LocalUploadStorage,
    s3_storage: S3UploadStorage,
    options: MigrationOptions,
) -> MigrationStats:
    """Process upload rows in id order until the candidate or limit budget is exhausted.

    Key parameters are the DB session, storage adapters, and migration options.
    Return value is final migration counters. Side effects depend on apply mode.
    """
    stats = MigrationStats()
    last_id = options.start_after_id
    remaining = options.limit or sys.maxsize

    while remaining > 0:
        result = await session.scalars(batch_statement(options, last_id, remaining))
        uploads = list(result)
        if not uploads:
            break

        for upload in uploads:
            last_id = upload.id
            stats.candidates += 1
            remaining -= 1
            try:
                await migrate_one_upload(session, upload, local_storage, s3_storage, options, stats)
            except Exception as exc:  # noqa: BLE001 - migration CLI must report and continue safely.
                await session.rollback()
                stats.failed += 1
                print(f"upload {upload.id}: failed: {exc}", file=sys.stderr)
                if options.stop_on_error:
                    raise
            if remaining <= 0:
                break

    return stats


async def migrate_one_upload(
    session: AsyncSession,
    upload: Upload,
    local_storage: LocalUploadStorage,
    s3_storage: S3UploadStorage,
    options: MigrationOptions,
    stats: MigrationStats,
) -> None:
    """Migrate one upload row and its cached thumbnail when present.

    Key parameters are the DB session, upload row, storage adapters, options, and
    counters. Return value is none. Side effects: may write S3 objects and update
    `uploads.storage_backend`.
    """
    source_path = local_storage.path_for(upload.storage_key)
    if not source_path.is_file():
        stats.skipped_missing_source += 1
        print(f"upload {upload.id}: missing local object {upload.storage_key}")
        return

    if not options.apply:
        stats.dry_run_ready += 1
        if upload.is_image and not thumbnail_path_for(local_storage, upload).is_file():
            stats.thumbnails_missing += 1
        print(f"upload {upload.id}: ready {upload.storage_key}")
        return

    content = local_storage.read(upload.storage_key)
    if not sha256_matches(upload, content) and not options.ignore_sha256_mismatch:
        stats.skipped_sha256_mismatch += 1
        print(f"upload {upload.id}: sha256 mismatch, skipped")
        return

    write_and_verify(
        s3_storage,
        upload.storage_key,
        content,
        upload.media_type,
        verify=not options.no_verify,
    )
    if upload.is_image:
        migrate_thumbnail_if_present(local_storage, s3_storage, upload, options, stats)

    upload.storage_backend = "s3"
    await session.commit()
    stats.migrated += 1
    print(f"upload {upload.id}: migrated {upload.storage_key}")


def write_and_verify(
    s3_storage: S3UploadStorage,
    key: str,
    content: bytes,
    media_type: str,
    *,
    verify: bool,
) -> None:
    """Write one object to S3/R2 and optionally verify it by reading it back.

    Key parameters are target storage, object key, bytes, media type, and verify
    flag. Return value is none. Side effect: writes and optionally reads the object.
    """
    s3_storage.write(key, content, media_type)
    if verify and s3_storage.read(key) != content:
        raise RuntimeError(f"S3 verification failed for {key}")


def migrate_thumbnail_if_present(
    local_storage: LocalUploadStorage,
    s3_storage: S3UploadStorage,
    upload: Upload,
    options: MigrationOptions,
    stats: MigrationStats,
) -> None:
    """Copy an existing cached thumbnail for one image upload when it exists locally.

    Key parameters are storage adapters, upload row, options, and counters. Return
    value is none. Side effects: may write the thumbnail object to S3/R2.
    """
    thumbnail_key = thumbnail_key_for(upload)
    try:
        thumbnail = local_storage.read(thumbnail_key)
    except NotFoundError:
        stats.thumbnails_missing += 1
        return
    write_and_verify(
        s3_storage,
        thumbnail_key,
        thumbnail,
        "image/webp",
        verify=not options.no_verify,
    )
    stats.thumbnails_migrated += 1


def thumbnail_key_for(upload: Upload) -> str:
    """Return the cached WebP thumbnail key for one upload row.

    Key parameter is an upload model. Return value is the relative thumbnail key.
    Side effect: none.
    """
    return f"{THUMBNAIL_DIRECTORY}/{upload.storage_key}.webp"


def thumbnail_path_for(local_storage: LocalUploadStorage, upload: Upload) -> Path:
    """Return the local thumbnail path for a dry-run existence check.

    Key parameters are local storage adapter and upload row. Return value is an
    absolute path. Side effect: validates that the key stays under the upload root.
    """
    return local_storage.path_for(thumbnail_key_for(upload))


def sha256_matches(upload: Upload, content: bytes) -> bool:
    """Check local bytes against the checksum stored on the upload row.

    Key parameters are the upload model and source bytes. Return value is true when
    the checksum matches or the row has no checksum. Side effect: none.
    """
    return not upload.sha256 or hashlib.sha256(content).hexdigest() == upload.sha256


def print_summary(stats: MigrationStats) -> None:
    """Print a compact migration summary.

    Key parameter is the final migration stats. Return value is none. Side effect:
    writes human-readable counters to stdout.
    """
    print(
        "summary: "
        f"candidates={stats.candidates} "
        f"dry_run_ready={stats.dry_run_ready} "
        f"migrated={stats.migrated} "
        f"missing_source={stats.skipped_missing_source} "
        f"sha256_mismatch={stats.skipped_sha256_mismatch} "
        f"thumbnails_migrated={stats.thumbnails_migrated} "
        f"thumbnails_missing={stats.thumbnails_missing} "
        f"failed={stats.failed}"
    )


async def async_main(argv: list[str] | None = None) -> int:
    """Async entrypoint for the migration command.

    Key parameter is an optional argv list. Return value is a process exit code.
    Side effects are those of `migrate_uploads`.
    """
    options = parse_args(argv)
    stats = await migrate_uploads(options)
    print_summary(stats)
    if options.apply and (
        stats.failed or stats.skipped_missing_source or stats.skipped_sha256_mismatch
    ):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous console entrypoint for `python -m app.migrate_uploads_to_s3`.

    Key parameter is an optional argv list. Return value is a process exit code.
    Side effect: runs the asyncio event loop.
    """
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
