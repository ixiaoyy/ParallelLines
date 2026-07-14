"""retire comics board and its uploaded assets

Revision ID: 0066_retire_comics_board
Revises: 0065_add_user_persona_flag
Create Date: 2026-07-14
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa

from alembic import op
from app.services.uploads import UploadService

revision: str = "0066_retire_comics_board"
down_revision: str | None = "0065_add_user_persona_flag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "comics"
TAG_SLUG = "comics"
UPLOAD_REFERENCE_PATTERN = re.compile(r"/(?:api/v1/)?uploads/([1-9][0-9]*)/content")


def upgrade() -> None:
    """Delete the comics board, its content, and every associated upload object.

    Key parameters: none. Return value: none. Side effects: removes original and
    thumbnail objects from local/S3 storage, then deletes their rows and all data
    owned by the `comics` board. Missing tables or an absent board are safe no-ops.
    """

    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if not {"boards", "topics", "posts"}.issubset(existing_tables):
        return

    board_id = bind.execute(
        sa.text("SELECT id FROM boards WHERE slug = :slug LIMIT 1"),
        {"slug": BOARD_SLUG},
    ).scalar_one_or_none()
    if board_id is None:
        _delete_comics_tag(bind, existing_tables)
        return

    topic_ids = list(
        bind.execute(
            sa.text("SELECT id FROM topics WHERE board_id = :board_id"),
            {"board_id": board_id},
        ).scalars()
    )
    post_rows = list(
        bind.execute(
            sa.text(
                "SELECT id, raw_md, cooked_html FROM posts "
                "WHERE topic_id IN (SELECT id FROM topics WHERE board_id = :board_id)"
            ),
            {"board_id": board_id},
        ).mappings()
    )
    post_ids = [row["id"] for row in post_rows]
    referenced_upload_ids = _extract_upload_ids(post_rows)

    if "uploads" in existing_tables:
        upload_rows = _find_board_uploads(
            bind,
            board_id=board_id,
            topic_ids=topic_ids,
            post_ids=post_ids,
            referenced_upload_ids=referenced_upload_ids,
        )
        _delete_upload_objects(upload_rows)
        upload_ids = [row["id"] for row in upload_rows]
        if upload_ids:
            bind.execute(sa.text("DELETE FROM uploads WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ), {"ids": upload_ids})

    bind.execute(sa.text("DELETE FROM boards WHERE id = :board_id"), {"board_id": board_id})
    _delete_comics_tag(bind, existing_tables)


def downgrade() -> None:
    """Keep the destructive board retirement irreversible.

    Key parameters: none. Return value: none. Side effect: none. Deleted user
    content and storage objects cannot be reconstructed safely during downgrade.
    """


def _extract_upload_ids(post_rows: list[sa.RowMapping]) -> set[int]:
    """Extract API upload IDs referenced by the retiring board's post bodies.

    Key parameter `post_rows` contains raw Markdown and cooked HTML. Return value
    is the distinct numeric upload IDs. Side effect: none.
    """

    upload_ids: set[int] = set()
    for row in post_rows:
        for body in (row["raw_md"], row["cooked_html"]):
            upload_ids.update(int(value) for value in UPLOAD_REFERENCE_PATTERN.findall(body or ""))
    return upload_ids


def _find_board_uploads(
    bind: sa.Connection,
    *,
    board_id: int,
    topic_ids: list[int],
    post_ids: list[int],
    referenced_upload_ids: set[int],
) -> list[sa.RowMapping]:
    """Return upload rows owned by or referenced from the comics board.

    Key parameters identify the board and its topic/post/upload IDs. Return value
    contains the metadata needed for object deletion. Side effect: reads the DB.
    """

    predicates = ["board_id = :board_id"]
    parameters: dict[str, object] = {"board_id": board_id}
    expanding_names: list[str] = []
    for name, values, column in (
        ("topic_ids", topic_ids, "topic_id"),
        ("post_ids", post_ids, "post_id"),
        ("upload_ids", sorted(referenced_upload_ids), "id"),
    ):
        if values:
            predicates.append(f"{column} IN :{name}")
            parameters[name] = values
            expanding_names.append(name)

    statement = sa.text(
        "SELECT id, storage_backend, storage_key FROM uploads WHERE " + " OR ".join(predicates)
    )
    for name in expanding_names:
        statement = statement.bindparams(sa.bindparam(name, expanding=True))
    return list(bind.execute(statement, parameters).mappings())


def _delete_upload_objects(upload_rows: list[sa.RowMapping]) -> None:
    """Delete original objects and cached thumbnails for selected upload rows.

    Key parameter `upload_rows` supplies backend and object keys. Return value is
    none. Side effect: performs local filesystem or signed S3 DELETE operations.
    """

    service = UploadService(None)  # type: ignore[arg-type]
    for row in upload_rows:
        upload = SimpleNamespace(
            storage_backend=row["storage_backend"],
            storage_key=row["storage_key"],
        )
        service.delete_upload_files(upload)  # type: ignore[arg-type]


def _delete_comics_tag(bind: sa.Connection, existing_tables: set[str]) -> None:
    """Delete the dedicated comics tag after its board topics are gone.

    Key parameters are the migration connection and known table names. Return
    value is none. Side effect: deletes only the tag whose stable slug is comics.
    """

    if "tags" in existing_tables:
        bind.execute(sa.text("DELETE FROM tags WHERE slug = :slug"), {"slug": TAG_SLUG})
