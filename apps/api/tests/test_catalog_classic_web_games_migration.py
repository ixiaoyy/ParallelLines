import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAMES = (
    (
        "stages", "choppy-orc", "Choppy Orc", "https://eddynardo.com/games/choppy-orc/",
        "操纵兽人投掷斧头，跨越障碍完成平台闯关；支持键盘与 Xbox 手柄。",
        "eddynardo", "https://eddynardo.com/",
    ),
    (
        "puzzle", "0hh1", "0h h1", "https://0hh1.com/",
        "用两种颜色填满棋盘：横纵不可连续三格同色，每行列两色数量相等，"
        "任意两行或两列不能完全相同。",
        "Q42 / Martin Kool", "https://www.q42.nl/en",
    ),
    (
        "puzzle", "0hn0", "0h n0", "https://0hn0.com/",
        "根据蓝点中的数字推断横纵方向可见的蓝点，红点会阻断视线，逐步解开棋盘。",
        "Q42 / Martin Kool", "https://www.q42.nl/en",
    ),
)


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证本批收录，不读取配置或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_classic_web_games",
        ROOT / "alembic/versions/0104_add_classic_web_games.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES (1, 'stages'), (2, 'puzzle'), (5, 'other')"
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
            "(50, 1, 'existing-stages', '已有游戏', 'https://example.com/a', 'external', "
            "'已有简介', '已有作者', 'https://example.com/author', 123, 7, 1, '旧创建时间', "
            "'旧修改时间', 13), "
            "(51, 1, 'hidden-stages', '隐藏闯关', 'https://example.com/b', 'external', "
            "NULL, NULL, NULL, NULL, 11, 0, '旧创建时间', '旧修改时间', 24), "
            "(52, 2, 'visible-puzzle', '已有解谜', 'https://example.com/c', 'external', "
            "NULL, NULL, NULL, NULL, 4, 1, '旧创建时间', '旧修改时间', 18), "
            "(53, 2, 'hidden-puzzle', '隐藏解谜', 'https://example.com/d', 'external', "
            "NULL, NULL, NULL, NULL, 14, 0, '旧创建时间', '旧修改时间', 8), "
            "(54, 5, 'visible-other', '其他游戏', 'https://example.com/e', 'external', "
            "NULL, NULL, NULL, NULL, 8, 1, '旧创建时间', '旧修改时间', 5), "
            "(55, 5, 'hidden-other', '其他隐藏', 'https://example.com/f', 'external', "
            "NULL, NULL, NULL, NULL, 100, 0, '旧创建时间', '旧修改时间', 9)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_ratings VALUES (50, 5), (51, 3), (52, 4), "
            "(53, 2), (54, 4), (55, 5)"
        )
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


def test_append_three_games_preserves_old_records_and_statistics(migration_store):
    migration, connection = migration_store
    assert migration.revision == "0104_add_classic_web_games"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0103_add_more_web_games"
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:6] == before
    assert len(project_rows(connection)) == 9
    assert rating_rows(connection) == ratings
    added = connection.execute(
        sa.text(
            "SELECT c.slug, p.slug, p.name, p.destination_url, p.description, "
            "p.author_name, p.author_url, p.destination_kind, p.icon_upload_id, "
            "p.sort_order, p.view_count, p.is_visible FROM catalog_projects p "
            "JOIN catalog_categories c ON c.id = p.category_id WHERE p.id > 55 ORDER BY p.id"
        )
    ).all()
    # 两款解谜分别保留各自规则并顺序追加，旧隐藏条目的字段与统计不变。
    assert added == [
        (*game, "external", None, order, 0, 1)
        for game, order in zip(GAMES, (12, 15, 16), strict=True)
    ]
    timestamps = connection.execute(
        sa.text("SELECT created_at, updated_at FROM catalog_projects WHERE id > 55")
    ).all()
    assert len(set(timestamps)) == 1
    assert timestamps[0][0] and timestamps[0][0] == timestamps[0][1]


def test_q42_projects_preserve_creator_and_share_author_url(migration_store):
    migration, connection = migration_store
    migration.upgrade()
    # 元数据必须使用同一作者键，并在展示署名中保留可搜索的 Martin Kool。
    assert connection.execute(
        sa.text(
            "SELECT author_name, author_url, COUNT(*) FROM catalog_projects "
            "WHERE slug IN ('0hh1', '0hn0') GROUP BY author_name, author_url"
        )
    ).all() == [("Q42 / Martin Kool", "https://www.q42.nl/en", 2)]


def test_repeat_and_downgrade_preserve_manual_changes_and_statistics(migration_store):
    migration, connection = migration_store
    migration.upgrade()
    # 人工改分类、入口、内容、封面、排序与隐藏状态后，重跑和回退均须原样保留。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 5, name = '人工改名', "
        "destination_url = '/play/manual', destination_kind = 'internal', "
        "description = '人工简介', author_name = '人工署名', "
        "author_url = 'https://example.com/manual-author', icon_upload_id = 456, "
        "sort_order = 80, is_visible = 0, view_count = 99, updated_at = '人工修改时间' "
        "WHERE id > 55"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (56, 4), (57, 5), (58, 3)")
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


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_existing_url_preserves_hidden_other_category_and_adds_remaining_games(
    migration_store, game, trailing_slash
):
    migration, connection = migration_store
    slug, url = game[1], game[3]
    existing_url = f"{url.rstrip('/')}/" if trailing_slash else url.rstrip("/")
    # 同一地址已在其他分类隐藏时也应去重，不覆盖已有记录，其余作品继续追加。
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 55"),
        {"url": existing_url},
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:6] == before
    assert len(project_rows(connection)) == 8
    assert rating_rows(connection) == ratings
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"), {"slug": slug}
    ) == 0
    assert connection.execute(
        sa.text("SELECT slug FROM catalog_projects WHERE id > 55 ORDER BY id")
    ).scalars().all() == [item[1] for item in GAMES if item[1] != slug]


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
def test_existing_slug_preserves_hidden_record_and_adds_remaining_games(migration_store, game):
    migration, connection = migration_store
    slug, url = game[1], game[3]
    # 固定标识相同但入口已人工变更时，不用新资料覆盖隐藏记录。
    connection.execute(
        sa.text("UPDATE catalog_projects SET slug = :slug WHERE id = 55"), {"slug": slug}
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:6] == before
    assert len(project_rows(connection)) == 8
    assert rating_rows(connection) == ratings
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"), {"url": url}
    ) == 0
    assert connection.execute(
        sa.text("SELECT slug FROM catalog_projects WHERE id > 55 ORDER BY id")
    ).scalars().all() == [item[1] for item in GAMES if item[1] != slug]


@pytest.mark.parametrize("category", ["stages", "puzzle"])
def test_missing_any_category_stops_before_first_insert(migration_store, category):
    migration, connection = migration_store
    connection.execute(
        sa.text("DELETE FROM catalog_categories WHERE slug = :slug"), {"slug": category}
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    with pytest.raises(RuntimeError, match="0104 requires catalog categories stages and puzzle"):
        migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings


def test_empty_target_categories_start_at_zero_and_preserve_other_category(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings WHERE project_id < 54")
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE category_id IN (1, 2)")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:2] == before
    assert rating_rows(connection) == ratings
    assert connection.execute(
        sa.text(
            "SELECT slug, category_id, sort_order, view_count FROM catalog_projects "
            "WHERE id > 55 ORDER BY id"
        )
    ).all() == [
        (game[1], category_id, order, 0)
        for game, category_id, order in zip(GAMES, (1, 2, 2), (0, 0, 1), strict=True)
    ]
