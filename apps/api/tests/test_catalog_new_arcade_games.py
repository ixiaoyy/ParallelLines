import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.core.exceptions import ValidationError
from app.services.catalog import CatalogService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migration_store(monkeypatch):
    """在独立内存 SQLite 验证两条收录，不读取或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_arcade", ROOT / "alembic/versions/0085_add_snake_flappy_dunk.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES (1, 'puzzle'), (2, 'casual')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT, author_url TEXT, sort_order INTEGER, "
            "is_visible BOOLEAN, created_at TEXT, updated_at TEXT, "
            "view_count BIGINT NOT NULL DEFAULT 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_projects "
            "(id, category_id, slug, name, destination_url, sort_order, is_visible, view_count) "
            "VALUES (50, 1, 'existing-puzzle', '已有游戏', 'https://example.com', 7, 1, 13), "
            "(51, 1, 'hidden-puzzle', '隐藏游戏', 'https://example.com/hidden', 11, 0, 24)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (50, 5)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def rows(connection):
    return connection.execute(sa.text("SELECT * FROM catalog_projects ORDER BY id")).all()


def test_append_to_two_categories_and_preserve_repeat_and_downgrade(migration_store):
    migration, connection = migration_store
    before = rows(connection)
    migration.upgrade()
    assert rows(connection)[:2] == before
    assert connection.execute(
        sa.text(
            "SELECT category_id, slug, destination_url, destination_kind, sort_order, view_count "
            "FROM catalog_projects WHERE id > 51 ORDER BY id"
        )
    ).all() == [
        (1, "snake-escape", "/play/snake-escape", "internal", 12, 0),
        (2, "flappy-dunk", "/play/flappy-dunk", "internal", 0, 0),
    ]
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET name = '人工改名', is_visible = 0, "
        "view_count = 99 WHERE id > 51"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (52, 4), (53, 5)")
    expected = rows(connection)
    ratings = connection.execute(sa.text("SELECT * FROM catalog_ratings")).all()
    migration.upgrade()
    migration.downgrade()
    assert rows(connection) == expected
    assert connection.execute(sa.text("SELECT * FROM catalog_ratings")).all() == ratings


@pytest.mark.parametrize("url", ["/play/snake-escape", "/play/snake-escape/"])
def test_existing_url_keeps_alias_and_only_adds_other_game(migration_store, url):
    migration, connection = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 50"), {"url": url}
    )
    before = rows(connection)
    migration.upgrade()
    assert rows(connection)[:2] == before
    assert len(rows(connection)) == 3
    assert rows(connection)[2].slug == "flappy-dunk"


def test_existing_slug_preserves_changed_destination(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("UPDATE catalog_projects SET slug = 'flappy-dunk' WHERE id = 51")
    before = rows(connection)
    migration.upgrade()
    assert rows(connection)[:2] == before
    assert len(rows(connection)) == 3
    assert rows(connection)[2].slug == "snake-escape"


@pytest.mark.parametrize("category", ["puzzle", "casual"])
def test_missing_either_category_stops_before_first_write(migration_store, category):
    migration, connection = migration_store
    connection.execute(
        sa.text("DELETE FROM catalog_categories WHERE slug = :slug"), {"slug": category}
    )
    before = rows(connection)
    with pytest.raises(RuntimeError, match="requires catalog categories"):
        migration.upgrade()
    assert rows(connection) == before


@pytest.mark.parametrize(
    "url", ["/play/generals-soldiers", "/play/snake-escape", "/play/flappy-dunk"]
)
def test_internal_game_whitelist_preserves_old_game_and_accepts_new_games(url):
    CatalogService._validate_destination("internal", url)


@pytest.mark.parametrize(
    "url", ["/play/unknown", "/admin", "/play/snake-escape/", "https://evil.test"]
)
def test_unregistered_internal_destinations_stay_rejected(url):
    with pytest.raises(ValidationError):
        CatalogService._validate_destination("internal", url)


def test_external_https_behavior_stays_unchanged():
    CatalogService._validate_destination("external", "https://example.com/game")
    with pytest.raises(ValidationError):
        CatalogService._validate_destination("external", "http://example.com/game")
