"""独立 unittest：真实内存 SQLite SQL 和 ASGI 入口，不连接项目配置数据库。"""

from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.catalog import admin_router, router
from app.api.v1.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.db.base import Base
from app.db.session import get_session
from app.models.catalog import CatalogCategory, CatalogProject, CatalogRating, CatalogSubmission
from app.models.catalog_ai_rating import (
    AiAssessmentDimension,
    AiAssessmentHumanReview,
    AiGameAssessment,
    AiRatingBatch,
    AiRatingRule,
    AiRatingWeightScheme,
)
from app.schemas.catalog import (
    CatalogAiRatingResponse,
    CatalogCategoryCreateRequest,
    CatalogCategoryUpdateRequest,
    CatalogProjectCreateRequest,
    CatalogProjectUpdateRequest,
)
from app.services.catalog import CatalogService, parse_catalog_slug_list
from app.services.catalog_ai_ratings import CatalogAiRatingService
from app.services.catalog_cache import (
    invalidate_public_catalog_cache,
    read_public_catalog_cache,
    store_public_catalog_cache,
)

NOW = datetime(2026, 11, 4, tzinfo=UTC)
SETTINGS = SimpleNamespace(
    catalog_rating_ip_secret="offline-public-catalog-key-over-32-characters",
    jwt_secret_key="unused-offline-key-over-32-characters",
)


def visitor_request(ip="192.0.2.1"):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/catalog",
            "headers": [(b"x-real-ip", ip.encode())],
            "client": (ip, 1234),
        }
    )


class SQLiteBridge:
    """同步 SQLite 的异步适配；记录真实语句，测试用 BIGINT ID 显式分配。"""

    def __init__(self, session):
        self.session = session
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.session.execute(statement)

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.session.scalar(statement)

    async def scalars(self, statement):
        self.statements.append(statement)
        return self.session.scalars(statement)

    async def get(self, entity, key):
        return self.session.get(entity, key)

    def add(self, entity):
        if entity.id is None:
            with self.session.no_autoflush:
                current = self.session.scalar(sa.select(sa.func.max(type(entity).id)))
            entity.id = str(int(current or 0) + 1)
        self.session.add(entity)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    @asynccontextmanager
    async def begin_nested(self):
        with self.session.begin_nested():
            yield


class CatalogPublicPagingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        invalidate_public_catalog_cache()
        self.engine = sa.create_engine("sqlite://")
        Base.metadata.create_all(
            self.engine,
            tables=[
                CatalogCategory.__table__,
                CatalogProject.__table__,
                CatalogRating.__table__,
                CatalogSubmission.__table__,
                AiRatingRule.__table__,
                AiRatingWeightScheme.__table__,
                AiRatingBatch.__table__,
                AiGameAssessment.__table__,
                AiAssessmentDimension.__table__,
                AiAssessmentHumanReview.__table__,
            ],
        )
        self.session = Session(self.engine, expire_on_commit=False)
        self.bridge = SQLiteBridge(self.session)
        self.admin = SimpleNamespace(id="99", role="admin")
        self.session.add_all(
            [
                CatalogCategory(id="1", slug="cards", name="卡牌", sort_order=5),
                CatalogCategory(id="2", slug="hidden", name="隐藏", is_visible=False),
                CatalogCategory(id="3", slug="other", name="其他", sort_order=0),
                CatalogCategory(id="4", slug="empty", name="空分类", sort_order=10),
            ]
        )
        for project_id, category, visible, created in [
            ("1", "1", True, NOW),
            ("2", "1", True, NOW),
            ("3", "1", True, NOW),
            ("10", "1", True, NOW),
            ("4", "1", True, NOW + timedelta(days=1)),
            ("5", "1", False, NOW),
            ("6", "3", True, NOW),
            ("7", "2", True, NOW),
            *[(str(index), "1", True, NOW - timedelta(days=1)) for index in range(11, 19)],
        ]:
            self.session.add(
                CatalogProject(
                    id=project_id,
                    category_id=category,
                    slug=f"game-{project_id}",
                    name=f"游戏 {project_id}",
                    destination_url=f"https://example.org/{project_id}",
                    destination_kind="external",
                    is_visible=visible,
                    created_at=created,
                    updated_at=created,
                )
            )
        digest = CatalogService(None, SETTINGS)._ip_digest(visitor_request(), required=True)
        self.session.add(CatalogRating(id="1", project_id="1", ip_digest=digest, score=5))
        self.session.commit()
        self.service = CatalogService(self.bridge, SETTINGS)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.include_router(admin_router, prefix="/api/v1")

        async def isolated_session():
            yield self.bridge

        @app.exception_handler(AppError)
        async def domain_error(_request, error):
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": {"code": error.code, "message": error.message},
                },
            )

        app.dependency_overrides[get_session] = isolated_session
        app.dependency_overrides[get_settings] = lambda: SETTINGS
        app.dependency_overrides[get_current_user] = lambda: self.admin
        self.client = AsyncClient(
            transport=ASGITransport(app, raise_app_exceptions=False),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.session.close()
        self.engine.dispose()
        invalidate_public_catalog_cache()

    async def test_sql_limit_cursor_order_and_no_missing_or_duplicate_rows(self):
        ids, cursor = [], None
        while True:
            page = await self.service.public_category_projects(
                "cards",
                limit=2,
                cursor=cursor,
                priority_slugs=("game-2", "game-1"),
            )
            self.assertEqual(page.total, 13)
            self.assertLessEqual(len(page.projects), 2)
            ids.extend(project.id for project in page.projects)
            cursor = page.next_cursor
            if not page.has_more:
                self.assertIsNone(cursor)
                break
        self.assertEqual(
            ids, ["4", "2", "1", "10", "3", "18", "17", "16", "15", "14", "13", "12", "11"]
        )
        self.assertEqual(len(ids), len(set(ids)))
        full_reads = [
            str(statement.compile(compile_kwargs={"literal_binds": True}))
            for statement in self.bridge.statements
            if "catalog_projects.description" in str(statement)
        ]
        self.assertEqual(len(full_reads), 7)
        self.assertTrue(all("LIMIT 3" in query for query in full_reads))
        self.assertIn("catalog_projects.created_at <", full_reads[1])
        self.assertIn("catalog_projects.id <", full_reads[1])

    async def test_cursor_scope_bounds_and_visibility(self):
        first = await self.service.public_category_projects("cards", limit=1)
        for slug, cursor, priorities in [
            ("other", first.next_cursor, ()),
            ("cards", first.next_cursor, ("game-1",)),
            ("cards", "not-a-cursor", ()),
            ("cards", "x" * 2049, ()),
        ]:
            with self.subTest(slug=slug, priorities=priorities):
                with self.assertRaises(ValidationError):
                    await self.service.public_category_projects(
                        slug,
                        limit=2,
                        cursor=cursor,
                        priority_slugs=priorities,
                    )
        for slug in ("hidden", "missing"):
            with self.assertRaises(NotFoundError):
                await self.service.public_category_projects(slug, limit=2)
        empty = await self.service.public_category_projects("empty", limit=2)
        self.assertEqual(empty.total, 0)
        self.assertEqual(empty.projects, [])
        for value in (0, 61):
            response = await self.client.get(
                f"/api/v1/catalog/categories/cards/projects?limit={value}"
            )
            self.assertEqual(response.status_code, 422)

    async def test_overview_column_metadata_empty_candidate_and_six_card_bound(self):
        empty = await self.service.public_overview(hero_slugs=())
        self.assertEqual(
            [(item.slug, item.total) for item in empty.categories],
            [
                ("other", 1),
                ("cards", 13),
                ("empty", 0),
            ],
        )
        self.assertEqual(empty.hero.projects, [])
        self.assertEqual(len(self.bridge.statements), 1)
        self.assertNotIn("catalog_projects.description", str(self.bridge.statements[0]))
        overview = await self.service.public_overview()
        self.assertEqual(overview.hero.total, 14)
        self.assertEqual(len(overview.hero.projects), 6)
        self.assertEqual(overview.hero.next_offset, 6)
        self.assertTrue(all(project.my_score is None for project in overview.hero.projects))
        self.assertEqual(overview.hero.projects[0].category_slug, "other")
        full_reads = [
            str(statement.compile(compile_kwargs={"literal_binds": True}))
            for statement in self.bridge.statements
            if "catalog_projects.description" in str(statement)
        ]
        self.assertEqual(len(full_reads), 1)
        self.assertIn("LIMIT 6", full_reads[0])

    async def test_hero_ai_order_stable_ties_zero_score_and_candidate_membership(self):
        def ai(score):
            return CatalogAiRatingResponse(
                score=score,
                label="AI评分",
                assessment_id="assessment",
                rule_version="rule",
                weight_version="weight",
                source_kind="independent_ai",
                evaluated_at=None,
                reported_review_date=None,
                reported_timezone=None,
                game_version=None,
                dimensions=[],
                play_scope={},
                limitations=[],
            )

        scores = {
            key: ai(value)
            for key, value in {"1": 9, "2": 9, "4": 8, "6": 9, "10": 0, "11": 7}.items()
        }
        with patch.object(
            CatalogAiRatingService, "public_summaries", AsyncMock(return_value=scores)
        ):
            overview = await self.service.public_overview()
            self.assertEqual(
                [item.id for item in overview.hero.projects], ["6", "1", "2", "4", "11", "10"]
            )
            filtered = await self.service.public_overview(
                hero_slugs=("game-2", "game-1", "game-5", "game-7")
            )
            self.assertEqual([item.id for item in filtered.hero.projects], ["1", "2"])
            self.assertEqual(filtered.hero.total, 2)
            self.assertIsNone(filtered.hero.next_offset)
            last = await self.service.public_overview(hero_offset=12)
            self.assertEqual(len(last.hero.projects), 2)
            self.assertIsNone(last.hero.next_offset)

    async def test_public_cache_identity_isolation_etag_304_and_legacy_private_contract(self):
        old_a = await self.client.get("/api/v1/catalog", headers={"X-Real-IP": "192.0.2.1"})
        old_b = await self.client.get("/api/v1/catalog", headers={"X-Real-IP": "192.0.2.2"})
        cards_a = next(
            item for item in old_a.json()["data"]["categories"] if item["slug"] == "cards"
        )
        cards_b = next(
            item for item in old_b.json()["data"]["categories"] if item["slug"] == "cards"
        )
        self.assertEqual(cards_a["projects"][0]["my_score"], 5)
        self.assertIsNone(cards_b["projects"][0]["my_score"])
        self.assertNotIn("category_slug", cards_a["projects"][0])
        self.assertEqual(old_a.headers["cache-control"], "private, no-store")
        self.assertNotIn("etag", old_a.headers)
        first = await self.client.get(
            "/api/v1/catalog/overview", headers={"X-Real-IP": "192.0.2.1"}
        )
        count = len(self.bridge.statements)
        second = await self.client.get(
            "/api/v1/catalog/overview",
            headers={
                "X-Real-IP": "192.0.2.2",
                "Authorization": "Bearer unrelated-identity",
            },
        )
        self.assertEqual(first.content, second.content)
        self.assertEqual(len(self.bridge.statements), count)
        self.assertEqual(first.headers["x-parallellines-cache"], "miss")
        self.assertEqual(second.headers["x-parallellines-cache"], "hit")
        self.assertEqual(second.headers["cache-control"], "public, no-cache")
        for project in second.json()["data"]["hero"]["projects"]:
            self.assertIsNone(project["my_score"])
            self.assertIn("category_slug", project)
            self.assertNotIn("ip_digest", project)
        conditional = await self.client.get(
            "/api/v1/catalog/overview",
            headers={
                "If-None-Match": f'"other", W/{first.headers["etag"]}',
            },
        )
        self.assertEqual(conditional.status_code, 304)
        self.assertEqual(conditional.content, b"")
        self.assertEqual(conditional.headers["etag"], first.headers["etag"])

    async def test_all_cache_parameters_and_explicit_empty_hero(self):
        first = await self.client.get("/api/v1/catalog/overview?hero_slugs=game-2,game-1")
        same = await self.client.get("/api/v1/catalog/overview?hero_slugs=game-1,game-2")
        self.assertEqual(same.headers["x-parallellines-cache"], "hit")
        self.assertEqual(first.content, same.content)
        empty = await self.client.get("/api/v1/catalog/overview?hero_slugs=")
        self.assertEqual(
            empty.json()["data"]["hero"], {"projects": [], "total": 0, "next_offset": None}
        )
        all_games = await self.client.get("/api/v1/catalog/overview")
        self.assertEqual(all_games.json()["data"]["hero"]["total"], 14)
        for suffix in (
            "limit=2",
            "limit=3",
            "limit=2&priority_slugs=game-1,game-2",
            "limit=2&priority_slugs=game-2,game-1",
        ):
            response = await self.client.get(f"/api/v1/catalog/categories/cards/projects?{suffix}")
            self.assertEqual(response.headers["x-parallellines-cache"], "miss")
        for raw in ("game-1,,game-2", "UPPER", ",", ",".join(["valid"] * 65)):
            with self.assertRaises(ValidationError):
                parse_catalog_slug_list(raw)

    async def test_private_write_responses_refresh_public_etag_without_personal_score(self):
        first = await self.client.get("/api/v1/catalog/overview")
        view = await self.client.post("/api/v1/catalog/projects/1/views")
        self.assertEqual(view.json()["data"], {"project_id": "1", "view_count": 1})
        self.assertEqual(view.headers["cache-control"], "private, no-store")
        fresh = await self.client.get(
            "/api/v1/catalog/overview",
            headers={
                "If-None-Match": first.headers["etag"],
            },
        )
        self.assertEqual(fresh.status_code, 200)
        self.assertNotEqual(fresh.headers["etag"], first.headers["etag"])
        project = next(
            item for item in fresh.json()["data"]["hero"]["projects"] if item["id"] == "1"
        )
        self.assertEqual(project["view_count"], 1)
        for submitted in (2, 4):
            rating = await self.client.post(
                "/api/v1/catalog/projects/1/ratings",
                json={
                    "score": submitted,
                },
                headers={"X-Real-IP": "192.0.2.2"},
            )
            self.assertEqual(rating.headers["cache-control"], "private, no-store")
            self.assertEqual(
                rating.json()["data"],
                {
                    "project_id": "1",
                    "average_score": 3.5,
                    "rating_count": 2,
                    "rating_score_sum": 7,
                    "my_score": 2,
                },
            )
        page = await self.client.get("/api/v1/catalog/categories/cards/projects?limit=60")
        project = next(item for item in page.json()["data"]["projects"] if item["id"] == "1")
        self.assertIsNone(project["my_score"])
        self.assertEqual(project["rating_score_sum"], 7)

    async def test_writes_clear_cache_after_commit_and_reject_stale_population(self):
        actions = [
            lambda: self.service.record_view("1"),
            lambda: self.service.rate_project("1", 3, visitor_request("192.0.2.2")),
            lambda: self.service.update_project(
                "1", CatalogProjectUpdateRequest(name="改名"), self.admin
            ),
            lambda: self.service.update_category(
                "1", CatalogCategoryUpdateRequest(name="新分类名"), self.admin
            ),
            lambda: self.service.create_category(
                CatalogCategoryCreateRequest(slug="added", name="新增"), self.admin
            ),
            lambda: self.service.create_project(
                CatalogProjectCreateRequest(
                    category_id="1",
                    slug="added-game",
                    name="新增游戏",
                    url="https://example.org/added",
                    kind="external",
                ),
                self.admin,
            ),
        ]
        key = ("overview", None, 0)
        for action in actions:
            await self.client.get("/api/v1/catalog/overview")
            content, generation = read_public_catalog_cache(key)
            self.assertIsNotNone(content)
            await action()
            self.assertIsNone(read_public_catalog_cache(key)[0])
            store_public_catalog_cache(key, content, generation)
            self.assertIsNone(read_public_catalog_cache(key)[0])
        await self.client.get("/api/v1/catalog/overview")
        with patch.object(self.bridge, "commit", AsyncMock(side_effect=SQLAlchemyError("failure"))):
            with self.assertRaises(AppError):
                await self.service.update_project(
                    "1", CatalogProjectUpdateRequest(name="失败"), self.admin
                )
        self.assertIsNotNone(read_public_catalog_cache(key)[0])

    async def test_approval_clears_cache_and_failures_are_not_cached(self):
        self.session.add(
            CatalogSubmission(
                id="100",
                category_name="卡牌",
                project_name="投稿游戏",
                destination_url="https://example.org/submitted",
                submitter_ip_digest="d" * 64,
                pending_url_digest="e" * 64,
                status="pending",
            )
        )
        self.session.commit()
        await self.client.get("/api/v1/catalog/overview")
        response = await self.client.post(
            "/api/v1/admin/catalog/submissions/100/review", json={"decision": "approve"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(read_public_catalog_cache(("overview", None, 0))[0])
        with patch.object(
            CatalogService, "public_overview", AsyncMock(side_effect=SQLAlchemyError("failure"))
        ):
            failed = await self.client.get("/api/v1/catalog/overview")
            self.assertEqual(failed.status_code, 500)
        self.assertIsNone(read_public_catalog_cache(("overview", None, 0))[0])
        recovered = await self.client.get("/api/v1/catalog/overview")
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.headers["x-parallellines-cache"], "miss")


if __name__ == "__main__":
    unittest.main()
