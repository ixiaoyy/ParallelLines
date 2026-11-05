import importlib.util
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAMES = (
    (
        "romance",
        "her-tears-were-my-light",
        "她的眼泪曾是我的光芒（Her Tears Were My Light）",
        "https://html-classic.itch.zone/html/18220499/index.html?v=1783279519",
        "支持简体中文的恋爱视觉小说：扮演时间，回溯故事节点，尝试帮助空间摆脱孤独；含轻度恐怖元素。免费网页版不含付费下载版的部分额外功能。",
        "NomnomNami / Emmit / LydianChord",
        "https://nomnomnami.itch.io/",
    ),
    (
        "farming",
        "farmhand",
        "Farmhand",
        "https://jeremyckahn.github.io/farmhand/",
        "英文种田经营游戏：购买种子、种植、浇水并出售作物，结合每日变化的市场价格经营农场；可单人游玩，联网模式为可选功能。",
        "Jeremy Kahn / Farmhand contributors",
        "https://jeremyckahn.itch.io/",
    ),
    (
        "horror",
        "exhibit-of-sorrows",
        "Exhibit of Sorrows",
        "https://html-classic.itch.zone/html/14611877/index.html",
        "英文马戏团展馆互动恐怖短篇：探索手绘展品，完成互动并寻找出口；包含心理恐怖、小丑惊吓与伤害表现。",
        "Maxim Tsai (adayofjoy) / Theresa Kao",
        "https://adayofjoy.itch.io/",
    ),
    (
        "romance",
        "known-unknowns",
        "Known Unknowns",
        "https://known.zone/one",
        "英文校园捉鬼与恋爱文字冒险，围绕旧友情、感情纠葛和神秘事件展开。四章完整免费，此入口从第一章开始；阅读量较大，含粗口及药物相关话题。",
        "Brendan Patrick Hennessy / Izzy Marbella",
        "https://bphennessy.com/",
    ),
    (
        "rpg",
        "crosscode-demo",
        "CrossCode（网页试玩版）",
        "https://www.cross-code.com/en/start",
        "英文像素动作角色扮演试玩，结合即时战斗、投球机关与解谜。"
        "此入口为官方旧版网页 Demo，非付费完整版。",
        "Radical Fish Games",
        "https://www.radicalfishgames.com/",
    ),
)
EXPECTED_AUTHOR = "Brendan Patrick Hennessy / Izzy Marbella"
OLD_AUTHOR_URL = "https://bphennessy.itch.io/birdland"
NEW_AUTHOR_URL = "https://bphennessy.com/"
AI_TABLES = (
    "catalog_ai_rating_rules",
    "catalog_ai_rating_weight_schemes",
    "catalog_ai_rating_batches",
    "catalog_ai_game_assessments",
    "catalog_ai_assessment_dimensions",
    "catalog_ai_assessment_human_reviews",
)


@pytest.fixture
def migration_store(monkeypatch):
    """使用内存 SQLite 和非零评分哨兵，不读取配置或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_five_browser_games",
        ROOT / "alembic/versions/0108_add_five_browser_games.py",
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
            "(1, 'romance'), (2, 'farming'), (3, 'horror'), (4, 'rpg'), (5, 'other')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT COLLATE NOCASE, "
            "author_url TEXT COLLATE NOCASE, icon_upload_id INTEGER, sort_order INTEGER, "
            "is_visible BOOLEAN, created_at TEXT, updated_at TEXT, "
            "view_count BIGINT NOT NULL DEFAULT 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_projects VALUES "
            "(41, 1, 'birdland', 'BIRDLAND人工标题', 'https://birdland.camp/', 'external', "
            "'保留旧简介', 'Brendan Patrick Hennessy / Izzy Marbella', "
            "'https://bphennessy.itch.io/birdland', 123, 7, 1, '旧创建时间', '人工修改时间', 77), "
            "(42, 1, 'hidden-romance', '隐藏恋爱', 'https://example.com/r', 'external', "
            "NULL, NULL, NULL, NULL, 11, 0, '旧创建时间', '旧修改时间', 41), "
            "(43, 2, 'hidden-farming', '隐藏种田', 'https://example.com/f', 'external', "
            "NULL, NULL, NULL, NULL, 14, 0, '旧创建时间', '旧修改时间', 19), "
            "(44, 3, 'hidden-horror', '隐藏恐怖', 'https://example.com/h', 'external', "
            "NULL, NULL, NULL, NULL, 4, 0, '旧创建时间', '旧修改时间', 38), "
            "(45, 4, 'hidden-rpg', '隐藏角色扮演', 'https://example.com/p', 'external', "
            "NULL, NULL, NULL, NULL, 8, 0, '旧创建时间', '旧修改时间', 11), "
            "(50, 5, 'manual-other', '人工其他项目', 'https://example.com/m', 'external', "
            "'人工简介', '人工作者', 'https://example.com/author', 456, 100, 0, "
            "'旧创建时间', '旧修改时间', 12), "
            "(51, 5, 'unrelated-visible', '无关项目', 'https://example.com/u', 'internal', "
            "'无关简介', '无关作者', 'https://example.com/unrelated', NULL, 4, 1, "
            "'旧创建时间', '旧修改时间', 56)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (41, 5), (45, 4), (50, 3)")
        # AI 表放置非零原值哨兵，只验证本批绝不写入，不冒充完整 AI schema 集成回归。
        for table in AI_TABLES:
            connection.exec_driver_sql(
                f"CREATE TABLE {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                sa.text(f"INSERT INTO {table} VALUES (:id, :payload)"),
                {"id": f"original-{table}", "payload": '{"score": 8.25}'},
            )
        statements = []
        sa.event.listen(
            connection, "before_cursor_execute",
            lambda _conn, _cursor, statement, _params, _ctx, _many: statements.append(statement),
        )
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection, statements
    engine.dispose()


def snapshot(connection):
    """按主键读取全部项目、用户评分与 AI 哨兵，比较本批允许字段之外的原值。"""

    return {
        table: [dict(row) for row in connection.execute(
            sa.text(f"SELECT * FROM {table} ORDER BY {order}")
        ).mappings()]
        for table, order in (
            ("catalog_projects", "id"), ("catalog_ratings", "project_id, score"),
            *((table, "id") for table in AI_TABLES),
        )
    }


def expected_old_records(before):
    """仅原始署名与原作者 URL 同时精确匹配时，允许更新原 BIRDLAND 一字段。"""

    expected = [dict(row) for row in before["catalog_projects"]]
    for row in expected:
        if (row["slug"] == "birdland" and row["author_name"] == EXPECTED_AUTHOR
                and row["author_url"] == OLD_AUTHOR_URL):
            row["author_url"] = NEW_AUTHOR_URL
    return expected


def assert_old_data_preserved(before, after):
    """核对全部旧项目及非零评分，不把新增项目算作旧记录变化。"""

    old_ids = {row["id"] for row in before["catalog_projects"]}
    assert [row for row in after["catalog_projects"] if row["id"] in old_ids] == (
        expected_old_records(before)
    )
    for table in ("catalog_ratings", *AI_TABLES):
        assert after[table] == before[table]


def test_exact_five_games_and_one_legacy_author_field(migration_store):
    migration, connection, statements = migration_store
    assert migration.revision == "0108_add_five_browser_games"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0107_add_birdland"
    before = snapshot(connection)
    statements.clear()
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 12
    assert_old_data_preserved(before, after)
    assert sum(sql.startswith("INSERT INTO catalog_projects ") for sql in statements) == 5
    updates = [sql for sql in statements if sql.startswith("UPDATE ")]
    assert len(updates) == 1
    assert updates[0].startswith("UPDATE catalog_projects SET author_url =")
    added = connection.execute(
        sa.text(
            "SELECT c.slug, p.slug, p.name, p.destination_url, p.description, "
            "p.author_name, p.author_url, p.destination_kind, p.icon_upload_id, "
            "p.sort_order, p.view_count, p.is_visible FROM catalog_projects p "
            "JOIN catalog_categories c ON c.id = p.category_id WHERE p.id > 51 ORDER BY p.id"
        )
    ).all()
    # 精确核对合同；恋爱两款依次追加，原站评分不生成站内用户或 AI 评分。
    assert added == [
        (*game, "external", None, order, 0, 1)
        for game, order in zip(GAMES, (12, 15, 5, 13, 9), strict=True)
    ]
    times = connection.execute(
        sa.text("SELECT created_at, updated_at FROM catalog_projects WHERE id > 51")
    ).all()
    assert len(set(times)) == 1 and times[0][0] and times[0][0] == times[0][1]
    assert connection.execute(
        sa.text(
            "SELECT author_name, author_url, COUNT(*) FROM catalog_projects "
            "WHERE slug IN ('birdland', 'known-unknowns') GROUP BY author_name, author_url"
        )
    ).all() == [(EXPECTED_AUTHOR, NEW_AUTHOR_URL, 2)]


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
@pytest.mark.parametrize("trailing_slash", [False, True])
@pytest.mark.parametrize("visible", [False, True])
def test_existing_url_in_other_category_is_not_overwritten(
    migration_store, game, trailing_slash, visible
):
    migration, connection, _statements = migration_store
    parts = urlsplit(game[3])
    path = parts.path.rstrip("/") + ("/" if trailing_slash else "")
    url = urlunsplit(parts._replace(path=path))
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET destination_url = :url, is_visible = :visible "
            "WHERE id = 50"
        ), {"url": url, "visible": visible},
    )
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 11
    assert_old_data_preserved(before, after)
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"), {"slug": game[1]}
    ) == 0


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
def test_existing_slug_with_manual_url_stays_hidden_and_unchanged(migration_store, game):
    migration, connection, _statements = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET slug = :slug WHERE id = 50"), {"slug": game[1]}
    )
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 11
    assert_old_data_preserved(before, after)
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"),
        {"url": game[3]},
    ) == 0


@pytest.mark.parametrize("url", [
    "https://html-classic.itch.zone/html/18220499/index.html",
    "https://html-classic.itch.zone/html/18220499/index.html?v=1783279520",
    "https://html-classic.itch.zone/html/18220499/index.html?v=1783279519/",
])
def test_nami_cache_query_is_not_ignored_for_deduplication(migration_store, url):
    migration, connection, _statements = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 50"), {"url": url}
    )
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 12
    assert_old_data_preserved(before, after)
    assert connection.scalar(
        sa.text("SELECT destination_url FROM catalog_projects WHERE slug = :slug"),
        {"slug": "her-tears-were-my-light"},
    ) == GAMES[0][3]


@pytest.mark.parametrize("existing_url", [
    "https://html-classic.itch.zone/html/18220499/index.html?v=1783279519",
    "https://html-classic.itch.zone/html/18220499/index.html/?v=1783279519",
])
def test_nami_same_query_with_path_slash_variants_keeps_existing_record(
    migration_store, existing_url
):
    migration, connection, _statements = migration_store
    # 独立固定期望地址；path 变化可防重，不能借查询串内多一个斜线冒充同一形式。
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 50"),
        {"url": existing_url},
    )
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 11
    assert_old_data_preserved(before, after)
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"),
        {"slug": "her-tears-were-my-light"},
    ) == 0


@pytest.mark.parametrize(("author_name", "author_url", "visible"), [
    (EXPECTED_AUTHOR, OLD_AUTHOR_URL, False),
    (EXPECTED_AUTHOR, NEW_AUTHOR_URL, True),
    (EXPECTED_AUTHOR, "https://example.com/manual", True),
    ("人工署名", OLD_AUTHOR_URL, False),
    (EXPECTED_AUTHOR, OLD_AUTHOR_URL + "/", True),
    (EXPECTED_AUTHOR.upper(), OLD_AUTHOR_URL, True),
    (EXPECTED_AUTHOR, OLD_AUTHOR_URL.upper(), True),
    (EXPECTED_AUTHOR, None, True),
    (None, OLD_AUTHOR_URL, True),
])
def test_birdland_author_correction_requires_exact_original_fields(
    migration_store, author_name, author_url, visible
):
    migration, connection, _statements = migration_store
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET author_name = :name, author_url = :url, "
            "is_visible = :visible WHERE slug = 'birdland'"
        ), {"name": author_name, "url": author_url, "visible": visible},
    )
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert_old_data_preserved(before, after)
    assert len(after["catalog_projects"]) == 12


def test_missing_old_birdland_is_not_recreated(migration_store):
    migration, connection, _statements = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE slug = 'birdland'")
    before = snapshot(connection)
    migration.upgrade()
    assert_old_data_preserved(before, snapshot(connection))
    assert connection.scalar(
        sa.text("SELECT COUNT(*) FROM catalog_projects WHERE slug = 'birdland'")
    ) == 0


def test_repeat_and_noop_downgrade_preserve_later_manual_state(migration_store):
    migration, connection, _statements = migration_store
    migration.upgrade()
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 5, name = '人工改名', "
        "destination_url = '/play/manual', destination_kind = 'internal', "
        "description = '人工简介', author_name = '人工署名', "
        "author_url = 'https://example.com/manual', icon_upload_id = 999, "
        "sort_order = 88, is_visible = 0, view_count = 91, updated_at = '人工修改时间' "
        "WHERE id > 51"
    )
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET author_url = 'https://example.com/later-author' "
        "WHERE slug = 'birdland'"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (52, 4)")
    expected = snapshot(connection)
    migration.upgrade()
    assert snapshot(connection) == expected
    migration.downgrade()
    assert snapshot(connection) == expected
    migration.upgrade()
    assert snapshot(connection) == expected


@pytest.mark.parametrize("category", ["romance", "farming", "horror", "rpg"])
def test_missing_category_prevents_all_writes_including_author_fix(migration_store, category):
    migration, connection, statements = migration_store
    connection.execute(
        sa.text("DELETE FROM catalog_categories WHERE slug = :slug"), {"slug": category}
    )
    before = snapshot(connection)
    statements.clear()
    with pytest.raises(
        RuntimeError, match="0108 requires catalog categories romance, farming, horror and rpg"
    ):
        migration.upgrade()
    assert not any(sql.startswith(("INSERT ", "UPDATE ")) for sql in statements)
    assert snapshot(connection) == before


def test_empty_categories_start_at_zero_and_romance_advances_twice(migration_store):
    migration, connection, _statements = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings WHERE project_id < 50")
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE category_id IN (1, 2, 3, 4)")
    before = snapshot(connection)
    migration.upgrade()
    assert_old_data_preserved(before, snapshot(connection))
    assert connection.execute(
        sa.text(
            "SELECT slug, category_id, sort_order, view_count FROM catalog_projects "
            "WHERE id > 51 ORDER BY id"
        )
    ).all() == [
        (game[1], category, order, 0)
        for game, category, order in zip(GAMES, (1, 2, 3, 1, 4), (0, 0, 0, 1, 0), strict=True)
    ]


def test_insert_failure_rolls_back_author_fix_and_previous_inserts(migration_store):
    migration, connection, _statements = migration_store
    before = snapshot(connection)
    insert_count = 0

    def fail_third_insert(_conn, _cursor, statement, parameters, _ctx, _many):
        nonlocal insert_count
        if statement.startswith("INSERT INTO catalog_projects "):
            insert_count += 1
            if insert_count == 3:
                raise sa.exc.OperationalError(
                    statement, parameters, RuntimeError("simulated insert failure")
                )

    sa.event.listen(connection, "before_cursor_execute", fail_third_insert)
    with pytest.raises(sa.exc.OperationalError, match="simulated insert failure"):
        migration.upgrade()
    assert insert_count == 3
    assert snapshot(connection) == before
