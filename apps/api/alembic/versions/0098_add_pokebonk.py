"""Add the external PokéBonk entry without changing existing catalog records.

Revision ID: 0098_add_pokebonk
Revises: 0097_add_four_external_games
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import op

revision: str = "0098_add_pokebonk"
down_revision: str | None = "0097_add_four_external_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pokebonk_root_url(value: str) -> bool:
    """Match the root site, including historical scheme/www/tracking variants.

    Only the exact host (optionally www) and root path are equivalent. Other
    subdomains, non-root game paths and non-default ports remain separate.
    Query strings and fragments do not identify a different root game.
    """

    try:
        parsed = urlsplit(value.strip())
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return False
    if scheme not in {"http", "https"}:
        return False
    if host.startswith("www."):
        host = host[4:]
    default_port = 80 if scheme == "http" else 443
    return (
        host == "pokebonk.com"
        and not parsed.path.rstrip("/")
        and port in {None, default_port}
    )


def upgrade() -> None:
    """Append one action game; preserve existing entries, visibility and stats."""

    bind = op.get_bind()
    # Deliberately include hidden entries and every category. A previous manual
    # entry must not be duplicated, unhidden, moved or otherwise overwritten.
    existing = bind.execute(
        sa.text("SELECT slug, destination_url FROM catalog_projects")
    ).mappings()
    if any(
        row["slug"].strip().casefold() == "pokebonk"
        or _is_pokebonk_root_url(row["destination_url"])
        for row in existing
    ):
        return

    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
        {"slug": "action"},
    )
    if category_id is None:
        raise RuntimeError("0098 requires catalog category action")

    next_order = (
        int(
            bind.scalar(
                sa.text(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
        )
        + 1
    )
    now = datetime.now(UTC)
    # view_count uses the existing server default 0; no rating or upload row is
    # created or changed by this catalog-only migration.
    bind.execute(
        sa.text(
            "INSERT INTO catalog_projects "
            "(category_id, slug, name, destination_url, destination_kind, description, "
            "author_name, author_url, sort_order, is_visible, created_at, updated_at) "
            "VALUES (:category_id, :slug, :name, :url, 'external', :description, "
            ":author_name, :author_url, :sort_order, TRUE, :now, :now)"
        ),
        {
            "category_id": category_id,
            "slug": "pokebonk",
            "name": "PokéBonk",
            "url": "https://pokebonk.com/",
            "description": (
                "浏览器游玩的免费 3D 宝可梦幸存者类同人游戏，在敌群中生存、进化并解锁宝可梦；"
                "非官方作品。"
            ),
            "author_name": "Charcher",
            "author_url": "https://x.com/ImCharcher",
            "sort_order": next_order,
            "now": now,
        },
    )


def downgrade() -> None:
    """Keep the business record and its possible later edits, ratings and views."""

    pass
