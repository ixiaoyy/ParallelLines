import os

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.workers.background_jobs import run_once

DEFAULT_TEST_DATABASE_URL = (
    "mysql+asyncmy://root:root@127.0.0.1:3306/parallellines_test?charset=utf8mb4"
)


def get_test_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


async def reset_test_database(conn: AsyncConnection) -> None:
    uses_foreign_key_checks = conn.dialect.name in {"mysql", "mariadb"}
    if uses_foreign_key_checks:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        await conn.run_sync(Base.metadata.drop_all)
    finally:
        if uses_foreign_key_checks:
            await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    await conn.run_sync(Base.metadata.create_all)


async def register_and_verify_user(
    client: AsyncClient,
    username: str,
    *,
    email: str | None = None,
    password: str = "strong-pass-123",
) -> dict[str, str]:
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
    )
    assert register.status_code == 201
    register_data = register.json()["data"]
    code = register_data["dev_verification_code"]
    assert code

    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_data["email"], "code": code},
    )
    assert verify.status_code == 200
    return verify.json()["data"]


async def drain_background_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    settings: Settings | None = None,
    max_iterations: int = 10,
) -> int:
    processed_total = 0
    for _ in range(max_iterations):
        processed_count = await run_once(
            session_factory=session_factory,
            settings=settings,
            enqueue_scheduled=False,
        )
        processed_total += processed_count
        if processed_count == 0:
            break
    return processed_total
