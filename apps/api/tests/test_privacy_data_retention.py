import io
import json
from datetime import timedelta
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import Settings, get_settings
from app.db.base import Base, utcnow
from app.main import create_app
from app.models.background_job import BackgroundJob
from app.models.user import User, UserSecurityToken
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "email": data["user"]["email"],
        "auth": f"Bearer {data['access_token']}",
    }


async def promote_admin(session_factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = "admin"
        await session.commit()


def zip_json(content: bytes, name: str) -> object:
    with ZipFile(io.BytesIO(content)) as archive:
        return json.loads(archive.read(name))


async def create_public_topic(client: AsyncClient, auth: str) -> str:
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": "privacy-roadmap",
            "name": "Privacy",
            "description": "Privacy test board",
            "color": "#3B82F6",
        },
    )
    assert board.status_code == 201
    topic = await client.post(
        "/api/v1/boards/privacy-roadmap/topics",
        headers={"Authorization": auth},
        json={"title": "Privacy topic", "raw_md": "Public content remains readable."},
    )
    assert topic.status_code == 201
    return topic.json()["data"]["id"]


@pytest.mark.asyncio
async def test_admin_anonymize_revokes_private_data_and_keeps_topic_readable(tmp_path) -> None:
    session_factory, engine = await create_test_session()
    settings = Settings(
        backup_storage_path=str(tmp_path / "backups"),
        upload_storage_path=str(tmp_path / "uploads"),
    )

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_user(client, "privacyadmin")
        author = await register_user(client, "privacyauthor")
        await promote_admin(session_factory, admin["id"])
        topic_id = await create_public_topic(client, author["auth"])

        anonymized = await client.post(
            f"/api/v1/admin/users/{author['id']}/anonymize",
            headers={"Authorization": admin["auth"]},
            json={"reason": "user requested erasure"},
        )
        assert anonymized.status_code == 200
        data = anonymized.json()["data"]
        assert data["status"] == "deleted"
        assert data["anonymized"] is True
        assert data["username"] != "privacyauthor"
        assert data["email"] != author["email"]
        assert data["email"].endswith("@deleted.invalid")
        assert data["revoked_sessions"] >= 1

        old_profile = await client.get("/api/v1/users/privacyauthor")
        assert old_profile.status_code == 404

        topic_after = await client.get(f"/api/v1/topics/{topic_id}")
        assert topic_after.status_code == 200
        topic_data = topic_after.json()["data"]
        assert topic_data["author_name"] == data["username"]
        assert b"privacyauthor" not in topic_after.content

        old_token_export = await client.get(
            "/api/v1/users/me/export",
            headers={"Authorization": author["auth"]},
        )
        assert old_token_export.status_code == 401

        async with session_factory() as session:
            user = await session.get(User, author["id"])
            assert user is not None
            assert user.username == data["username"]
            assert user.email == data["email"]
            assert user.two_factor_enabled is False
            assert user.two_factor_secret is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_privacy_exports_redact_token_hashes_and_job_secrets(tmp_path) -> None:
    session_factory, engine = await create_test_session()
    settings = Settings(
        backup_storage_path=str(tmp_path / "backups"),
        upload_storage_path=str(tmp_path / "uploads"),
    )

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_user(client, "redactadmin")
        member = await register_user(client, "redactmember")
        await promote_admin(session_factory, admin["id"])

        async with session_factory() as session:
            now = utcnow()
            session.add(
                UserSecurityToken(
                    user_id=member["id"],
                    purpose="password_reset",
                    token_hash="raw-sensitive-token-hash",
                    email=member["email"],
                    sent_at=now,
                    expires_at=now + timedelta(minutes=30),
                )
            )
            session.add(
                BackgroundJob(
                    queue="mail",
                    task_name="send_email",
                    payload={"secret": "raw-mail-secret", "token_hash": "raw-payload-hash"},
                    status="queued",
                    idempotency_key="email:password_reset:raw-idempotency-hash",
                    priority=20,
                    run_at=now,
                    attempts=0,
                    max_attempts=5,
                )
            )
            await session.commit()

        user_export = await client.get(
            "/api/v1/users/me/export",
            headers={"Authorization": member["auth"]},
        )
        assert user_export.status_code == 200
        assert b"raw-sensitive-token-hash" not in user_export.content
        assert b"raw-mail-secret" not in user_export.content

        site_export = await client.get(
            "/api/v1/admin/exports/site",
            headers={"Authorization": admin["auth"]},
        )
        assert site_export.status_code == 200
        tokens = zip_json(site_export.content, "database/user_security_tokens.json")
        assert {row["token_hash"] for row in tokens} == {"***redacted***"}
        jobs = zip_json(site_export.content, "database/background_jobs.json")
        assert "***redacted***" in {row["idempotency_key"] for row in jobs}
        assert b"raw-sensitive-token-hash" not in site_export.content
        assert b"raw-mail-secret" not in site_export.content
        assert b"raw-idempotency-hash" not in site_export.content
        assert b"raw-payload-hash" not in site_export.content

    await engine.dispose()
