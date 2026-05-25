from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Column

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401  # Import all model classes so metadata is populated.
from app.db.base import Base
from app.db.schema_comments import COLUMN_COMMENTS, TABLE_COMMENTS


@dataclass(frozen=True)
class PrimaryKeyInfo:
    table: str
    column: str
    type_name: str
    autoincrement: object
    has_python_default: bool
    has_server_default: bool


@dataclass(frozen=True)
class ForeignKeyInfo:
    table: str
    column: str
    type_name: str
    target: str
    target_type_name: str
    type_matches: bool


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SQLAlchemy schema metadata.")
    parser.add_argument("--format", choices=["text", "markdown"], default="text")
    args = parser.parse_args()

    primary_keys = list(iter_primary_keys())
    foreign_keys = list(iter_foreign_keys())
    missing_table_comments = sorted(
        table.name for table in Base.metadata.sorted_tables if table.name not in TABLE_COMMENTS
    )
    missing_column_comments = sorted(
        f"{table.name}.{column.name}"
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.name not in {"id", "created_at", "updated_at"}
        and column.name not in COLUMN_COMMENTS.get(table.name, {})
    )
    legacy_varchar36_pks = [
        info for info in primary_keys if info.type_name.lower().startswith("varchar(36")
    ]
    fk_mismatches = [info for info in foreign_keys if not info.type_matches]

    if args.format == "markdown":
        print_markdown(
            primary_keys,
            foreign_keys,
            legacy_varchar36_pks,
            fk_mismatches,
            missing_table_comments,
            missing_column_comments,
        )
    else:
        print_text(
            primary_keys,
            foreign_keys,
            legacy_varchar36_pks,
            fk_mismatches,
            missing_table_comments,
            missing_column_comments,
        )


def iter_primary_keys() -> Iterable[PrimaryKeyInfo]:
    for table in Base.metadata.sorted_tables:
        for column in table.primary_key.columns:
            yield PrimaryKeyInfo(
                table=table.name,
                column=column.name,
                type_name=column_type(column),
                autoincrement=column.autoincrement,
                has_python_default=column.default is not None,
                has_server_default=column.server_default is not None,
            )


def iter_foreign_keys() -> Iterable[ForeignKeyInfo]:
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                target_column = foreign_key.column
                yield ForeignKeyInfo(
                    table=table.name,
                    column=column.name,
                    type_name=column_type(column),
                    target=f"{target_column.table.name}.{target_column.name}",
                    target_type_name=column_type(target_column),
                    type_matches=column_type(column) == column_type(target_column),
                )


def column_type(column: Column[object]) -> str:
    return str(column.type).lower()


def print_text(
    primary_keys: list[PrimaryKeyInfo],
    foreign_keys: list[ForeignKeyInfo],
    legacy_varchar36_pks: list[PrimaryKeyInfo],
    fk_mismatches: list[ForeignKeyInfo],
    missing_table_comments: list[str],
    missing_column_comments: list[str],
) -> None:
    print("Schema audit")
    print(f"Tables: {len(Base.metadata.sorted_tables)}")
    print(f"Primary keys: {len(primary_keys)}")
    print(f"Foreign keys: {len(foreign_keys)}")
    print(f"Legacy varchar(36) primary keys: {len(legacy_varchar36_pks)}")
    print(f"Foreign key type mismatches: {len(fk_mismatches)}")
    print(f"Missing table comments: {len(missing_table_comments)}")
    print(f"Missing column comments: {len(missing_column_comments)}")


def print_markdown(
    primary_keys: list[PrimaryKeyInfo],
    foreign_keys: list[ForeignKeyInfo],
    legacy_varchar36_pks: list[PrimaryKeyInfo],
    fk_mismatches: list[ForeignKeyInfo],
    missing_table_comments: list[str],
    missing_column_comments: list[str],
) -> None:
    pk_types = Counter(info.type_name for info in primary_keys)
    print("# Schema Audit")
    print()
    print("## Summary")
    print()
    print(f"- Tables: {len(Base.metadata.sorted_tables)}")
    print(f"- Primary key columns: {len(primary_keys)}")
    print(f"- Foreign key columns: {len(foreign_keys)}")
    print(f"- Legacy varchar(36) primary keys: {len(legacy_varchar36_pks)}")
    print(f"- Foreign key type mismatches: {len(fk_mismatches)}")
    print(f"- Missing table comments in registry: {len(missing_table_comments)}")
    print(f"- Missing column comments in registry: {len(missing_column_comments)}")
    print()
    print("## Primary Key Type Distribution")
    print()
    print("| Type | Count |")
    print("|---|---:|")
    for type_name, count in pk_types.most_common():
        print(f"| `{type_name}` | {count} |")
    print()
    print("## Legacy varchar(36) Primary Keys")
    print()
    print("| Table | Column | Autoincrement | Python default | Server default |")
    print("|---|---|---|---|---|")
    for info in legacy_varchar36_pks:
        print(
            f"| `{info.table}` | `{info.column}` | `{info.autoincrement}` | "
            f"{info.has_python_default} | {info.has_server_default} |"
        )
    if fk_mismatches:
        print()
        print("## Foreign Key Type Mismatches")
        print()
        print("| Column | Type | Target | Target type |")
        print("|---|---|---|---|")
        for info in fk_mismatches:
            print(
                f"| `{info.table}.{info.column}` | `{info.type_name}` | "
                f"`{info.target}` | `{info.target_type_name}` |"
            )


if __name__ == "__main__":
    main()

