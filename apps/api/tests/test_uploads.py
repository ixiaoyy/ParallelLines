import base64
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.main import create_app
from app.models.upload import Upload
from app.services.uploads import S3UploadStorage, extract_upload_references, public_storage_url
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_public_storage_url_builds_cdn_object_url() -> None:
    """Verify configured CDN bases produce stable object URLs.

    Key parameters: none. Return value is none. Side effect: none.
    """
    assert (
        public_storage_url("https://img.pingxingxian.space/", "2026/06/10.png")
        == "https://img.pingxingxian.space/2026/06/10.png"
    )


def test_extract_upload_references_accepts_api_and_configured_cdn_urls() -> None:
    """Verify attachment binding can see API URLs and configured CDN URLs.

    Key parameters: none. Return value is none. Side effect: none.
    """
    refs = extract_upload_references(
        "\n".join(
            [
                "![api](/uploads/10/content)",
                "![cdn](https://img.pingxingxian.space/2026/06/10.png)",
                "![thumb](https://img.pingxingxian.space/_thumbnails/2026/06/10.png.webp)",
            ]
        ),
        cdn_base_url="https://img.pingxingxian.space/",
    )

    assert refs.ids == ["10"]
    assert refs.storage_keys == ["2026/06/10.png"]


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


def create_upload_test_app(
    session_factory: async_sessionmaker[AsyncSession],
    upload_dir: Path,
    *,
    upload_max_bytes: int = 1024,
    settings_overrides: dict[str, object] | None = None,
):
    """Create a FastAPI test app with isolated session and upload settings.

    Key parameters are the session factory, upload directory, size limit, and
    optional settings overrides. Return value is an ASGI app. Side effect: installs
    dependency overrides on that app instance.
    """
    async def override_session():
        async with session_factory() as session:
            yield session

    settings_kwargs = {
        "environment": "test",
        "upload_storage_path": str(upload_dir),
        "upload_max_bytes": upload_max_bytes,
        "upload_max_avatar_bytes": upload_max_bytes,
    }
    if settings_overrides:
        settings_kwargs.update(settings_overrides)
    settings = Settings(**settings_kwargs)
    app = create_app()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings
    return app


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "auth": f"Bearer {data['access_token']}",
    }


@pytest.mark.asyncio
async def test_post_image_upload_attaches_and_renders_after_refresh(tmp_path: Path) -> None:
    session_factory, engine = await create_test_session()
    app = create_upload_test_app(session_factory, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "uploader")
        headers = {"Authorization": user["auth"]}
        board = await client.post(
            "/api/v1/boards",
            headers=headers,
            json={
                "slug": "uploads",
                "name": "上传测试",
                "description": "用于验证上传附件引用关系。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201

        upload = await client.post(
            "/api/v1/uploads",
            headers=headers,
            data={"kind": "post_attachment"},
            files={"file": ("diagram.png", PNG_BYTES, "image/png")},
        )
        assert upload.status_code == 201
        upload_data = upload.json()["data"]
        assert upload_data["is_image"] is True

        topic = await client.post(
            "/api/v1/boards/uploads/topics",
            headers=headers,
            json={
                "title": "上传图片刷新后仍然可展示",
                "raw_md": f"复现截图：![diagram]({upload_data['url']})",
                "tags": ["uploads"],
            },
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        posts = await client.get(f"/api/v1/topics/{topic_id}/posts")
        assert posts.status_code == 200
        first_post = posts.json()["data"][0]
        assert '<img src="/uploads/' in first_post["cooked_html"]
        assert 'alt="diagram"' in first_post["cooked_html"]

        content = await client.get(f"/api/v1/uploads/{upload_data['id']}/content")
        assert content.status_code == 200
        assert "max-age=86400" in content.headers["cache-control"]
        assert content.headers["content-type"].startswith("image/png")
        assert content.content == PNG_BYTES

        thumbnail = await client.get(f"/api/v1/uploads/{upload_data['id']}/thumbnail")
        assert thumbnail.status_code == 200
        assert "max-age=86400" in thumbnail.headers["cache-control"]
        assert thumbnail.headers["content-type"].startswith("image/webp")
        assert thumbnail.content[:4] == b"RIFF"
        assert thumbnail.content[8:12] == b"WEBP"

    async with session_factory() as session:
        saved_upload = await session.get(Upload, upload_data["id"])
        assert saved_upload is not None
        assert saved_upload.status == "attached"
        assert saved_upload.board_id == board.json()["data"]["id"]
        assert saved_upload.topic_id == topic_id
        assert saved_upload.post_id == first_post["id"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_s3_backend_stores_and_serves_upload_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_objects: dict[str, tuple[bytes, str]] = {}

    def fake_write(self: S3UploadStorage, key: str, content: bytes, media_type: str) -> None:
        """Store one fake S3 object in memory for upload flow assertions.

        Key parameters mirror `S3UploadStorage.write`. Return value is none. Side
        effect: mutates the in-memory object map used by this test.
        """
        stored_objects[key] = (content, media_type)

    def fake_read(self: S3UploadStorage, key: str) -> bytes:
        """Read one fake S3 object from memory for API response assertions.

        Key parameter is the storage key. Return value is object bytes. Side effect:
        raises the same not-found error shape as real storage when absent.
        """
        if key not in stored_objects:
            raise NotFoundError("upload_not_found", "Upload not found")
        return stored_objects[key][0]

    def fake_delete(self: S3UploadStorage, key: str) -> None:
        """Delete one fake S3 object from memory for cleanup compatibility.

        Key parameter is the storage key. Return value is none. Side effect: removes
        the object from the in-memory map when present.
        """
        stored_objects.pop(key, None)

    monkeypatch.setattr(S3UploadStorage, "write", fake_write)
    monkeypatch.setattr(S3UploadStorage, "read", fake_read)
    monkeypatch.setattr(S3UploadStorage, "delete", fake_delete)

    session_factory, engine = await create_test_session()
    app = create_upload_test_app(
        session_factory,
        tmp_path,
        settings_overrides={
            "upload_storage_backend": "s3",
            "upload_s3_bucket": "parallel-lines-test",
            "upload_s3_region": "auto",
            "upload_s3_endpoint_url": "https://example-account.r2.cloudflarestorage.com",
            "upload_s3_access_key_id": "test-access-key",
            "upload_s3_secret_access_key": "test-secret-key",
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "r2uploader")
        headers = {"Authorization": user["auth"]}

        upload = await client.post(
            "/api/v1/uploads",
            headers=headers,
            data={"kind": "post_attachment"},
            files={"file": ("r2.png", PNG_BYTES, "image/png")},
        )
        assert upload.status_code == 201
        upload_data = upload.json()["data"]

        content = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/content",
            headers=headers,
        )
        assert content.status_code == 200
        assert content.headers["content-type"].startswith("image/png")
        assert content.content == PNG_BYTES

        thumbnail = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/thumbnail",
            headers=headers,
        )
        assert thumbnail.status_code == 200
        assert thumbnail.headers["content-type"].startswith("image/webp")
        assert thumbnail.content[:4] == b"RIFF"
        assert thumbnail.content[8:12] == b"WEBP"

    async with session_factory() as session:
        saved_upload = await session.get(Upload, upload_data["id"])
        assert saved_upload is not None
        assert saved_upload.storage_backend == "s3"
        assert re.fullmatch(r"\d{4}/\d{2}/\d+\.png", saved_upload.storage_key)
        assert stored_objects[saved_upload.storage_key] == (PNG_BYTES, "image/png")
        thumbnail_key = f"_thumbnails/{saved_upload.storage_key}.webp"
        assert thumbnail_key in stored_objects

    await engine.dispose()


@pytest.mark.asyncio
async def test_upload_validation_rejects_disallowed_mismatch_and_size(tmp_path: Path) -> None:
    session_factory, engine = await create_test_session()
    app = create_upload_test_app(session_factory, tmp_path, upload_max_bytes=4)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "uploadguard")
        headers = {"Authorization": user["auth"]}

        executable = await client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("bad.js", b"js", "text/javascript")},
        )
        assert executable.status_code == 422
        assert executable.json()["error"]["code"] == "upload_type_not_allowed"

        mismatch = await client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("note.txt", b"safe", "image/png")},
        )
        assert mismatch.status_code == 422
        assert mismatch.json()["error"]["code"] == "upload_mime_mismatch"

        too_large = await client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("note.txt", b"12345", "text/plain")},
        )
        assert too_large.status_code == 422
        assert too_large.json()["error"]["code"] == "upload_too_large"

    await engine.dispose()


@pytest.mark.asyncio
async def test_avatar_upload_updates_current_user_and_public_profile(tmp_path: Path) -> None:
    session_factory, engine = await create_test_session()
    app = create_upload_test_app(session_factory, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "avataruser")
        headers = {"Authorization": user["auth"]}
        avatar = await client.post(
            "/api/v1/uploads/avatar",
            headers=headers,
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )
        assert avatar.status_code == 200
        current_user = avatar.json()["data"]
        assert current_user["avatar_url"].startswith("/uploads/")

        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["data"]["avatar_url"] == current_user["avatar_url"]

        profile = await client.get("/api/v1/users/avataruser")
        assert profile.status_code == 200
        assert profile.json()["data"]["avatar_url"] == current_user["avatar_url"]

        board = await client.post(
            "/api/v1/boards",
            headers=headers,
            json={
                "slug": "avatar-board",
                "name": "头像版块",
                "description": "验证主题和楼层列表会返回作者头像。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201

        topic = await client.post(
            "/api/v1/boards/avatar-board/topics",
            headers=headers,
            json={
                "title": "头像应该在列表中显示",
                "raw_md": "创建主题后，列表需要拿到作者头像。",
                "tags": ["avatar"],
            },
        )
        assert topic.status_code == 201
        topic_data = topic.json()["data"]
        assert topic_data["author_avatar_url"] == current_user["avatar_url"]

        topics = await client.get("/api/v1/topics")
        assert topics.status_code == 200
        assert topics.json()["data"][0]["author_avatar_url"] == current_user["avatar_url"]

        posts = await client.get(f"/api/v1/topics/{topic_data['id']}/posts", headers=headers)
        assert posts.status_code == 200
        assert posts.json()["data"][0]["author_avatar_url"] == current_user["avatar_url"]

        content = await client.get(f"/api/v1{current_user['avatar_url']}")
        assert content.status_code == 200
        assert content.content == PNG_BYTES

    avatar_upload_id = current_user["avatar_url"].split("/")[2]
    async with session_factory() as session:
        saved_avatar = await session.get(Upload, avatar_upload_id)
        assert saved_avatar is not None
        assert re.fullmatch(r"\d{4}/\d{2}/\d+\.png", saved_avatar.storage_key)
        assert (tmp_path / saved_avatar.storage_key).is_file()

    await engine.dispose()


@pytest.mark.asyncio
async def test_private_board_attachment_requires_board_access(tmp_path: Path) -> None:
    session_factory, engine = await create_test_session()
    app = create_upload_test_app(session_factory, tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "privateowner")
        invitee = await register_user(client, "privateinvitee")
        stranger = await register_user(client, "privatestranger")
        owner_headers = {"Authorization": owner["auth"]}
        invitee_headers = {"Authorization": invitee["auth"]}
        stranger_headers = {"Authorization": stranger["auth"]}

        board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "private-uploads",
                "name": "私密附件版块",
                "description": "验证附件不会泄漏给无权限用户。",
                "color": "#409EFF",
                "visibility": "private",
            },
        )
        assert board.status_code == 201
        board_id = board.json()["data"]["id"]

        upload = await client.post(
            "/api/v1/uploads",
            headers=owner_headers,
            data={"kind": "post_attachment"},
            files={"file": ("secret.png", PNG_BYTES, "image/png")},
        )
        assert upload.status_code == 201
        upload_data = upload.json()["data"]

        topic = await client.post(
            "/api/v1/boards/private-uploads/topics",
            headers=owner_headers,
            json={
                "title": "私密附件只有成员可读",
                "raw_md": f"内部截图：![secret]({upload_data['url']})",
                "tags": ["private"],
            },
        )
        assert topic.status_code == 201

        anonymous_content = await client.get(f"/api/v1/uploads/{upload_data['id']}/content")
        assert anonymous_content.status_code == 404
        anonymous_thumbnail = await client.get(f"/api/v1/uploads/{upload_data['id']}/thumbnail")
        assert anonymous_thumbnail.status_code == 404
        stranger_content = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/content",
            headers=stranger_headers,
        )
        assert stranger_content.status_code == 404
        stranger_thumbnail = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/thumbnail",
            headers=stranger_headers,
        )
        assert stranger_thumbnail.status_code == 404
        owner_content = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/content",
            headers=owner_headers,
        )
        assert owner_content.status_code == 200
        owner_thumbnail = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/thumbnail",
            headers=owner_headers,
        )
        assert owner_thumbnail.status_code == 200

        invite = await client.post(
            "/api/v1/invites",
            headers=owner_headers,
            json={"board_id": board_id, "username": "privateinvitee"},
        )
        assert invite.status_code == 201

        before_accept = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/content",
            headers=invitee_headers,
        )
        assert before_accept.status_code == 404

        accepted = await client.put(
            f"/api/v1/invites/{invite.json()['data']['id']}/accept",
            headers=invitee_headers,
        )
        assert accepted.status_code == 200
        after_accept = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/content",
            headers=invitee_headers,
        )
        assert after_accept.status_code == 200
        assert after_accept.content == PNG_BYTES
        invitee_thumbnail = await client.get(
            f"/api/v1/uploads/{upload_data['id']}/thumbnail",
            headers=invitee_headers,
        )
        assert invitee_thumbnail.status_code == 200

    await engine.dispose()
