"""apply schema comments

Revision ID: 0005_schema_comments
Revises: 0004_create_moderation
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from alembic import op
from app.db.schema_comments import COLUMN_COMMENTS, COMMON_COLUMN_COMMENTS, TABLE_COMMENTS

revision: str = "0005_schema_comments"
down_revision: str | None = "0004_create_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALEMBIC_TABLE_COMMENTS = {
    "alembic_version": "Alembic 数据库迁移版本记录表。",
}
ALEMBIC_COLUMN_COMMENTS = {
    "alembic_version": {
        "version_num": "当前已应用的 Alembic 迁移版本号。",
    },
}


def upgrade() -> None:
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    if dialect_name == "mysql":
        _apply_mysql_comments(connection, clear=False)
    elif dialect_name == "postgresql":
        _apply_postgresql_comments(connection, clear=False)


def downgrade() -> None:
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    if dialect_name == "mysql":
        _apply_mysql_comments(connection, clear=True)
    elif dialect_name == "postgresql":
        _apply_postgresql_comments(connection, clear=True)


def _table_comments() -> dict[str, str]:
    return {**TABLE_COMMENTS, **ALEMBIC_TABLE_COMMENTS}


def _column_comment(table_name: str, column_name: str) -> str | None:
    return (
        ALEMBIC_COLUMN_COMMENTS.get(table_name, {}).get(column_name)
        or COLUMN_COMMENTS.get(table_name, {}).get(column_name)
        or COMMON_COLUMN_COMMENTS.get(column_name)
    )


def _apply_mysql_comments(connection: Connection, *, clear: bool) -> None:
    existing_tables = set(inspect(connection).get_table_names())
    preparer = connection.dialect.identifier_preparer
    for table_name, comment in _table_comments().items():
        if table_name not in existing_tables:
            continue
        table_identifier = preparer.quote(table_name)
        table_comment = "" if clear else comment
        connection.exec_driver_sql(
            f"ALTER TABLE {table_identifier} COMMENT = {_sql_literal(table_comment)}"
        )
        rows = connection.exec_driver_sql(f"SHOW FULL COLUMNS FROM {table_identifier}").mappings()
        for row in rows:
            column_name = str(row["Field"])
            if _column_comment(table_name, column_name) is None:
                continue
            column_comment = "" if clear else _column_comment(table_name, column_name) or ""
            column_identifier = preparer.quote(column_name)
            column_definition = _mysql_column_definition(row)
            connection.exec_driver_sql(
                f"ALTER TABLE {table_identifier} MODIFY COLUMN {column_identifier} "
                f"{column_definition} COMMENT {_sql_literal(column_comment)}"
            )


def _apply_postgresql_comments(connection: Connection, *, clear: bool) -> None:
    existing_tables = set(inspect(connection).get_table_names())
    preparer = connection.dialect.identifier_preparer
    for table_name, comment in _table_comments().items():
        if table_name not in existing_tables:
            continue
        table_identifier = preparer.quote(table_name)
        table_comment = "NULL" if clear else _sql_literal(comment)
        connection.exec_driver_sql(f"COMMENT ON TABLE {table_identifier} IS {table_comment}")
        column_names = {column["name"] for column in inspect(connection).get_columns(table_name)}
        for column_name in column_names:
            comment = _column_comment(table_name, column_name)
            if comment is None:
                continue
            column_comment = "NULL" if clear else _sql_literal(comment)
            column_identifier = preparer.quote(column_name)
            connection.exec_driver_sql(
                f"COMMENT ON COLUMN {table_identifier}.{column_identifier} IS {column_comment}"
            )


def _mysql_column_definition(row: dict[str, object]) -> str:
    column_type = str(row["Type"])
    null_clause = "NULL" if row["Null"] == "YES" else "NOT NULL"
    default_clause = _mysql_default_clause(row["Default"])
    extra = str(row["Extra"] or "").strip()
    charset_clause = _mysql_charset_clause(row.get("Collation"))
    return " ".join(
        part for part in [column_type, charset_clause, null_clause, default_clause, extra] if part
    )


def _mysql_charset_clause(collation: object) -> str:
    if not collation:
        return ""
    collation_name = str(collation)
    charset = collation_name.split("_", 1)[0]
    return f"CHARACTER SET {charset} COLLATE {collation_name}"


def _mysql_default_clause(default: object) -> str:
    if default is None:
        return ""
    default_text = str(default)
    upper_default = default_text.upper()
    if upper_default.startswith("CURRENT_TIMESTAMP"):
        return f"DEFAULT {default_text}"
    return f"DEFAULT {_sql_literal(default_text)}"


def _sql_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"
