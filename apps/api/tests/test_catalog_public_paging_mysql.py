"""使用既有 CI MySQL 测试库验证公开分页入口；本地不运行此测试。"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.catalog import CatalogCategory, CatalogProject
from app.services.catalog_cache import invalidate_public_catalog_cache
from tests.helpers import get_test_database_url, reset_test_database


@pytest.mark.asyncio
async def test_public_category_pages_execute_on_mysql_without_or_with_priority() -> None:
    """真实 asyncmy GET 首批及游标后续批；空排序与 CASE 排序均不能使用列序号。"""

    engine = create_async_engine(get_test_database_url())
    invalidate_public_catalog_cache()
    try:
        async with engine.begin() as connection:
            await reset_test_database(connection)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        created = datetime(2026, 11, 4, tzinfo=UTC)
        async with sessions() as session:
            session.add_all(
                [
                    CatalogCategory(id="1", slug="cards", name="卡牌"),
                    CatalogCategory(id="2", slug="hidden", name="隐藏", is_visible=False),
                ]
            )
            await session.flush()
            for project_id in ("2", "5", "10", "20", "30", "40", "50", "60", "70"):
                session.add(
                    CatalogProject(
                        id=project_id,
                        category_id="2" if project_id == "60" else "1",
                        slug=f"game-{project_id}",
                        name=f"游戏 {project_id}",
                        destination_url=f"https://example.org/{project_id}",
                        destination_kind="external",
                        is_visible=project_id != "70",
                        created_at=created + timedelta(days=1) if project_id == "50" else created,
                        updated_at=created,
                    )
                )
            await session.commit()

        async def override_session():
            async with sessions() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_session] = override_session
        path = "/api/v1/catalog/categories/cards/projects"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for priorities, expected in [
                (None, ["50", "40", "30", "20", "10", "5", "2"]),
                ("game-2,game-5", ["50", "2", "5", "40", "30", "20", "10"]),
            ]:
                cursor, ids = None, []
                # 七个可见项目，每批三张，固定三批验证到终点，避免测试无限轮询。
                for index in range(3):
                    params = {"limit": "3"}
                    if priorities is not None:
                        params["priority_slugs"] = priorities
                    if cursor is not None:
                        params["cursor"] = cursor
                    response = await client.get(path, params=params)
                    assert response.status_code == 200
                    page = response.json()["data"]
                    assert page["total"] == 7
                    assert page["category_slug"] == "cards"
                    assert all(project["my_score"] is None for project in page["projects"])
                    assert all(project["category_slug"] == "cards" for project in page["projects"])
                    ids.extend(project["id"] for project in page["projects"])
                    next_cursor = page["next_cursor"]
                    assert next_cursor != cursor if index < 2 else next_cursor is None
                    assert page["has_more"] == (index < 2)
                    cursor = next_cursor
                assert ids == expected
                assert len(ids) == len(set(ids))
            hidden = await client.get("/api/v1/catalog/categories/hidden/projects?limit=3")
            assert hidden.status_code == 404
    finally:
        invalidate_public_catalog_cache()
        await engine.dispose()
