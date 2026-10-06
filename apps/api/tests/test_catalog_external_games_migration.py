import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAMES = (
    ("soulforge", "https://soulforge.glasden.top/"),
    ("achroma", "https://game.unsnow.online/ach/"),
    ("pelican-rider", "https://luoxiaoman.com/pelican-rider/"),
    ("shousui", "https://shousui.vercel.app/"),
    ("sketch-rts", "https://lexicalmathical.com/sketch-rts/"),
    ("bubble-tank", "https://bubble-tank.zackwill.space/"),
)


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证整批收录，不读取或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_external_games", ROOT / "alembic/versions/0086_add_external_games.py"
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
            "(1, 'action'), (2, 'racing'), (3, 'rts'), (4, 'shooting')"
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
            "VALUES (50, 1, 'existing-action', '已有动作游戏', 'https://example.com/a', 7, 1, 13), "
            "(51, 1, 'hidden-action', '隐藏动作游戏', 'https://example.com/b', 11, 0, 24), "
            "(52, 3, 'hidden-rts', '隐藏策略游戏', 'https://example.com/c', 14, 0, 18), "
            "(53, 2, 'existing-racing', '已有竞速游戏', 'https://example.com/d', 3, 1, 8)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (50, 5), (51, 3), (52, 4)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def project_rows(connection):
    """读取给定内存连接中的完整项目快照，按主键稳定排序供保留行为断言。"""

    return connection.execute(sa.text("SELECT * FROM catalog_projects ORDER BY id")).all()


def test_append_six_games_and_preserve_repeat_and_downgrade(migration_store):
    migration, connection = migration_store
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    added = connection.execute(
        sa.text(
            "SELECT category_id, slug, name, destination_url, destination_kind, "
            "author_name, author_url, sort_order, view_count, is_visible "
            "FROM catalog_projects WHERE id > 53 ORDER BY id"
        )
    ).all()
    assert added == [
        (
            1, "soulforge", "SOULFORGE 灵魂锻炉", "https://soulforge.glasden.top/", "external",
            "Glasden", "https://linux.do/u/glasden/summary", 12, 0, 1,
        ),
        (
            1, "achroma", "Achroma", "https://game.unsnow.online/ach/", "external",
            "snowunseasonl", "https://linux.do/u/snowunseasonl/summary", 13, 0, 1,
        ),
        (
            2, "pelican-rider", "鹈鹕骑手", "https://luoxiaoman.com/pelican-rider/", "external",
            "aqua33", "https://linux.do/u/aqua33/summary", 4, 0, 1,
        ),
        (
            3, "shousui", "守岁 · 猫与十二生肖", "https://shousui.vercel.app/", "external",
            "donghuyulong", "https://linux.do/u/donghuyulong/summary", 15, 0, 1,
        ),
        (
            3, "sketch-rts", "SKETCH RTS", "https://lexicalmathical.com/sketch-rts/", "external",
            "Jeffry", "https://linux.do/u/jeffry/summary", 16, 0, 1,
        ),
        (
            4, "bubble-tank", "泡泡坦克 Bubble Tanks", "https://bubble-tank.zackwill.space/",
            "external", "ZackWill", "https://linux.do/u/zackwill/summary", 0, 0, 1,
        ),
    ]
    descriptions = connection.execute(
        sa.text("SELECT description FROM catalog_projects WHERE id > 53 ORDER BY id")
    ).scalars().all()
    assert descriptions == [
        "像素风动作生存游戏，在裂隙中迎战成群敌人，通过装备合成、符文选择与锻炉强化构筑角色，挑战波次与首领。",
        "像素风地牢动作游戏，在灰白世界中探索房间、收集棱镜碎片，组合武器与元素强化，闪避弹幕并挑战首领，夺回失去的色彩。",
        "和一群鹈鹕骑车穿过海岸、花田、松林与港口小镇，吃鱼补充体力、躲避障碍，借助尾流与道具争先抵达终点。",
        "以十二生肖与天轮为核心的回合制策略游戏，通过猫牌出击、拨动时针和生肖羁绊布阵，在除夕之夜与猫一起守岁。",
        "即时战略游戏，指挥农民采集金矿、建设基地与兵营，训练部队并运用不同兵种和法术展开战斗。",
        "操控泡泡坦克射击敌人，收集泡泡成长进化，在无尽的泡泡海中探索与战斗。",
    ]
    # 追加后管理员改内容、归类和排序或隐藏游戏，重跑和回退均不能覆盖。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 4, name = '人工改名', "
        "destination_url = 'https://example.com/manual', description = '人工简介', "
        "author_name = '人工署名', author_url = 'https://example.com/author', "
        "sort_order = 80, is_visible = 0, view_count = 99 WHERE id > 53"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (54, 4), (55, 5)")
    expected = project_rows(connection)
    ratings = connection.execute(sa.text("SELECT * FROM catalog_ratings")).all()
    migration.upgrade()
    migration.downgrade()
    assert project_rows(connection) == expected
    assert connection.execute(sa.text("SELECT * FROM catalog_ratings")).all() == ratings


@pytest.mark.parametrize("slug,url", GAMES)
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_existing_url_alias_preserves_record_and_adds_other_games(
    migration_store, slug, url, trailing_slash
):
    migration, connection = migration_store
    existing_url = url if trailing_slash else url.rstrip("/")
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 50"),
        {"url": existing_url},
    )
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 9
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"), {"slug": slug}
    ) == 0


@pytest.mark.parametrize("slug,url", GAMES)
def test_existing_slug_preserves_manually_changed_destination(migration_store, slug, url):
    migration, connection = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET slug = :slug WHERE id = 51"), {"slug": slug}
    )
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 9
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"), {"url": url}
    ) == 0


@pytest.mark.parametrize("category", ["action", "racing", "rts", "shooting"])
def test_missing_any_category_stops_before_first_insert(migration_store, category):
    migration, connection = migration_store
    connection.execute(
        sa.text("DELETE FROM catalog_categories WHERE slug = :slug"), {"slug": category}
    )
    before = project_rows(connection)
    with pytest.raises(RuntimeError, match="requires catalog categories"):
        migration.upgrade()
    assert project_rows(connection) == before
