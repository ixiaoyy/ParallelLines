import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAME_URL = "https://greyfall-ashen-descent.ayuotk01.chatgpt.site/"


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证收录，不读取配置或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_greyfall", ROOT / "alembic/versions/0088_add_greyfall.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES (1, 'action'), (2, 'puzzle')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT, author_url TEXT, icon_upload_id INTEGER, "
            "sort_order INTEGER, is_visible BOOLEAN, created_at TEXT, updated_at TEXT, "
            "view_count BIGINT NOT NULL DEFAULT 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_projects "
            "(id, category_id, slug, name, destination_url, destination_kind, description, "
            "author_name, author_url, icon_upload_id, sort_order, is_visible, "
            "created_at, updated_at, view_count) VALUES "
            "(50, 1, 'existing-action', '已有动作游戏', 'https://example.com/a', 'external', "
            "'已有简介', '已有作者', 'https://example.com/author', 123, 7, 1, '旧创建时间', "
            "'旧修改时间', 13), "
            "(51, 1, 'hidden-action', '隐藏动作游戏', 'https://example.com/b', 'external', "
            "NULL, NULL, NULL, NULL, 11, 0, '旧创建时间', '旧修改时间', 24), "
            "(52, 2, 'hidden-puzzle', '隐藏解谜游戏', 'https://example.com/c', 'external', "
            "NULL, NULL, NULL, NULL, 100, 0, '旧创建时间', '旧修改时间', 18)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (50, 5), (51, 3), (52, 4)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def project_rows(connection):
    """读取内存连接的完整项目快照，按主键稳定排序验证旧数据保留。"""

    return connection.execute(sa.text("SELECT * FROM catalog_projects ORDER BY id")).all()


def rating_rows(connection):
    """读取内存连接的评分快照，按项目稳定排序验证迁移不改统计。"""

    return connection.execute(
        sa.text("SELECT * FROM catalog_ratings ORDER BY project_id, score")
    ).all()


def test_append_game_preserves_old_records_and_statistics(migration_store):
    migration, connection = migration_store
    assert migration.revision == "0088_add_greyfall"
    assert migration.down_revision == "0087_add_astra_updates"
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:3] == before
    assert len(project_rows(connection)) == 4
    assert rating_rows(connection) == ratings
    added = connection.execute(
        sa.text(
            "SELECT c.slug, p.slug, p.name, p.destination_url, p.destination_kind, "
            "p.description, p.author_name, p.author_url, p.icon_upload_id, p.sort_order, "
            "p.is_visible, p.view_count, p.created_at, p.updated_at FROM catalog_projects p "
            "JOIN catalog_categories c ON c.id = p.category_id WHERE p.slug = 'greyfall'"
        )
    ).one()
    # 已确认的元数据保持一致；动作分类隐藏项目参与排序，其他分类不影响顺序。
    assert added[:12] == (
        "action", "greyfall", "烬落 GREYFALL", GAME_URL, "external",
        "黑白像素横版动作游戏，探索随机地牢，选择武器与强化，"
        "翻滚避险并挑战首领；需使用键盘游玩。",
        "hlool", "https://linux.do/u/hlool/summary", None, 12, 1, 0,
    )
    assert added.created_at and added.created_at == added.updated_at


def test_repeat_and_downgrade_preserve_manual_changes_and_statistics(migration_store):
    migration, connection = migration_store
    migration.upgrade()
    # 模拟管理员修改归类、入口、内容和隐藏状态后，重跑与回退仍须保留业务数据。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 2, name = '人工改名', "
        "destination_url = '/play/manual', destination_kind = 'internal', "
        "description = '人工简介', author_name = '人工署名', "
        "author_url = 'https://example.com/manual-author', icon_upload_id = 456, "
        "sort_order = 80, is_visible = 0, view_count = 99, updated_at = '人工修改时间' "
        "WHERE slug = 'greyfall'"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (53, 4)")
    expected = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == expected
    migration.downgrade()
    assert project_rows(connection) == expected
    assert rating_rows(connection) == ratings
    migration.upgrade()
    assert project_rows(connection) == expected
    assert rating_rows(connection) == ratings


@pytest.mark.parametrize("trailing_slash", [False, True])
def test_existing_url_alias_in_other_category_preserves_hidden_record(
    migration_store, trailing_slash
):
    migration, connection = migration_store
    existing_url = GAME_URL if trailing_slash else GAME_URL.rstrip("/")
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 52"),
        {"url": existing_url},
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings


def test_existing_slug_preserves_hidden_record_with_changed_destination(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("UPDATE catalog_projects SET slug = 'greyfall' WHERE id = 51")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings


def test_missing_action_category_stops_before_insert(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_categories WHERE slug = 'action'")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    with pytest.raises(RuntimeError, match="0088 requires catalog category action"):
        migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings


def test_empty_action_category_starts_from_zero(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings WHERE project_id IN (50, 51)")
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE category_id = 1")
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:1] == before
    added = connection.execute(
        sa.text(
            "SELECT category_id, sort_order, view_count FROM catalog_projects "
            "WHERE slug = 'greyfall'"
        )
    ).one()
    assert added == (1, 0, 0)
