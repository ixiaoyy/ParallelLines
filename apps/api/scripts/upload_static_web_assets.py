from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.uploads import S3UploadStorage, public_storage_url

STATIC_WEB_PREFIX = "static/web"


@dataclass(frozen=True)
class StaticAsset:
    """One frontend static file that should be published under the CDN static prefix."""

    source: str
    key: str
    media_type: str


STATIC_ASSETS = (
    StaticAsset(
        source="static/web/auth-visual/parallel-auth-pc-bg.png",
        key="auth-visual/parallel-auth-pc-bg.png",
        media_type="image/png",
    ),
    StaticAsset(
        source="static/web/auth-visual/parallel-auth-h5-bg.png",
        key="auth-visual/parallel-auth-h5-bg.png",
        media_type="image/png",
    ),
    StaticAsset(
        source="static/web/auth-visual/auth-mark.png",
        key="auth-visual/auth-mark.png",
        media_type="image/png",
    ),
    StaticAsset(
        source="static/web/avatar-frames/level-1.webp",
        key="avatar-frames/level-1.webp",
        media_type="image/webp",
    ),
    StaticAsset(
        source="static/web/avatar-frames/level-2.webp",
        key="avatar-frames/level-2.webp",
        media_type="image/webp",
    ),
    StaticAsset(
        source="static/web/avatar-frames/level-3.webp",
        key="avatar-frames/level-3.webp",
        media_type="image/webp",
    ),
    StaticAsset(
        source="static/web/avatar-frames/level-4.webp",
        key="avatar-frames/level-4.webp",
        media_type="image/webp",
    ),
    StaticAsset(
        source="static/web/avatar-frames/level-5.webp",
        key="avatar-frames/level-5.webp",
        media_type="image/webp",
    ),
    StaticAsset(
        source="static/web/avatar-frames/ultimate-animated.webp",
        key="avatar-frames/ultimate-animated.webp",
        media_type="image/webp",
    ),
)


# Returns the repository root so this script can be launched from apps/api or the repo root.
def repo_root() -> Path:
    """Return the absolute repository root inferred from this script path."""

    return Path(__file__).resolve().parents[3]


# Builds the object key for one static asset under the configured CDN directory prefix.
def object_key(asset: StaticAsset, prefix: str) -> str:
    """Return the normalized object key for one static asset and directory prefix."""

    return f"{prefix.strip('/')}/{asset.key.lstrip('/')}"


# Uploads all declared frontend static assets without creating upload database rows.
def upload_static_assets(*, prefix: str, dry_run: bool, verify: bool) -> None:
    """Upload configured frontend static assets to S3/R2 and print their public CDN URLs."""

    settings = Settings()
    storage = None if dry_run else S3UploadStorage(settings)
    root = repo_root()
    if not settings.upload_cdn_base_url:
        raise RuntimeError("UPLOAD_CDN_BASE_URL is required to print public static asset URLs")

    for asset in STATIC_ASSETS:
        source_path = root / asset.source
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        key = object_key(asset, prefix)
        content = source_path.read_bytes()
        public_url = public_storage_url(settings.upload_cdn_base_url, key)
        action = "would upload" if dry_run else "uploaded"
        if storage is not None:
            storage.write(key, content, asset.media_type)
            if verify and storage.read(key) != content:
                raise RuntimeError(f"verification failed for {key}")
        print(f"{action} {asset.source} -> {key} ({len(content)} bytes)")
        print(public_url)


# Parses CLI flags while keeping the default prefix stable for production deploys.
def parse_args() -> argparse.Namespace:
    """Parse command-line options for static frontend asset upload."""

    parser = argparse.ArgumentParser(
        description="Upload built-in frontend static assets to the CDN bucket."
    )
    parser.add_argument(
        "--prefix",
        default=STATIC_WEB_PREFIX,
        help="Object key prefix for frontend static assets.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned uploads without writing objects.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read each object back after upload and compare bytes.",
    )
    return parser.parse_args()


# Console entrypoint for `uv --directory apps/api run python scripts/upload_static_web_assets.py`.
def main() -> None:
    """Run the static asset upload command using runtime environment settings."""

    args = parse_args()
    upload_static_assets(prefix=args.prefix, dry_run=args.dry_run, verify=args.verify)


if __name__ == "__main__":
    main()