import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAMES = (
    (
        "action", "entropy-blade", "熵刃 · ENTROPY BLADE",
        "https://game.inc.re/entropy-blade/",
        "像素风横版动作肉鸽，包含三名角色、武技连段与秘技，"
        "四个场景各有专属敌人与首领，支持键盘、手柄和手机触屏。",
        "mumuhaha487", "https://linux.do/u/mumuhaha487/summary",
    ),
    (
        "exploration", "nexus", "NEXUS", "https://traveritas.github.io/nexus/",
        "第一人称探索游戏，从家中出发，通过门、杯子与床穿行于不同世界，"
        "使用罗盘查看地图，在日记中记录足迹。",
        "traveritas", "https://linux.do/u/traveritas/summary",
    ),
    (
        "action", "emberfall", "EmberFall", "https://ef.usbsb.sbs/",
        "暗黑像素风生存动作游戏，选择近战、远程或法术猎人，通过走位、冲刺和装备构筑"
        "抵御三十波敌潮，随后可继续无尽狩猎，支持键鼠与手机触屏。",
        "doveusa", "https://linux.do/u/doveusa/summary",
    ),
)


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证三款收录，不读取配置或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_three_external_games",
        ROOT / "alembic/versions/0089_add_three_external_games.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES "
            "(1, 'action'), (2, 'exploration'), (3, 'puzzle')"
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
            "(52, 2, 'hidden-exploration', '隐藏探索游戏', 'https://example.com/c', 'external', "
            "NULL, NULL, NULL, NULL, 14, 0, '旧创建时间', '旧修改时间', 18), "
            "(53, 3, 'hidden-puzzle', '隐藏解谜游戏', 'https://example.com/d', 'external', "
            "NULL, NULL, NULL, NULL, 100, 0, '旧创建时间', '旧修改时间', 8)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_ratings VALUES (50, 5), (51, 3), (52, 4), (53, 2)"
        )
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


def test_append_three_games_preserves_old_records_and_statistics(migration_store):
    migration, connection = migration_store
    assert migration.revision == "0089_add_three_external_games"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0088_add_greyfall"
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 7
    assert rating_rows(connection) == ratings
    added = connection.execute(
        sa.text(
            "SELECT c.slug, p.slug, p.name, p.destination_url, p.description, "
            "p.author_name, p.author_url, p.destination_kind, p.icon_upload_id, "
            "p.sort_order, p.view_count, p.is_visible FROM catalog_projects p "
            "JOIN catalog_categories c ON c.id = p.category_id WHERE p.id > 53 ORDER BY p.id"
        )
    ).all()
    # 已确认字段逐项核对；隐藏最大顺序参与追加，两款动作游戏按收录顺序排列。
    assert added == [
        (*game, "external", None, order, 0, 1)
        for game, order in zip(GAMES, (12, 15, 13), strict=True)
    ]
    timestamps = connection.execute(
        sa.text("SELECT created_at, updated_at FROM catalog_projects WHERE id > 53")
    ).all()
    assert len(set(timestamps)) == 1
    assert timestamps[0][0] and timestamps[0][0] == timestamps[0][1]


def test_repeat_and_downgrade_preserve_manual_changes_and_statistics(migration_store):
    migration, connection = migration_store
    migration.upgrade()
    # 管理员改归类、入口、内容、封面和隐藏状态后，重跑与回退仍须保留业务数据。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 3, name = '人工改名', "
        "destination_url = '/play/manual', destination_kind = 'internal', "
        "description = '人工简介', author_name = '人工署名', "
        "author_url = 'https://example.com/manual-author', icon_upload_id = 456, "
        "sort_order = 80, is_visible = 0, view_count = 99, updated_at = '人工修改时间' "
        "WHERE id > 53"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (54, 4), (55, 5), (56, 3)")
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
def test_existing_url_alias_preserves_hidden_other_category_and_adds_other_games(
    migration_store, game, trailing_slash
):
    migration, connection = migration_store
    slug, url = game[1], game[3]
    existing_url = f"{url.rstrip('/')}/" if trailing_slash else url.rstrip("/")
    # 相同地址落在隐藏解谜记录时也视为重复，不应覆盖它或阻止其余两款收录。
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 53"),
        {"url": existing_url},
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 6
    assert rating_rows(connection) == ratings
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"), {"slug": slug}
    ) == 0
    assert connection.execute(
        sa.text("SELECT slug FROM catalog_projects WHERE id > 53 ORDER BY id")
    ).scalars().all() == [item[1] for item in GAMES if item[1] != slug]


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
def test_existing_slug_preserves_hidden_record_and_adds_other_games(migration_store, game):
    migration, connection = migration_store
    slug, url = game[1], game[3]
    # 已改入口的隐藏记录仍以固定标识去重，其余游戏继续追加。
    connection.execute(
        sa.text("UPDATE catalog_projects SET slug = :slug WHERE id = 53"), {"slug": slug}
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 6
    assert rating_rows(connection) == ratings
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"), {"url": url}
    ) == 0
    assert connection.execute(
        sa.text("SELECT slug FROM catalog_projects WHERE id > 53 ORDER BY id")
    ).scalars().all() == [item[1] for item in GAMES if item[1] != slug]


@pytest.mark.parametrize("category", ["action", "exploration"])
def test_missing_any_category_stops_before_first_insert(migration_store, category):
    migration, connection = migration_store
    connection.execute(
        sa.text("DELETE FROM catalog_categories WHERE slug = :slug"), {"slug": category}
    )
    before = project_rows(connection)
    ratings = rating_rows(connection)
    with pytest.raises(
        RuntimeError, match="0089 requires catalog categories action and exploration"
    ):
        migration.upgrade()
    assert project_rows(connection) == before
    assert rating_rows(connection) == ratings


def test_empty_target_categories_start_at_zero_and_preserve_other_category(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings WHERE project_id IN (50, 51, 52)")
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE category_id IN (1, 2)")
    before = project_rows(connection)
    ratings = rating_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:1] == before
    assert rating_rows(connection) == ratings
    assert connection.execute(
        sa.text(
            "SELECT slug, category_id, sort_order, view_count FROM catalog_projects "
            "WHERE id > 53 ORDER BY id"
        )
    ).all() == [("entropy-blade", 1, 0, 0), ("nexus", 2, 0, 0), ("emberfall", 1, 1, 0)]
