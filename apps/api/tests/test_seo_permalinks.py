import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.mark.asyncio
async def test_sitemap_filters_private_content_and_legacy_redirects() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        member = await register_and_verify_user(client, "seomember")
        auth_headers = {"Authorization": f"Bearer {member['access_token']}"}

        public_board = await client.post(
            "/api/v1/boards",
            headers=auth_headers,
            json={
                "slug": "seo-public",
                "name": "SEO Public",
                "description": "Public board for sitemap",
                "visibility": "public",
            },
        )
        assert public_board.status_code == 201
        private_board = await client.post(
            "/api/v1/boards",
            headers=auth_headers,
            json={
                "slug": "seo-private",
                "name": "SEO Private",
                "description": "Private board excluded from sitemap",
                "visibility": "private",
            },
        )
        assert private_board.status_code == 201

        public_topic = await client.post(
            "/api/v1/boards/seo-public/topics",
            headers=auth_headers,
            json={
                "title": "Public sitemap topic",
                "raw_md": "This public topic should be indexed and shared.",
                "tags": ["seo"],
            },
        )
        assert public_topic.status_code == 201
        private_topic = await client.post(
            "/api/v1/boards/seo-private/topics",
            headers=auth_headers,
            json={
                "title": "Private sitemap topic",
                "raw_md": "This private topic must not be indexed.",
                "tags": ["secret"],
            },
        )
        assert private_topic.status_code == 201

        sitemap = await client.get("/sitemap.xml")
        assert sitemap.status_code == 200
        assert sitemap.headers["x-parallellines-cache"] == "miss"
        body = sitemap.text
        public_topic_data = public_topic.json()["data"]
        private_topic_data = private_topic.json()["data"]
        assert "/b/seo-public" in body
        assert f"/topics/{public_topic_data['id']}/{public_topic_data['slug']}" in body
        assert "/b/seo-private" not in body
        assert f"/topics/{private_topic_data['id']}/{private_topic_data['slug']}" not in body

        cached_sitemap = await client.get("/sitemap.xml")
        assert cached_sitemap.status_code == 200
        assert cached_sitemap.headers["x-parallellines-cache"] == "hit"
        assert cached_sitemap.text == body

        next_public_topic = await client.post(
            "/api/v1/boards/seo-public/topics",
            headers=auth_headers,
            json={
                "title": "Public sitemap cache refresh topic",
                "raw_md": "Publishing a new topic should invalidate cached sitemap XML.",
                "tags": ["seo"],
            },
        )
        assert next_public_topic.status_code == 201
        refreshed_sitemap = await client.get("/sitemap.xml")
        assert refreshed_sitemap.status_code == 200
        assert refreshed_sitemap.headers["x-parallellines-cache"] == "miss"
        next_topic_data = next_public_topic.json()["data"]
        next_topic_path = f"/topics/{next_topic_data['id']}/{next_topic_data['slug']}"
        assert next_topic_path in refreshed_sitemap.text

        robots = await client.get("/robots.txt")
        assert robots.status_code == 200
        assert "Sitemap: http://test/sitemap.xml" in robots.text

        topic_data = public_topic_data
        legacy = await client.get(f"/t/old-slug/{topic_data['id']}", follow_redirects=False)
        assert legacy.status_code == 301
        assert legacy.headers["location"] == (
            f"http://test/topics/{topic_data['id']}/{topic_data['slug']}"
        )

        private_legacy = await client.get(
            f"/t/old-slug/{private_topic.json()['data']['id']}",
            follow_redirects=False,
        )
        assert private_legacy.status_code == 404

        meta = await client.get(f"/api/v1/seo/meta?path=/topics/{topic_data['id']}/old")
        assert meta.status_code == 200
        meta_data = meta.json()["data"]
        assert meta_data["canonical_url"] == (
            f"http://test/topics/{topic_data['id']}/{topic_data['slug']}"
        )
        assert meta_data["og_type"] == "article"
        assert "Public sitemap topic" in meta_data["title"]

    await engine.dispose()
