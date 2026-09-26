import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migration_store(monkeypatch):
    """只用内存 SQLite 验证新增数据，不连接项目配置中的数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_fengling", ROOT / "alembic/versions/0082_add_fengling_town.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_categories VALUES (1, 'stages')")
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
            "VALUES (50, 1, 'existing-stage', '已有游戏', 'https://example.com/stage', 7, 1, 13), "
            "(51, 1, 'hidden-stage', '隐藏游戏', 'https://example.com/hidden', 11, 0, 24)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (50, 5), (51, 3)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def project_rows(connection):
    return connection.execute(sa.text("SELECT * FROM catalog_projects ORDER BY id")).all()


def test_append_sort_default_views_and_repeat_preserve_manual_edits(migration_store):
    migration, connection = migration_store
    previous = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:2] == previous
    added = connection.execute(
        sa.text("SELECT category_id, sort_order, view_count FROM catalog_projects WHERE id > 51")
    ).all()
    # 包含隐藏项目的原排序也应参与追加计算；新计数由数据库默认值初始化。
    assert added == [(1, 12, 0)]
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET name = '人工改名', view_count = 99 WHERE id > 51"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (52, 4)")
    expected_projects = project_rows(connection)
    expected_ratings = connection.execute(sa.text("SELECT * FROM catalog_ratings")).all()
    migration.upgrade()
    migration.downgrade()
    assert project_rows(connection) == expected_projects
    assert connection.execute(sa.text("SELECT * FROM catalog_ratings")).all() == expected_ratings


@pytest.mark.parametrize("url", ["https://uffv.de", "https://uffv.de/"])
def test_root_url_aliases_keep_existing_admin_records(migration_store, url):
    migration, connection = migration_store
    connection.execute(
        sa.text(
            "INSERT INTO catalog_projects "
            "(category_id, slug, name, destination_url, author_name, sort_order, view_count) "
            "VALUES (1, 'manual-alias', '管理员版本', :url, '人工署名', 20, 88)"
        ),
        {"url": url},
    )
    expected = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == expected


def test_existing_slug_keeps_manually_changed_url(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET slug = 'fengling-town', "
        "destination_url = 'https://example.com/manually-changed' WHERE id = 50"
    )
    expected = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == expected


def test_missing_category_stops_before_any_insert(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_categories WHERE slug = 'stages'")
    previous = project_rows(connection)
    with pytest.raises(RuntimeError, match="requires catalog category stages"):
        migration.upgrade()
    assert project_rows(connection) == previous
