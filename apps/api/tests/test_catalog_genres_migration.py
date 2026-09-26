import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "alembic/data/catalog_genres_20260927.json").read_text(encoding="utf-8"))


@pytest.fixture
def catalog_migration(monkeypatch):
    """用独立内存库验证分类数据迁移，不连接项目测试库或线上数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_genres_migration", ROOT / "alembic/versions/0080_unify_catalog_genres.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE, "
                "name TEXT, sort_order INTEGER, is_visible BOOLEAN, "
                "created_at TEXT, updated_at TEXT)"
            )
        )
        connection.execute(
            sa.text(
                "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, slug TEXT UNIQUE, "
                "category_id INTEGER, name TEXT, destination_url TEXT, author_name TEXT, "
                "icon_upload_id INTEGER, is_visible BOOLEAN, updated_at TEXT)"
            )
        )
        connection.execute(
            sa.text("CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)")
        )
        for index, category in enumerate(PLAN["previous_categories"], 1):
            connection.execute(
                sa.text(
                    "INSERT INTO catalog_categories VALUES "
                    "(:id, :slug, :name, :id, 1, 'before', 'before')"
                ),
                {**category, "id": index},
            )
        ids = dict(connection.execute(sa.text("SELECT slug, id FROM catalog_categories")).all())
        for index, project in enumerate(PLAN["projects"], 1):
            connection.execute(
                sa.text(
                    "INSERT INTO catalog_projects VALUES "
                    "(:id, :slug, :category_id, :name, 'https://example.com/game', "
                    "'original-author', 123, 1, 'before')"
                ),
                {**project, "id": index, "category_id": ids[project["previous_category"]]},
            )
        connection.execute(sa.text("INSERT INTO catalog_ratings VALUES (1, 5), (2, 3)"))
        monkeypatch.setattr(module, "op", SimpleNamespace(get_bind=lambda: connection))
        yield module, connection
    engine.dispose()


def project_categories(connection):
    return dict(
        connection.execute(
            sa.text(
                "SELECT p.slug, c.slug FROM catalog_projects p "
                "JOIN catalog_categories c ON c.id = p.category_id"
            )
        ).all()
    )


def test_all_games_are_classified_without_changing_content(catalog_migration):
    migration, connection = catalog_migration
    content_query = sa.text(
        "SELECT id, slug, name, destination_url, author_name, icon_upload_id, is_visible "
        "FROM catalog_projects ORDER BY id"
    )
    content = connection.execute(content_query).all()
    migration.upgrade()
    categories = project_categories(connection)
    assert len(categories) == 183
    assert categories == {p["slug"]: p["category"] for p in PLAN["projects"]}
    assert categories["merge-watermelon"] == "casual"
    assert categories["generals-soldiers"] == "rts"
    assert categories["super-mario"] == "stages"
    assert categories["fablespace"] == "farming"
    assert connection.execute(content_query).all() == content
    assert connection.execute(
        sa.text("SELECT * FROM catalog_ratings ORDER BY project_id")
    ).all() == [(1, 5), (2, 3)]
    visible = connection.execute(
        sa.text(
            "SELECT slug, name FROM catalog_categories WHERE is_visible = 1 ORDER BY sort_order"
        )
    ).all()
    assert visible == [(c["slug"], c["name"]) for c in PLAN["categories"]]


def test_manual_moves_and_unlisted_hidden_games_are_preserved(catalog_migration):
    migration, connection = catalog_migration
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET category_id = "
            "(SELECT id FROM catalog_categories WHERE slug = 'racing') "
            "WHERE slug = 'astra-9681da78b6870a313d7b'"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO catalog_projects (slug, category_id, name, is_visible) "
            "VALUES ('custom-hidden', (SELECT id FROM catalog_categories "
            "WHERE slug = 'astra-action-arcade'), 'Hidden game', 0)"
        )
    )
    migration.upgrade()
    categories = project_categories(connection)
    assert categories["astra-9681da78b6870a313d7b"] == "racing"
    assert categories["custom-hidden"] == "astra-action-arcade"
    assert (
        connection.scalar(
            sa.text("SELECT is_visible FROM catalog_categories WHERE slug = 'astra-action-arcade'")
        )
        == 1
    )
    migration.downgrade()
    assert project_categories(connection)["astra-9681da78b6870a313d7b"] == "racing"


def test_repeat_upgrade_and_downgrade_preserve_classification(catalog_migration):
    migration, connection = catalog_migration
    # 迁移前已人工归入目标分类时，回退版本号也不能把它移回来源分类。
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET category_id = "
            "(SELECT id FROM catalog_categories WHERE slug = 'casual') "
            "WHERE slug = 'astra-9681da78b6870a313d7b'"
        )
    )
    migration.upgrade()
    expected = project_categories(connection)
    migration.upgrade()
    assert project_categories(connection) == expected
    migration.downgrade()
    assert project_categories(connection) == expected
    assert (
        connection.scalar(sa.text("SELECT COUNT(*) FROM catalog_categories WHERE is_visible = 1"))
        == 15
    )
