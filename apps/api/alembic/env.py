from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.models import (  # noqa: F401
    AuditLog,
    BackgroundJob,
    BackgroundJobLog,
    Board,
    BoardMember,
    Bookmark,
    EmailDeliveryEvent,
    EmailVerificationCode,
    Flag,
    InboundEmail,
    Notification,
    Post,
    PostRevision,
    RateLimitEvent,
    Reaction,
    ScreenedRule,
    SiteSetting,
    SpamAction,
    Tag,
    Topic,
    TopicRead,
    User,
    UserEmailPreference,
    UserRecoveryCode,
    UserSecurityToken,
    UserSession,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    # Alembic's default version_num is VARCHAR(32). Our descriptive revision IDs
    # are longer, and MySQL enforces the length strictly.
    context.get_context()._version.c.version_num.type.length = 128
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
