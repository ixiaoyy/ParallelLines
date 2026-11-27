from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, id_column_type


class UserWorkspaceConfig(Base):
    """每个主站账号的一份云配置；对已有记录的写入须匹配 revision。"""

    __tablename__ = "user_workspace_configs"
    __table_args__ = (
        sa.CheckConstraint("schema_version >= 1", name="ck_user_workspace_configs_schema"),
        sa.CheckConstraint("revision >= 1", name="ck_user_workspace_configs_revision"),
        sa.CheckConstraint(
            "UPPER(JSON_TYPE(config_json)) = 'OBJECT'",
            name="ck_user_workspace_configs_object",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        sa.ForeignKey("users.id", name="fk_user_workspace_configs_user", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    schema_version: Mapped[int] = mapped_column(sa.SmallInteger(), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(sa.JSON(none_as_null=True), nullable=False)
    revision: Mapped[int] = mapped_column(
        sa.BigInteger(), nullable=False, server_default=sa.text("1")
    )
    created_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
