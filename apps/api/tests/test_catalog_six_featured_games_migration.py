import importlib.util
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
GAMES = (
    (
        "puzzle", "dragonsweeper", "Dragonsweeper",
        "https://html-classic.itch.zone/html/12786123/index.html",
        "Daniel Benmergui", "https://danielben.itch.io/",
    ),
    (
        "puzzle", "growmi", "Growmi",
        "https://html-classic.itch.zone/html/7612919/index.html",
        "Carlos Pedroso / Inês Ribeiro", "https://carlospedroso.itch.io/",
    ),
    (
        "simulation", "sort-the-court", "Sort the Court!",
        "https://html-classic.itch.zone/html/347310/index.html",
        "Graeme Borland / amymja / Bogdan Rybak", "https://graebor.itch.io/sort-the-court",
    ),
    (
        "cards", "solitomb", "Solitomb",
        "https://html-classic.itch.zone/html/12290587/index.html",
        "Jakub Wasilewski / Chris Donnelly", "https://krajzeg.itch.io/solitomb",
    ),
    (
        "rts", "slipways-classic", "Slipways Classic",
        "https://html-classic.itch.zone/html/3076366/index.html",
        "Jakub Wasilewski / Gruber", "https://krajzeg.itch.io/slipways",
    ),
    (
        "cards", "die-in-the-dungeon-classic", "Die in the Dungeon CLASSIC",
        "https://html-classic.itch.zone/html/7330268/"
        "Die%20in%20the%20Dungeon%201.6.2f%20%5BWEB%5D/index.html",
        "Alarts / SexyBuggy / Jaun / aghsshagahdjjdhwhwureuduu",
        "https://alarts.itch.io/die-in-the-dungeon",
    ),
)
AI_TABLES = (
    "catalog_ai_rating_rules", "catalog_ai_rating_weight_schemes", "catalog_ai_rating_batches",
    "catalog_ai_game_assessments", "catalog_ai_assessment_dimensions",
    "catalog_ai_assessment_human_reviews",
)


@pytest.fixture
def migration_store(monkeypatch):
    """独立内存 SQLite 放入真实形态字段及评分哨兵，不读取项目运行配置。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_six_featured_games", ROOT / "alembic/versions/0110_add_six_featured_games.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES (1, 'puzzle'), (2, 'simulation'), "
            "(3, 'cards'), (4, 'rts'), (6, 'other')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT, author_url TEXT, icon_upload_id INTEGER, "
            "sort_order INTEGER, is_visible BOOLEAN, created_at TEXT, updated_at TEXT, "
            "view_count BIGINT NOT NULL DEFAULT 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_projects VALUES "
            "(40, 1, 'old-puzzle', '旧解谜', 'https://example.com/puzzle', 'external', "
            "'旧简介', '旧作者', 'https://example.com/author', 123, 7, 1, "
            "'旧时间', '人工时间', 77), "
            "(41, 1, 'hidden-puzzle', '隐藏解谜', 'https://example.com/p', 'external', "
            "NULL, NULL, NULL, NULL, 11, 0, '旧时间', '旧时间', 41), "
            "(42, 2, 'hidden-simulation', '隐藏经营', 'https://example.com/s', 'external', "
            "NULL, NULL, NULL, NULL, 14, 0, '旧时间', '旧时间', 19), "
            "(43, 3, 'hidden-cards', '隐藏卡牌', 'https://example.com/c', 'external', "
            "NULL, NULL, NULL, NULL, 4, 0, '旧时间', '旧时间', 38), "
            "(44, 4, 'hidden-rts', '隐藏策略', 'https://example.com/r', 'external', "
            "NULL, NULL, NULL, NULL, 8, 0, '旧时间', '旧时间', 11), "
            "(50, 6, 'manual-other', '人工其他项目', 'https://example.com/m', 'external', "
            "'人工简介', '人工作者', 'https://example.com/manual', 456, 100, 0, "
            "'旧创建时间', '人工修改时间', 12), "
            "(51, 6, 'unrelated-visible', '无关项目', '/play/manual', 'internal', "
            "'无关简介', '无关作者', 'https://example.com/unrelated', NULL, 4, 1, "
            "'旧创建时间', '旧修改时间', 56)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (40, 5), (44, 4), (50, 3)")
        # 非零 AI 哨兵只检查本批不碰评分资料，不冒充 AI schema 的集成验证。
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
    """按主键快照全部旧资料与非零评分，用于精确比较不变项。"""

    return {
        table: [dict(row) for row in connection.execute(
            sa.text(f"SELECT * FROM {table} ORDER BY {order}")
        ).mappings()]
        for table, order in (
            ("catalog_categories", "id"), ("catalog_projects", "id"),
            ("catalog_ratings", "project_id, score"), *((table, "id") for table in AI_TABLES),
        )
    }


def assert_old_data_preserved(before, after):
    """旧分类、全部旧项目和评分必须逐字段不变，不仅检查可见记录或总数。"""

    old_ids = {row["id"] for row in before["catalog_projects"]}
    assert [row for row in after["catalog_projects"] if row["id"] in old_ids] == (
        before["catalog_projects"]
    )
    for table in ("catalog_categories", "catalog_ratings", *AI_TABLES):
        assert after[table] == before[table]


def test_exact_six_games_and_all_old_data_preserved(migration_store):
    migration, connection, statements = migration_store
    assert migration.revision == "0110_add_six_featured_games"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0109_birdland_localized_entry"
    before = snapshot(connection)
    statements.clear()
    migration.upgrade()
    writes = [sql for sql in statements if sql.startswith(("INSERT ", "UPDATE ", "DELETE "))]
    assert len(writes) == 6
    assert all(sql.startswith("INSERT INTO catalog_projects ") for sql in writes)
    # 分类一次批量核齐；逐款单条防重与单分类 MAX 排序，没有额外全库读取或写入。
    selects = [sql for sql in statements if sql.startswith("SELECT ")]
    assert len(selects) == 13
    assert "WHERE slug IN ('puzzle', 'simulation', 'cards', 'rts')" in selects[0]
    assert sum(" LIMIT 1" in sql for sql in selects) == 6
    assert sum("MAX(sort_order)" in sql for sql in selects) == 6
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 13
    assert_old_data_preserved(before, after)
    added = connection.execute(sa.text(
        "SELECT c.slug, p.slug, p.name, p.destination_url, p.author_name, p.author_url, "
        "p.destination_kind, p.icon_upload_id, p.sort_order, p.view_count, p.is_visible "
        "FROM catalog_projects p JOIN catalog_categories c ON c.id = p.category_id "
        "WHERE p.id > 51 ORDER BY p.id"
    )).all()
    assert added == [
        (*game, "external", None, order, 0, 1)
        for game, order in zip(GAMES, (12, 13, 15, 5, 9, 6), strict=True)
    ]
    times = connection.execute(sa.text(
        "SELECT created_at, updated_at FROM catalog_projects WHERE id > 51"
    )).all()
    assert len(set(times)) == 1 and times[0][0] and times[0][0] == times[0][1]
    descriptions = dict(connection.execute(sa.text(
        "SELECT slug, description FROM catalog_projects WHERE id > 51"
    )).all())
    assert all(0 < len(description) <= 300 for description in descriptions.values())
    assert "英文" in descriptions["sort-the-court"]
    assert "手机与其他语言更新版另有入口" in descriptions["sort-the-court"]
    for slug in ("solitomb", "slipways-classic"):
        assert "PICO-8" in descriptions[slug] and "扩充版" in descriptions[slug]
    assert "英文骰子构筑与回合制地牢" in descriptions["die-in-the-dungeon-classic"]
    assert "Classic 旧版网页游戏，非另售商业完整版" in (
        descriptions["die-in-the-dungeon-classic"]
    )


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
@pytest.mark.parametrize("trailing_slash", [False, True])
@pytest.mark.parametrize("visible", [False, True])
def test_existing_url_in_other_category_is_not_overwritten(
    migration_store, game, trailing_slash, visible,
):
    migration, connection, _statements = migration_store
    parts = urlsplit(game[3])
    url = urlunsplit(parts._replace(path=parts.path.rstrip("/") + ("/" if trailing_slash else "")))
    connection.execute(sa.text(
        "UPDATE catalog_projects SET destination_url = :url, is_visible = :visible WHERE id = 50"
    ), {"url": url, "visible": visible})
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 12
    assert_old_data_preserved(before, after)
    assert connection.scalar(sa.text(
        "SELECT COUNT(*) FROM catalog_projects WHERE slug = :slug"
    ), {"slug": game[1]}) == 0


@pytest.mark.parametrize("game", GAMES, ids=[game[1] for game in GAMES])
def test_existing_slug_with_manual_url_stays_hidden_and_unchanged(migration_store, game):
    migration, connection, _statements = migration_store
    connection.execute(sa.text(
        "UPDATE catalog_projects SET slug = :slug WHERE id = 50"
    ), {"slug": game[1]})
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 12
    assert_old_data_preserved(before, after)
    assert connection.scalar(sa.text(
        "SELECT COUNT(*) FROM catalog_projects WHERE destination_url = :url"
    ), {"url": game[3]}) == 0


@pytest.mark.parametrize("suffix", ["?v=1", "?v=1/", "#manual"])
def test_distinct_query_or_fragment_is_not_silently_merged(migration_store, suffix):
    migration, connection, _statements = migration_store
    connection.execute(sa.text(
        "UPDATE catalog_projects SET destination_url = :url WHERE id = 50"
    ), {"url": GAMES[0][3] + suffix})
    before = snapshot(connection)
    migration.upgrade()
    after = snapshot(connection)
    assert len(after["catalog_projects"]) == 13
    assert_old_data_preserved(before, after)
    assert connection.scalar(sa.text(
        "SELECT destination_url FROM catalog_projects WHERE slug = 'dragonsweeper'"
    )) == GAMES[0][3]


def test_repeat_and_noop_downgrade_preserve_later_manual_state(migration_store):
    migration, connection, _statements = migration_store
    migration.upgrade()
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET category_id = 6, name = '人工改名', "
        "destination_url = '/play/later', destination_kind = 'internal', "
        "description = '人工简介', author_name = '人工署名', "
        "author_url = 'https://example.com/later', icon_upload_id = 999, "
        "sort_order = 88, is_visible = 0, view_count = 91, updated_at = '人工修改时间' "
        "WHERE id > 51"
    )
    connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (52, 4)")
    expected = snapshot(connection)
    migration.upgrade()
    assert snapshot(connection) == expected
    migration.downgrade()
    assert snapshot(connection) == expected


@pytest.mark.parametrize("category", ["puzzle", "simulation", "cards", "rts"])
def test_missing_category_prevents_all_writes(migration_store, category):
    migration, connection, statements = migration_store
    connection.execute(sa.text(
        "DELETE FROM catalog_categories WHERE slug = :slug"
    ), {"slug": category})
    before = snapshot(connection)
    statements.clear()
    with pytest.raises(RuntimeError, match="0110 requires catalog categories"):
        migration.upgrade()
    assert not any(sql.startswith(("INSERT ", "UPDATE ", "DELETE ")) for sql in statements)
    assert snapshot(connection) == before


def test_empty_categories_start_at_zero_and_shared_categories_advance_twice(migration_store):
    migration, connection, _statements = migration_store
    connection.exec_driver_sql("DELETE FROM catalog_ratings WHERE project_id < 50")
    connection.exec_driver_sql("DELETE FROM catalog_projects WHERE category_id <> 6")
    before = snapshot(connection)
    migration.upgrade()
    assert_old_data_preserved(before, snapshot(connection))
    assert connection.execute(sa.text(
        "SELECT slug, category_id, sort_order, view_count FROM catalog_projects "
        "WHERE id > 51 ORDER BY id"
    )).all() == [
        (game[1], category, order, 0)
        for game, category, order in zip(GAMES, (1, 1, 2, 3, 4, 3), (0, 1, 0, 0, 0, 1), strict=True)
    ]


@pytest.mark.parametrize("failure_position", range(1, 7))
def test_insert_failure_rolls_back_all_previous_inserts(migration_store, failure_position):
    migration, connection, _statements = migration_store
    before = snapshot(connection)
    insert_count = 0

    def fail_insert(_conn, _cursor, statement, parameters, _ctx, _many):
        nonlocal insert_count
        if statement.startswith("INSERT INTO catalog_projects "):
            insert_count += 1
            if insert_count == failure_position:
                raise sa.exc.OperationalError(
                    statement, parameters, RuntimeError("simulated insert failure"),
                )

    sa.event.listen(connection, "before_cursor_execute", fail_insert)
    with pytest.raises(sa.exc.OperationalError, match="simulated insert failure"):
        migration.upgrade()
    assert insert_count == failure_position
    assert snapshot(connection) == before
