import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.catalog import router
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.db.base import Base
from app.db.session import get_session
from app.models.catalog import CatalogCategory, CatalogProject, CatalogRating
from app.schemas.catalog import CatalogProjectCreateRequest, CatalogProjectUpdateRequest
from app.services.catalog import SAVE_FAILED_MESSAGE, CatalogService

ROOT = Path(__file__).resolve().parents[1]
BEFORE = datetime(2026, 9, 26, 0, 0, tzinfo=UTC)
SETTINGS = SimpleNamespace(catalog_rating_ip_secret="", jwt_secret_key="")


class SQLiteSession:
    """用同步内存 SQLite 执行真实 SQL，提供服务所需异步接口，不访问配置数据库。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.rollback_count = 0

    async def execute(self, statement):
        return self.session.execute(statement)

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.rollback_count += 1
        self.session.rollback()


@pytest.fixture
def catalog_store():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[CatalogCategory.__table__, CatalogProject.__table__, CatalogRating.__table__],
    )
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                CatalogCategory(id="1", slug="cards", name="卡牌", is_visible=True),
                CatalogCategory(id="2", slug="hidden", name="隐藏分类", is_visible=False),
            ]
        )
        for project_id, category_id, is_visible in [
            ("1", "1", True),
            ("2", "1", False),
            ("3", "2", True),
        ]:
            session.add(
                CatalogProject(
                    id=project_id,
                    category_id=category_id,
                    slug=f"game-{project_id}",
                    name=f"游戏 {project_id}",
                    destination_url=f"https://example.com/{project_id}",
                    destination_kind="external",
                    is_visible=is_visible,
                    created_at=BEFORE,
                    updated_at=BEFORE,
                )
            )
        session.add(CatalogRating(id="1", project_id="1", ip_digest="a" * 64, score=5))
        session.commit()
        yield engine, session, SQLiteSession(session)
    engine.dispose()


@pytest.mark.asyncio
async def test_atomic_increment_does_not_use_stale_objects_or_change_content_time(catalog_store):
    engine, session, bridge = catalog_store
    stale_first = session.get(CatalogProject, "1")
    with Session(engine, expire_on_commit=False) as second_session:
        stale_second = second_session.get(CatalogProject, "1")
        assert stale_first.view_count == stale_second.view_count == 0
        first = await CatalogService(bridge, SETTINGS).record_view("1")
        second = await CatalogService(SQLiteSession(second_session), SETTINGS).record_view("1")
    assert first.view_count == 1
    assert second.view_count == 2
    assert session.scalar(sa.select(CatalogProject.view_count).where(CatalogProject.id == "1")) == 2
    assert session.scalar(
        sa.select(CatalogProject.updated_at).where(CatalogProject.id == "1")
    ) == BEFORE.replace(tzinfo=None)
    assert session.scalar(
        sa.select(CatalogProject.created_at).where(CatalogProject.id == "1")
    ) == BEFORE.replace(tzinfo=None)
    assert session.execute(sa.select(CatalogRating.project_id, CatalogRating.score)).all() == [
        ("1", 5)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("project_id", ["2", "3", "999", "invalid", "0"])
async def test_hidden_or_missing_project_is_not_counted(catalog_store, project_id):
    _, session, bridge = catalog_store
    with pytest.raises(NotFoundError) as error:
        await CatalogService(bridge, SETTINGS).record_view(project_id)
    assert error.value.status_code == 404
    assert session.scalar(sa.select(sa.func.sum(CatalogProject.view_count))) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_step", ["execute", "scalar", "commit"])
async def test_count_failure_rolls_back_and_uses_existing_error(
    catalog_store, monkeypatch, failed_step
):
    _, session, bridge = catalog_store
    monkeypatch.setattr(bridge, failed_step, AsyncMock(side_effect=SQLAlchemyError("test failure")))
    with pytest.raises(AppError) as error:
        await CatalogService(bridge, SETTINGS).record_view("1")
    assert error.value.status_code == 503
    assert error.value.message == SAVE_FAILED_MESSAGE
    assert bridge.rollback_count == 1
    assert session.scalar(sa.select(CatalogProject.view_count).where(CatalogProject.id == "1")) == 0


@pytest.mark.asyncio
async def test_public_post_and_get_preserve_contract_and_rating(catalog_store):
    _, session, bridge = catalog_store
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def isolated_session():
        yield bridge

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, error: AppError):
        return JSONResponse(status_code=error.status_code, content={"error": {"code": error.code}})

    app.dependency_overrides[get_session] = isolated_session
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        before = await client.get("/api/v1/catalog")
        assert before.status_code == 200
        assert before.json()["data"]["categories"][0]["projects"][0]["view_count"] == 0
        for count in (1, 2):
            response = await client.post("/api/v1/catalog/projects/1/views")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            assert response.json()["data"] == {"project_id": "1", "view_count": count}
        assert (await client.post("/api/v1/catalog/projects/3/views")).status_code == 404
        after = await client.get("/api/v1/catalog")
        project = after.json()["data"]["categories"][0]["projects"][0]
        assert project["view_count"] == 2
        assert project["rating_count"] == 1
        assert project["rating_score_sum"] == 5
    assert session.scalar(sa.select(CatalogProject.view_count).where(CatalogProject.id == "1")) == 2


def test_admin_response_includes_count_but_admin_input_cannot_set_it(catalog_store):
    _, session, bridge = catalog_store
    session.execute(sa.update(CatalogProject).where(CatalogProject.id == "1").values(view_count=7))
    project = session.get(CatalogProject, "1")
    service = CatalogService(bridge, SETTINGS)
    assert service._project_response(project, {}, {}).view_count == 7
    assert service._admin_project_response(project, {}).view_count == 7
    create = CatalogProjectCreateRequest(
        category_id="1",
        slug="new-game",
        name="New game",
        url="https://example.com/",
        kind="external",
        view_count=999,
    )
    update = CatalogProjectUpdateRequest(view_count=999)
    assert "view_count" not in create.model_dump()
    assert update.model_dump(exclude_unset=True) == {}


@pytest.fixture
def catalog_migration(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "catalog_games_and_views", ROOT / "alembic/versions/0081_catalog_games_and_views.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_categories VALUES (1, 'rts'), (2, 'cards')")
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT, author_url TEXT, sort_order INTEGER, "
            "is_visible BOOLEAN, created_at TEXT, updated_at TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        yield module, connection
    engine.dispose()


def test_migration_defaults_seed_idempotence_author_and_downgrade(catalog_migration):
    migration, connection = catalog_migration
    migration.upgrade()
    rows = connection.execute(
        sa.text(
            "SELECT slug, author_name, author_url, view_count FROM catalog_projects ORDER BY id"
        )
    ).all()
    assert rows == [
        ("shi-yu-yuanfang", "liangdabiao", "https://linux.do/u/liangdabiao/summary", 0),
        ("hongloumeng-haitang-shishe", "liangdabiao", "https://linux.do/u/liangdabiao/summary", 0),
    ]
    connection.exec_driver_sql("UPDATE catalog_projects SET view_count = 4 WHERE id = 1")
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (1, 5)")
    migration.upgrade()
    assert connection.scalar(sa.text("SELECT COUNT(*) FROM catalog_projects")) == 2
    assert connection.scalar(sa.text("SELECT view_count FROM catalog_projects WHERE id = 1")) == 4
    field = next(
        c
        for c in sa.inspect(connection).get_columns("catalog_projects")
        if c["name"] == "view_count"
    )
    assert isinstance(field["type"], sa.BigInteger)
    assert field["nullable"] is False
    migration.downgrade()
    assert "view_count" not in {
        c["name"] for c in sa.inspect(connection).get_columns("catalog_projects")
    }
    assert connection.scalar(sa.text("SELECT COUNT(*) FROM catalog_projects")) == 2
    assert connection.execute(sa.text("SELECT * FROM catalog_ratings")).all() == [(1, 5)]


@pytest.mark.parametrize("url", ["https://gushi.348349.xyz", "https://gushi.348349.xyz/"])
def test_migration_root_url_deduplication_preserves_existing_game(catalog_migration, url):
    migration, connection = catalog_migration
    connection.execute(
        sa.text(
            "INSERT INTO catalog_projects (id, category_id, slug, name, destination_url, "
            "author_name, sort_order) VALUES (10, 1, 'manual-entry', '管理员名称', :url, '作者', 7)"
        ),
        {"url": url},
    )
    migration.upgrade()
    assert connection.scalar(sa.text("SELECT COUNT(*) FROM catalog_projects")) == 2
    assert connection.execute(
        sa.text(
            "SELECT slug, name, destination_url, author_name, view_count "
            "FROM catalog_projects WHERE id = 10"
        )
    ).one() == ("manual-entry", "管理员名称", url, "作者", 0)
    assert (
        connection.scalar(
            sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = 'shi-yu-yuanfang'")
        )
        == 0
    )


def test_migration_preflight_requires_both_categories_before_schema_change(catalog_migration):
    migration, connection = catalog_migration
    connection.exec_driver_sql("DELETE FROM catalog_categories WHERE slug = 'cards'")
    with pytest.raises(RuntimeError, match="requires catalog category cards"):
        migration.upgrade()
    assert "view_count" not in {
        c["name"] for c in sa.inspect(connection).get_columns("catalog_projects")
    }
    assert connection.scalar(sa.text("SELECT COUNT(*) FROM catalog_projects")) == 0


def test_migration_has_one_head():
    config = Config()
    config.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0081_catalog_games_and_views"]
    assert script.get_revision("head").down_revision == "0080_unify_catalog_genres"
