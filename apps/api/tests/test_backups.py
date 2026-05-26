import io
import json
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.backup import BackupArtifact
from app.models.user import User
from app.services.background_jobs import BackgroundJobService
from app.services.backups import BackupService
from tests.helpers import (
    drain_background_jobs,
    get_test_database_url,
    register_and_verify_user,
    reset_test_database,
)


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
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


@pytest.mark.asyncio
async def test_admin_backup_lifecycle_download_and_restore_validation(tmp_path) -> None:
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
        admin = await register_user(client, "backupadmin")
        member = await register_user(client, "backupmember")
        await promote_admin(session_factory, admin["id"])

        forbidden = await client.post(
            "/api/v1/admin/backups",
            headers={"Authorization": member["auth"]},
            json={"include_uploads": False},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "admin_required"

        created = await client.post(
            "/api/v1/admin/backups",
            headers={"Authorization": admin["auth"]},
            json={"include_uploads": False},
        )
        assert created.status_code == 200
        backup_id = created.json()["data"]["id"]
        assert created.json()["data"]["status"] == "queued"

        await drain_background_jobs(session_factory, settings=settings)

        backup = await client.get(
            f"/api/v1/admin/backups/{backup_id}",
            headers={"Authorization": admin["auth"]},
        )
        assert backup.status_code == 200
        backup_data = backup.json()["data"]
        assert backup_data["status"] == "succeeded"
        assert backup_data["byte_size"] > 0
        assert len(backup_data["sha256"]) == 64

        downloaded = await client.get(
            f"/api/v1/admin/backups/{backup_id}/download",
            headers={"Authorization": admin["auth"]},
        )
        assert downloaded.status_code == 200
        assert downloaded.headers["X-Backup-SHA256"] == backup_data["sha256"]
        metadata = zip_json(downloaded.content, "metadata.json")
        assert metadata["kind"] == "site_backup"
        users = zip_json(downloaded.content, "database/users.json")
        assert users[0]["hashed_password"] == "***redacted***"
        assert b"strong-pass-123" not in downloaded.content

        bad_restore = await client.post(
            f"/api/v1/admin/backups/{backup_id}/restore",
            headers={"Authorization": admin["auth"]},
            json={"confirmation": "restore please"},
        )
        assert bad_restore.status_code == 422
        assert bad_restore.json()["error"]["code"] == "invalid_restore_confirmation"

        restore = await client.post(
            f"/api/v1/admin/backups/{backup_id}/restore",
            headers={"Authorization": admin["auth"]},
            json={"confirmation": f"RESTORE {backup_id}"},
        )
        assert restore.status_code == 200
        assert restore.json()["data"]["verified_checksum"] is True
        assert restore.json()["data"]["restore_supported"] is False

        deleted = await client.delete(
            f"/api/v1/admin/backups/{backup_id}",
            headers={"Authorization": admin["auth"]},
        )
        assert deleted.status_code == 200
        assert deleted.json()["data"]["status"] == "deleted"

    await engine.dispose()


@pytest.mark.asyncio
async def test_user_and_site_exports_redact_secrets(tmp_path) -> None:
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
        admin = await register_user(client, "exportadmin")
        member = await register_user(client, "exportmember")
        await promote_admin(session_factory, admin["id"])

        user_export = await client.get(
            "/api/v1/users/me/export",
            headers={"Authorization": member["auth"]},
        )
        assert user_export.status_code == 200
        profile = zip_json(user_export.content, "profile.json")
        assert profile["email"] == member["email"]
        assert "hashed_password" not in profile
        assert b"strong-pass-123" not in user_export.content

        forbidden_site_export = await client.get(
            "/api/v1/admin/exports/site",
            headers={"Authorization": member["auth"]},
        )
        assert forbidden_site_export.status_code == 403

        site_export = await client.get(
            "/api/v1/admin/exports/site",
            headers={"Authorization": admin["auth"]},
        )
        assert site_export.status_code == 200
        users = zip_json(site_export.content, "database/users.json")
        assert {row["hashed_password"] for row in users} == {"***redacted***"}
        assert b"strong-pass-123" not in site_export.content

    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_backup_records_artifact_status_and_job_log(tmp_path) -> None:
    session_factory, engine = await create_test_session()
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("blocks mkdir")
    settings = Settings(backup_storage_path=str(blocking_file))

    async with session_factory() as session:
        user = User(
            username="failedbackupadmin",
            email="failedbackupadmin@example.com",
            hashed_password="hashed",
            role="admin",
            status="active",
        )
        session.add(user)
        await session.flush()
        artifact = BackupArtifact(
            kind="site_backup",
            status="queued",
            filename="will-fail.zip",
            storage_backend="local",
            artifact_metadata={"include_uploads": False},
            created_by_id=user.id,
        )
        session.add(artifact)
        await session.flush()
        backup_id = artifact.id

        service = BackgroundJobService(session)
        job = await service.enqueue(
            "failing_backup",
            payload={"backup_id": backup_id},
            max_attempts=1,
        )

        async def failing_handler(
            handler_session: AsyncSession,
            payload: dict[str, object],
        ) -> dict[str, object]:
            return await BackupService(handler_session, settings).run_site_backup(
                str(payload["backup_id"])
            )

        completed = await service.run_next(
            {"failing_backup": failing_handler},
            worker_id="test-worker",
        )
        assert completed is not None
        assert completed.status == "dead"
        logs = await service.list_logs(job.id)
        assert [log.event for log in logs] == ["enqueued", "started", "dead"]

        failed_artifact = await session.get(BackupArtifact, backup_id)
        assert failed_artifact is not None
        assert failed_artifact.status == "failed"
        assert failed_artifact.failure_reason

    await engine.dispose()
