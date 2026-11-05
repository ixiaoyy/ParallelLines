import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = (
    "英文文字互动剧情：少女 Bridget 在夏令营中暗恋女孩 Bell，"
    "在奇幻梦境与日常交流间探索感情和自我认同；包含粗口与成熟话题。"
)


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证收录，不读取配置或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_birdland", ROOT / "alembic/versions/0107_add_birdland.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES (1, 'romance'), (5, 'other')"
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
            "(50, 1, 'existing-romance', '已有游戏', 'https://example.com/a', 'external', "
            "'已有简介', '已有作者', 'https://example.com/author', 123, 7, 1, '旧创建时间', "
            "'旧修改时间', 13), "
            "(51, 1, 'hidden-romance', '隐藏恋爱', 'https://example.com/b', 'external', "
            "NULL, NULL, NULL, NULL, 11, 0, '旧创建时间', '旧修改时间', 24), "
            "(55, 5, 'hidden-other', '其他隐藏', 'https://example.com/c', 'external', "
            "'人工简介', '人工作者', 'https://example.com/other-author', 456, "
            "100, 0, '旧创建时间', '旧修改时间', 9)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (50, 5), (51, 3), (55, 4)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def project_rows(connection):
    """按主键读取内存项目快照，验证迁移完整保留已有数据。"""

    return connection.execute(sa.text("SELECT * FROM catalog_projects ORDER BY id")).all()


def rating_rows(connection):
    """按项目稳定读取内存评分快照，验证迁移不修改评分。"""

    return connection.execute(
        sa.text("SELECT * FROM catalog_ratings ORDER BY project_id, score")
    ).all()


def test_append_birdland_preserves_old_records_and_statistics(migration_store):
    migration, connection = migration_store
    assert migration.revision == "0107_add_birdland"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0106_add_direct_game_sites"
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:3] == before
    assert len(project_rows(connection)) == 4
    assert rating_rows(connection) == ratings
    added = connection.execute(
        sa.text(
            "SELECT c.slug, p.slug, p.name, p.destination_url, p.description, "
            "p.author_name, p.author_url, p.destination_kind, p.icon_upload_id, "
            "p.sort_order, p.view_count, p.is_visible FROM catalog_projects p "
            "JOIN catalog_categories c ON c.id = p.category_id WHERE p.slug = 'birdland'"
        )
    ).one()
    # 入口为英文游戏本体，作者页仅作完整署名来源；隐藏旧项目的排序与非零统计不变。
    assert added == (
        "romance", "birdland", "BIRDLAND", "https://birdland.camp/", DESCRIPTION,
        "Brendan Patrick Hennessy / Izzy Marbella", "https://bphennessy.itch.io/birdland",
        "external", None, 12, 0, 1,
    )
    timestamps = connection.execute(
        sa.text("SELECT created_at, updated_at FROM catalog_projects WHERE slug = 'birdland'")
    ).one()
    assert timestamps[0] and timestamps[0] == timestamps[1]


def test_repeat_and_downgrade_preserve_manual_changes_and_statistics(migration_store):
    migration, connection = migration_store
    migration.upgrade()
    # 人工改分类、入口、内容、封面、排序与隐藏状态后，重跑和回退均须原样保留。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 5, name = '人工改名', "
        "destination_url = '/play/manual', destination_kind = 'internal', "
        "description = '人工简介', author_name = '人工署名', "
        "author_url = 'https://example.com/manual-author', icon_upload_id = 789, "
        "sort_order = 80, is_visible = 0, view_count = 99, updated_at = '人工修改时间' "
        "WHERE slug = 'birdland'"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (56, 5)")
    expected = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == expected
    assert rating_rows(connection) == ratings
    migration.downgrade()
    assert project_rows(connection) == expected
    assert rating_rows(connection) == ratings
    migration.upgrade()
    assert project_rows(connection) == expected
    assert rating_rows(connection) == ratings


@pytest.mark.parametrize("category_id", [1, 5])
@pytest.mark.parametrize("is_visible", [False, True])
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_existing_url_keeps_manual_record_without_duplicate(
    migration_store, category_id, is_visible, trailing_slash
):
    migration, connection = migration_store
    # 作者已用其他标识维护同一入口时，无论分类和显隐状态都不得覆盖或重复收录。
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET category_id = :category_id, is_visible = :visible, "
            "destination_url = :url WHERE id = 55"
        ),
        {
            "category_id": category_id, "visible": is_visible,
            "url": "https://birdland.camp/" if trailing_slash else "https://birdland.camp",
        },
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = 'birdland'")
    ) == 0


def test_existing_slug_preserves_hidden_record_with_manual_url(migration_store):
    migration, connection = migration_store
    # 标识相同但入口已人工改为其他地址时，同样保留跨分类隐藏记录及其评分。
    connection.exec_driver_sql("UPDATE catalog_projects SET slug = 'birdland' WHERE id = 55")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"),
        {"url": "https://birdland.camp/"},
    ) == 0


def test_missing_romance_category_stops_before_first_insert(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_categories WHERE slug = 'romance'")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    with pytest.raises(RuntimeError, match="0107 requires catalog category romance"):
        migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings


def test_empty_romance_category_starts_at_zero_and_preserves_other_category(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings WHERE project_id IN (50, 51)")
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE category_id = 1")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:1] == before
    assert rating_rows(connection) == ratings
    assert connection.execute(
        sa.text(
            "SELECT slug, category_id, sort_order, view_count, is_visible FROM catalog_projects "
            "WHERE id > 55 ORDER BY id"
        )
    ).all() == [("birdland", 1, 0, 0, 1)]
