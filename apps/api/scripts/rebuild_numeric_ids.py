from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Date, DateTime, Time, insert, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.schema import Table

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401  # Import all model classes so metadata is populated.
from app.core.config import get_settings
from app.db.base import Base

IdMap = dict[str, dict[str, str]]
RowsByTable = dict[str, list[dict[str, Any]]]
ExistingSchema = dict[str, dict[str, str]]

# Non-FK columns that store internal row ids with a target type discriminator.
POLYMORPHIC_TARGET_TABLES: dict[str, dict[str, str]] = {
    "reactions": {"topic": "topics", "post": "posts"},
    "bookmarks": {"topic": "topics", "post": "posts"},
    "votes": {"topic": "topics", "post": "posts"},
    "flags": {"topic": "topics", "post": "posts"},
    "reviewables": {
        "topic": "topics",
        "post": "posts",
        "user": "users",
        "flag": "flags",
        "reviewable": "reviewables",
    },
    "drafts": {"topic": "topics"},
    # Audit logs are intentionally text columns because not every target is a row id. Known
    # internal target types are remapped; external/plugin/provider identifiers are preserved.
    "audit_logs": {
        "analytics_report": "background_jobs",
        "api_key": "api_keys",
        "backup_artifact": "backup_artifacts",
        "board": "boards",
        "external_integration_event": "external_integration_events",
        "flag": "flags",
        "payment_event": "payment_events",
        "post": "posts",
        "reviewable": "reviewables",
        "screened_rule": "screened_rules",
        "site_setting": "site_settings",
        "topic": "topics",
        "upload": "uploads",
        "user": "users",
        "webhook_endpoint": "webhook_endpoints",
    },
}

TEXT_COLUMNS_WITH_UPLOAD_URLS: dict[str, tuple[str, ...]] = {
    "posts": ("raw_md", "cooked_html"),
    "post_revisions": ("raw_md", "cooked_html"),
    "users": ("avatar_url",),
}

POLYMORPHIC_SOURCE_TABLES: dict[str, dict[str, str | tuple[str, ...]]] = {
    "user_point_events": {
        "admin_user_update": "users",
        "content_liked": ("posts", "topics"),
        "email_verified": "users",
        "invite_accepted": "board_invitations",
        "post_created": "posts",
        "topic_created": "topics",
    },
    "user_badges": {
        "content_liked": ("posts", "topics"),
        "email_verified": "users",
        "post_created": "posts",
        "topic_created": "topics",
    },
    "user_trust_level_events": {
        "admin_user_update": "users",
        "invite_accepted": "board_invitations",
        "post_created": "posts",
        "topic_created": "topics",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild a local/dev database so legacy string ids become compact numeric "
            "BIGINT ids. Dry-run by default; pass --apply to drop/recreate model tables."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Drop/recreate model tables and insert converted rows.",
    )
    parser.add_argument(
        "--backup-json",
        type=Path,
        default=Path("var/backups/legacy-string-id-backup.json"),
        help="Where to write a JSON backup before applying conversion.",
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        help="Read rows from a previous backup JSON instead of the current database.",
    )
    parser.add_argument(
        "--copy-upload-files",
        action="store_true",
        help="Copy local upload files from old storage_key paths to new numeric paths.",
    )
    asyncio.run(run(parser.parse_args()))


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        if args.source_json:
            existing_schema: ExistingSchema = {}
            rows_by_table = load_rows_from_json(args.source_json)
        else:
            existing_schema = await inspect_existing_schema(conn)
            rows_by_table = await load_rows(conn, existing_schema)
        id_maps = build_id_maps(rows_by_table)
        legacy_samples = legacy_id_samples(rows_by_table, existing_schema)
        if not legacy_samples:
            print("No legacy non-numeric primary keys found; database already uses numeric ids.")
            return

        converted_rows = convert_rows(rows_by_table, id_maps)
        backup_path = args.backup_json
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(
            json.dumps(rows_by_table, ensure_ascii=False, indent=2, default=json_default),
            encoding="utf-8",
        )

        print(f"Tables scanned: {len(rows_by_table)}")
        print(f"Tables with remapped ids: {sum(1 for mapping in id_maps.values() if mapping)}")
        print(f"Legacy primary-key samples: {', '.join(legacy_samples[:5])}")
        print(f"Backup written: {backup_path}")

        if not args.apply:
            print("Dry run only. Re-run with --apply to rebuild tables with numeric ids.")
            return

        upload_moves = plan_upload_file_moves(
            rows_by_table, converted_rows, settings.upload_storage_path
        )
        await set_fk_checks(conn, enabled=False)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await insert_rows(conn, converted_rows)
        await reset_sequences(conn, converted_rows)
        await stamp_alembic_head(conn)
        await set_fk_checks(conn, enabled=True)

    if args.copy_upload_files:
        copy_upload_files(upload_moves)
    await engine.dispose()
    print("Numeric id rebuild completed.")


async def inspect_existing_schema(conn: AsyncConnection) -> ExistingSchema:
    def inspect_sync(sync_conn) -> ExistingSchema:  # type: ignore[no-untyped-def]
        inspector = sa_inspect(sync_conn)
        table_names = set(inspector.get_table_names())
        return {
            table_name: {
                column["name"]: str(column["type"]).lower()
                for column in inspector.get_columns(table_name)
            }
            for table_name in table_names
        }

    return await conn.run_sync(inspect_sync)


async def load_rows(conn: AsyncConnection, existing_schema: ExistingSchema) -> RowsByTable:
    rows_by_table: RowsByTable = {}
    for table in Base.metadata.sorted_tables:
        existing_columns = existing_schema.get(table.name)
        if existing_columns is None:
            rows_by_table[table.name] = []
            continue
        selectable_columns = [
            table.c[column.name] for column in table.columns if column.name in existing_columns
        ]
        if not selectable_columns:
            rows_by_table[table.name] = []
            continue
        statement = select(*selectable_columns)
        if "created_at" in existing_columns and "created_at" in table.c:
            statement = statement.order_by(table.c.created_at, *table.primary_key.columns)
        elif table.primary_key.columns:
            statement = statement.order_by(
                *(column for column in table.primary_key.columns if column.name in existing_columns)
            )
        result = await conn.execute(statement)
        rows_by_table[table.name] = [dict(row) for row in result.mappings()]
    return rows_by_table


def build_id_maps(rows_by_table: RowsByTable) -> IdMap:
    id_maps: IdMap = {}
    for table in Base.metadata.sorted_tables:
        if not has_single_id_pk(table):
            continue
        mapping: dict[str, str] = {}
        for next_id, row in enumerate(rows_by_table.get(table.name, []), start=1):
            old_id = row.get("id")
            if old_id is not None:
                mapping[str(old_id)] = str(next_id)
        id_maps[table.name] = mapping
    return id_maps


def load_rows_from_json(path: Path) -> RowsByTable:
    raw_rows = json.loads(path.read_text(encoding="utf-8"))
    rows_by_table: RowsByTable = {}
    for table in Base.metadata.sorted_tables:
        rows = raw_rows.get(table.name, [])
        rows_by_table[table.name] = [
            coerce_json_row(table, dict(row)) for row in rows if isinstance(row, dict)
        ]
    return rows_by_table


def coerce_json_row(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    for column in table.columns:
        value = row.get(column.name)
        if not isinstance(value, str):
            continue
        try:
            if isinstance(column.type, DateTime):
                row[column.name] = datetime.fromisoformat(value)
            elif isinstance(column.type, Date):
                row[column.name] = date.fromisoformat(value)
            elif isinstance(column.type, Time):
                row[column.name] = time.fromisoformat(value)
        except ValueError:
            continue
    return row


def legacy_id_samples(rows_by_table: RowsByTable, existing_schema: ExistingSchema) -> list[str]:
    samples: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not has_single_id_pk(table):
            continue
        id_type = existing_schema.get(table.name, {}).get("id", "")
        if any(token in id_type for token in ("char", "text", "varchar")):
            samples.append(f"{table.name}.id type={id_type}")
            continue
        for row in rows_by_table.get(table.name, []):
            value = row.get("id")
            if value is not None and not is_int_like(value):
                samples.append(f"{table.name}.id={value}")
                break
    return samples


def convert_rows(rows_by_table: RowsByTable, id_maps: IdMap) -> RowsByTable:
    upload_id_map = id_maps.get("uploads", {})
    converted: RowsByTable = {}
    for table in Base.metadata.sorted_tables:
        table_rows: list[dict[str, Any]] = []
        fk_targets = foreign_key_targets(table)
        for source_row in rows_by_table.get(table.name, []):
            row = dict(source_row)
            if has_single_id_pk(table) and row.get("id") is not None:
                row["id"] = id_maps[table.name][str(row["id"])]
            for column_name, target_table in fk_targets.items():
                if column_name in row:
                    row[column_name] = remap_value(
                        row.get(column_name), id_maps.get(target_table, {})
                    )
            remap_polymorphic_value(table.name, row, id_maps)
            remap_polymorphic_source(table.name, row, id_maps)
            remap_upload_urls(table.name, row, upload_id_map)
            if table.name == "uploads" and row.get("id") and row.get("storage_key"):
                extension = Path(str(row["storage_key"])).suffix
                row["storage_key"] = storage_key_for(str(row["id"]), extension)
            table_rows.append(row)
        converted[table.name] = table_rows
    return converted


def remap_polymorphic_value(table_name: str, row: dict[str, Any], id_maps: IdMap) -> None:
    target_tables = POLYMORPHIC_TARGET_TABLES.get(table_name)
    if not target_tables or "target_id" not in row:
        return
    target_type = row.get("target_type")
    target_table = target_tables.get(str(target_type))
    if target_table:
        row["target_id"] = remap_value(row.get("target_id"), id_maps.get(target_table, {}))


def remap_polymorphic_source(table_name: str, row: dict[str, Any], id_maps: IdMap) -> None:
    source_tables = POLYMORPHIC_SOURCE_TABLES.get(table_name)
    if not source_tables or "source_id" not in row:
        return
    source_type = str(row.get("source_type") or "")
    target_table = source_tables.get(source_type)
    if not target_table:
        return
    if isinstance(target_table, tuple):
        row["source_id"] = remap_value_by_tables(row.get("source_id"), target_table, id_maps)
    else:
        row["source_id"] = remap_value(row.get("source_id"), id_maps.get(target_table, {}))


def remap_upload_urls(
    table_name: str, row: dict[str, Any], upload_id_map: Mapping[str, str]
) -> None:
    if not upload_id_map:
        return
    for column_name in TEXT_COLUMNS_WITH_UPLOAD_URLS.get(table_name, ()):
        value = row.get(column_name)
        if not isinstance(value, str):
            continue
        for old_id, new_id in upload_id_map.items():
            value = value.replace(f"/uploads/{old_id}/content", f"/uploads/{new_id}/content")
            value = value.replace(
                f"/api/v1/uploads/{old_id}/content", f"/api/v1/uploads/{new_id}/content"
            )
        row[column_name] = value


async def insert_rows(conn: AsyncConnection, rows_by_table: RowsByTable) -> None:
    for table in Base.metadata.sorted_tables:
        rows = rows_by_table.get(table.name, [])
        if rows:
            await conn.execute(insert(table), rows)


async def reset_sequences(conn: AsyncConnection, rows_by_table: RowsByTable) -> None:
    dialect = conn.dialect.name
    for table in Base.metadata.sorted_tables:
        if not has_single_id_pk(table):
            continue
        rows = rows_by_table.get(table.name, [])
        max_id = max((int(row["id"]) for row in rows if row.get("id") is not None), default=0)
        if max_id <= 0:
            continue
        quoted_table = table.name.replace('"', '""')
        if dialect.startswith("postgresql"):
            await conn.execute(
                text(
                    "select setval(pg_get_serial_sequence(:table_name, 'id'), :next_value, true)"
                ),
                {"table_name": table.name, "next_value": max_id},
            )
        elif dialect in {"mysql", "mariadb"}:
            await conn.execute(text(f"ALTER TABLE `{table.name}` AUTO_INCREMENT = {max_id + 1}"))
        elif dialect == "sqlite":
            await conn.execute(
                text("UPDATE sqlite_sequence SET seq = :seq WHERE name = :name"),
                {"seq": max_id, "name": table.name},
            )
        else:
            print(f"Sequence reset skipped for unsupported dialect: {dialect}.{quoted_table}")


async def set_fk_checks(conn: AsyncConnection, *, enabled: bool) -> None:
    dialect = conn.dialect.name
    if dialect in {"mysql", "mariadb"}:
        await conn.execute(text(f"SET FOREIGN_KEY_CHECKS={1 if enabled else 0}"))
    elif dialect == "sqlite":
        await conn.execute(text(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}"))
    elif dialect.startswith("postgresql"):
        role = "origin" if enabled else "replica"
        try:
            await conn.execute(text(f"SET session_replication_role = {role}"))
        except Exception as exc:  # noqa: BLE001
            print(f"PostgreSQL FK bypass skipped ({exc}); insert order must satisfy constraints.")


def foreign_key_targets(table: Table) -> dict[str, str]:
    targets: dict[str, str] = {}
    for column in table.columns:
        for foreign_key in column.foreign_keys:
            targets[column.name] = foreign_key.column.table.name
    return targets


def has_single_id_pk(table: Table) -> bool:
    if len(table.primary_key.columns) != 1:
        return False
    return next(iter(table.primary_key.columns)).name == "id"


def remap_value(value: Any, mapping: Mapping[str, str]) -> Any:
    if value is None or value == "":
        return value
    return mapping.get(str(value), value)


def remap_value_by_tables(value: Any, table_names: tuple[str, ...], id_maps: IdMap) -> Any:
    if value is None or value == "":
        return value
    raw_value = str(value)
    for table_name in table_names:
        mapping = id_maps.get(table_name, {})
        if raw_value in mapping:
            return mapping[raw_value]
    return value


def is_int_like(value: Any) -> bool:
    try:
        int(str(value))
    except (TypeError, ValueError):
        return False
    return True


def storage_key_for(upload_id: str, extension: str) -> str:
    safe_extension = extension if extension.startswith(".") else f".{extension}"
    bucket = upload_id[-2:].zfill(2)
    return f"{bucket}/{upload_id}{safe_extension}"


def plan_upload_file_moves(
    source_rows: RowsByTable, converted_rows: RowsByTable, upload_storage_path: str
) -> list[tuple[Path, Path]]:
    old_rows = source_rows.get("uploads", [])
    new_rows = converted_rows.get("uploads", [])
    root = Path(upload_storage_path)
    if not root.is_absolute():
        root = Path.cwd() / root
    moves: list[tuple[Path, Path]] = []
    for old_row, new_row in zip(old_rows, new_rows, strict=False):
        old_key = old_row.get("storage_key")
        new_key = new_row.get("storage_key")
        if old_key and new_key and old_key != new_key:
            moves.append(((root / str(old_key)).resolve(), (root / str(new_key)).resolve()))
    return moves


def copy_upload_files(moves: list[tuple[Path, Path]]) -> None:
    copied = 0
    for source, target in moves:
        if not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    print(f"Copied upload files: {copied}")


async def stamp_alembic_head(conn: AsyncConnection) -> None:
    head_revision = alembic_head_revision()
    await conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
        )
    )
    await conn.execute(text("DELETE FROM alembic_version"))
    await conn.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
        {"version_num": head_revision},
    )


def alembic_head_revision() -> str:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def json_default(value: Any) -> str:
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


if __name__ == "__main__":
    main()
