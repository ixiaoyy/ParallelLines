import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAMES = (
    (
        "shooting", "hollowmark", "HOLLOWMARK", "https://hollowmark.mindblown.ai/",
        "第一人称探索工业地下世界，寻找门禁卡、管理弹药并迎战敌人。",
        "Mindblown", "https://mindblown.ai/",
    ),
    (
        "shooting", "canyon-overdrive", "Canyon Overdrive",
        "https://canyonoverdrive.ai-created.com/",
        "驾驶战机穿越霓虹峡谷，以机炮、导弹与滚转突破封锁。",
        "Marco van Hylckama Vlieg / AI & Design", "https://x.com/AIandDesign",
    ),
    (
        "stages", "flight-1073", "Flight 1073", "https://flight1073.pages.dev/play/",
        "希伯来语航空恶搞小游戏，躲避餐车、完成限时任务并设法降落。",
        "Guy Eshel", "https://x.com/GuyEshel_",
    ),
    (
        "shooting", "foe-to-fleet", "FOE TO FLEET",
        "https://foe-to-fleet.miya333.chatgpt.site",
        "将击败的敌人收编为舰队，让伙伴协助攻防，撑过七波弹幕进攻。",
        "miya", "https://x.com/miya00907380",
    ),
    (
        "action", "moxride", "MoxRide", "https://www.moxride.com/",
        "在彩色城市中下坡滑板，通过磨轨、腾空动作与连续技巧得分。",
        "Moxazza / Moxazza Games", "https://www.moxride.com/",
    ),
    (
        "shooting", "midway-1942", "中途岛海战·空中突击", "https://ihca.cn/midway/",
        "与僚机迎战敌机并轰炸航母，掌握重力投弹落点，返回友舰补给。",
        "xilinnihao-afk / 一海千寻的AI实验室", "https://github.com/xilinnihao-afk",
    ),
    (
        "shooting", "sandline", "沙线行动 / SANDLINE", "https://ihca.cn/sandline/",
        "与 AI 队友进行单机 3 对 3 战术交战，运用掩体、枪械与手雷争夺爆破目标。",
        "xilinnihao-afk / 一海千寻的AI实验室", "https://github.com/xilinnihao-afk",
    ),
    (
        "action", "surge-for-oinja", "SURGE for Oinja", "https://oinja-game.vercel.app/",
        "自动攻击的第三人称生存游戏，组合电气技能和支援机械，修复设施并挑战首领。",
        "Olivia", "https://github.com/Olivia295",
    ),
    (
        "action", "jellyblob", "JellyBlob.win", "https://jellyblob.win/",
        "多人果冻竞技场，收集水滴、用尾迹围堵对手并跳跃避险。",
        "kvickan", "https://buymeacoffee.com/kvickan",
    ),
    (
        "puzzle", "astra-2048-eddy", "Astra 2048", "https://jianfan.app/2048/gpt/",
        "滑动合并相同数字并挑战 2048，收录作者模型对比中的 Astra 版本。",
        "Eddy", "https://x.com/ieddysun",
    ),
    (
        "puzzle", "the-fourth-knock", "The Fourth Knock",
        "https://nikhilsatishdesai.github.io/the-fourth-knock/play/",
        "探索 Cedar House、询问人物并组合线索，解开 2.5D 密室凶案。",
        "Nikhil Desai", "https://x.com/NikhilDesai_007",
    ),
    (
        "action", "saber-descent", "Saber / Descent", "https://vheissu.github.io/saber-battle/",
        "持能量剑探索五层地牢，以连击、格挡和冲刺击败守卫并前进。",
        "Dwayne", "https://x.com/CtrlAltDwayne",
    ),
    (
        "stages", "sulli-run", "Sulli RUN", "https://sulli-game.vercel.app/",
        "操控 3D 大猩猩在霓虹城市跑酷，换道、跳跃和滑行躲避障碍得分。",
        "Morteza", "https://x.com/Mortezabihzadeh",
    ),
)


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证整批收录，不读取或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_astra_updates", ROOT / "alembic/versions/0087_add_astra_updates.py"
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
            "(1, 'action'), (2, 'shooting'), (3, 'stages'), (4, 'puzzle')"
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
            "(52, 2, 'hidden-shooting', '隐藏射击游戏', 'https://example.com/c', 14, 0, 18), "
            "(53, 3, 'existing-stage', '已有闯关游戏', 'https://example.com/d', 3, 1, 8)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (50, 5), (51, 3), (52, 4)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def project_rows(connection):
    """读取给定内存连接的完整项目快照，按主键稳定排序供保留行为断言。"""

    return connection.execute(sa.text("SELECT * FROM catalog_projects ORDER BY id")).all()


def test_append_thirteen_games_and_preserve_repeat_and_downgrade(migration_store):
    migration, connection = migration_store
    assert migration.revision == "0087_add_astra_updates"
    assert migration.down_revision == "0086_add_external_games"
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    added = connection.execute(
        sa.text(
            "SELECT c.slug, p.slug, p.name, p.destination_url, p.description, "
            "p.author_name, p.author_url, p.destination_kind, p.sort_order, "
            "p.view_count, p.is_visible FROM catalog_projects p "
            "JOIN catalog_categories c ON c.id = p.category_id WHERE p.id > 53 ORDER BY p.id"
        )
    ).all()
    # 明确核对已确认的全部元数据；隐藏记录的顺序参与追加，空分类从零开始。
    expected_orders = (15, 16, 4, 17, 12, 18, 19, 13, 14, 0, 1, 15, 5)
    assert added == [
        (*game, "external", sort_order, 0, 1)
        for game, sort_order in zip(GAMES, expected_orders, strict=True)
    ]
    timestamps = connection.execute(
        sa.text("SELECT created_at, updated_at FROM catalog_projects WHERE id > 53")
    ).all()
    assert len(set(timestamps)) == 1
    assert timestamps[0][0] and timestamps[0][0] == timestamps[0][1]

    # 管理员改内容、归类、排序和隐藏状态后，重跑与回退均保留记录及浏览评分。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 2, name = '人工改名', "
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


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_existing_url_alias_preserves_record_and_adds_other_games(
    migration_store, game, trailing_slash
):
    migration, connection = migration_store
    slug, url = game[1], game[3]
    existing_url = f"{url.rstrip('/')}/" if trailing_slash else url.rstrip("/")
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 50"),
        {"url": existing_url},
    )
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 16
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"), {"slug": slug}
    ) == 0


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
def test_existing_slug_preserves_manually_changed_destination(migration_store, game):
    migration, connection = migration_store
    slug, url = game[1], game[3]
    connection.execute(
        sa.text("UPDATE catalog_projects SET slug = :slug WHERE id = 51"), {"slug": slug}
    )
    before = project_rows(connection)
    migration.upgrade()
    assert project_rows(connection)[:4] == before
    assert len(project_rows(connection)) == 16
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"), {"url": url}
    ) == 0


@pytest.mark.parametrize("category", ["action", "shooting", "stages", "puzzle"])
def test_missing_any_category_stops_before_first_insert(migration_store, category):
    migration, connection = migration_store
    connection.execute(
        sa.text("DELETE FROM catalog_categories WHERE slug = :slug"), {"slug": category}
    )
    before = project_rows(connection)
    with pytest.raises(RuntimeError, match="requires catalog categories"):
        migration.upgrade()
    assert project_rows(connection) == before


def test_empty_categories_append_in_order_from_zero(migration_store):
    migration, connection = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings")
    connection.exec_driver_sql("DELETE FROM catalog_projects")
    migration.upgrade()
    orders = connection.execute(
        sa.text(
            "SELECT category_id, sort_order, view_count FROM catalog_projects "
            "ORDER BY category_id, sort_order"
        )
    ).all()
    assert orders == [
        (category_id, sort_order, 0)
        for category_id, count in ((1, 4), (2, 5), (3, 2), (4, 2))
        for sort_order in range(count)
    ]
