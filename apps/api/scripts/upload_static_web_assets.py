from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.uploads import S3UploadStorage, public_storage_url

STATIC_WEB_PREFIX = "static/web"
ASTRA_COVER_DIR = (
    Path(__file__).resolve().parents[3] / "static/web/catalog/2026-09-26-v1/covers"
)
ASTRA_ILLUSTRATION_DIR = (
    Path(__file__).resolve().parents[3] / "static/web/catalog/2026-09-26-v2/covers"
)


@dataclass(frozen=True)
class StaticAsset:
    """One frontend static file that should be published under the CDN static prefix."""

    source: str
    key: str
    media_type: str


# 本地快照生成的独立卡面集中放在新版目录，只在指定版本时上传。
CATALOG_ASTRA_COVER_KEYS = tuple(
    f"catalog/2026-09-26-v1/covers/{path.name}"
    for path in sorted(ASTRA_COVER_DIR.glob("astra-*.svg"))
)
# 逐张制作的游戏插画只发布已完成的 WebP，旧 SVG 仍保留为未完成项目的兜底。
CATALOG_ASTRA_ILLUSTRATION_KEYS = tuple(
    f"catalog/2026-09-26-v2/covers/{path.name}"
    for path in sorted(ASTRA_ILLUSTRATION_DIR.glob("astra-*.webp"))
)

CATALOG_ASSET_KEYS = (
    "catalog/2026-09-24-v1/chibi-cat-explorer.webp",
    "catalog/2026-09-24-v1/hero-sky.webp",
    "catalog/2026-09-24-v1/covers/cf-transport.webp",
    "catalog/2026-09-24-v1/covers/clock-out.webp",
    "catalog/2026-09-24-v1/covers/csgo-desert.webp",
    "catalog/2026-09-24-v1/covers/discover.webp",
    "catalog/2026-09-24-v1/covers/fablespace.webp",
    "catalog/2026-09-24-v1/covers/fruit-ninja.webp",
    "catalog/2026-09-24-v1/covers/generals-soldiers.webp",
    "catalog/2026-09-24-v1/covers/infinite-garden.webp",
    "catalog/2026-09-24-v1/covers/merge-watermelon.webp",
    "catalog/2026-09-24-v1/covers/pelican-bike.webp",
    "catalog/2026-09-24-v1/covers/qin-imperial-factory.webp",
    "catalog/2026-09-24-v1/covers/qq-racing.webp",
    "catalog/2026-09-24-v1/covers/super-mario.webp",
    "catalog/2026-09-25-v1/covers/encounter-command-console.webp",
    "catalog/2026-09-25-v1/covers/geodesic-explorer.webp",
    "catalog/2026-09-25-v1/covers/hyperbolic-room.webp",
    "catalog/2026-09-25-v1/covers/liuxin-watermelon.webp",
    "catalog/2026-09-25-v1/covers/non-euclidean-lab.webp",
    "catalog/2026-09-25-v1/covers/sanguo-zhengshi.webp",
    "catalog/2026-09-25-v1/covers/secondhand-3c-store.webp",
    "catalog/2026-09-25-v1/covers/sneaky-thief.webp",
    "catalog/2026-09-25-v1/covers/voxel-tides.webp",
    "catalog/2026-09-25-v1/covers/xing-lei-shou-wei.webp",
    "catalog/2026-09-25-v1/covers/yeyu-tanglou.webp",
    "catalog/2026-09-25-v1/covers/yongyao-crystal-tower.webp",
    "catalog/2026-09-25-v1/covers/yu-gi-oh-destiny-duel.webp",
    "catalog/2026-09-25-v1/covers/zhi-guai-lu.webp",
) + CATALOG_ASTRA_COVER_KEYS + CATALOG_ASTRA_ILLUSTRATION_KEYS

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
        source="static/web/private-space-entry-b7d15288.png",
        key="private-space-entry-b7d15288.png",
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
) + tuple(
    StaticAsset(
        source=f"static/web/{key}",
        key=key,
        media_type="image/svg+xml" if key.endswith(".svg") else "image/webp",
    )
    for key in CATALOG_ASSET_KEYS
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
def upload_static_assets(
    *, prefix: str, dry_run: bool, verify: bool,
    catalog_only: bool = False, catalog_version: str | None = None,
) -> None:
    """Upload configured frontend static assets to S3/R2 and print their public CDN URLs."""

    settings = Settings()
    storage = None if dry_run else S3UploadStorage(settings)
    root = repo_root()
    if not settings.upload_cdn_base_url:
        raise RuntimeError("UPLOAD_CDN_BASE_URL is required to print public static asset URLs")

    # 本次发布只写入新版目录图片，避免重传已有的认证页和头像资源。
    assets = (
        (asset for asset in STATIC_ASSETS if asset.key in CATALOG_ASSET_KEYS)
        if catalog_only
        else STATIC_ASSETS
    )
    # 指定版本时只发布该版本新图，不重传其他目录版本或站点资源。
    if catalog_version:
        if catalog_version == "2026-09-26-v1" and len(CATALOG_ASTRA_COVER_KEYS) != 157:
            raise RuntimeError("expected 157 generated Astra cover files")
        version_prefix = f"catalog/{catalog_version.strip('/')}/"
        assets = tuple(asset for asset in assets if asset.key.startswith(version_prefix))
        if not assets:
            raise ValueError(f"no catalog assets for version {catalog_version}")
    for asset in assets:
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
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="Upload only the versioned catalog images.",
    )
    parser.add_argument(
        "--catalog-version",
        help="Upload only catalog images in this version directory.",
    )
    return parser.parse_args()


# Console entrypoint for `uv --directory apps/api run python scripts/upload_static_web_assets.py`.
def main() -> None:
    """Run the static asset upload command using runtime environment settings."""

    args = parse_args()
    upload_static_assets(
        prefix=args.prefix,
        dry_run=args.dry_run,
        verify=args.verify,
        catalog_only=args.catalog_only,
        catalog_version=args.catalog_version,
    )


if __name__ == "__main__":
    main()
