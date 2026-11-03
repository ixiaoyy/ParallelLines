from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogCategory, CatalogProject
from app.services.catalog import CatalogPublicLink, CatalogService


@pytest.mark.asyncio
async def test_public_links_preserve_visibility_order_and_skip_ratings():
    """仅在内存建两张表；核对真实筛选排序和单条查询，不连接任何配置数据库。"""
    engine = create_engine("sqlite:///:memory:")
    CatalogCategory.__table__.create(engine)
    CatalogProject.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(insert(CatalogCategory), [
            {"id": "1", "slug": "hidden", "name": "隐藏分类", "sort_order": 0, "is_visible": False},
            {"id": "2", "slug": "first", "name": "首类", "sort_order": 1, "is_visible": True},
            {"id": "10", "slug": "second", "name": "次类", "sort_order": 1, "is_visible": True},
        ])
        connection.execute(insert(CatalogProject), [
            {"id": str(id_), "category_id": str(category), "slug": f"game-{id_}",
             "name": f"游戏{id_}", "destination_url": f"https://example.invalid/{id_}",
             "description": None, "destination_kind": "external", "sort_order": order,
             "is_visible": visible}
            for id_, category, order, visible in [
                (1, 1, 0, True), (2, 2, 0, False), (10, 2, 1, True),
                (3, 2, 1, True), (4, 2, 0, True), (5, 10, 0, True),
            ]
        ])
        calls = []

        class MemorySession:
            async def execute(self, statement):
                sql = str(statement.compile(dialect=mysql.dialect()))
                assert "catalog_ratings" not in sql and "count(" not in sql.lower()
                calls.append(sql)
                return connection.execute(statement)

        service = CatalogService(cast(AsyncSession, MemorySession()), SimpleNamespace())
        links = await service.public_project_links()
        assert links == [CatalogPublicLink(f"https://example.invalid/{id_}", f"游戏{id_}", None)
                         for id_ in (4, 3, 10, 5)]
        assert len(calls) == 1
        connection.execute(CatalogProject.__table__.delete())
        assert await service.public_project_links() == []
    engine.dispose()
