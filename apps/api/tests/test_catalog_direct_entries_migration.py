import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
DIRECT = (
    (
        "gd-spectrum", "https://gd.games/mrmeeseeks/spectrum",
        "https://html-classic.itch.zone/html/7294044/Spectrum%201.1/index.html?v=1782787944",
    ),
    (
        "itch-six-cats-under", "https://teambeanloop.itch.io/six-cats-under",
        "https://html-classic.itch.zone/html/2267583/index.html",
    ),
    (
        "itch-the-final-earth-2", "https://flori9.itch.io/the-final-earth-2",
        "https://html-classic.itch.zone/html/1995721-336862/index.html",
    ),
)
HIDDEN = (
    ("gd-fungi-run", "https://gd.games/shehan/fungirun"),
    ("gd-super-chicken-td", "https://gd.games/texugozap/super-chicken-td"),
    ("gd-golf-adventures-2", "https://gd.games/zachjukamashi/golf-adventures-2"),
    ("gd-helicopter-sos", "https://gd.games/malaspina/helicopter-sos"),
    ("gd-rocket-racers", "https://gd.games/tulenvakiproductions/rocket-racers"),
    ("astra-940973d6b1805a52c1f0", "https://playableworld.itch.io/mystery-town"),
    ("astra-ca4e89010438edf3221e", "https://wavedash.com/games/canteen-crashers"),
    ("astra-0a5696802efe2cf4eb0b", "https://wavedash.com/games/must-make-paperclips"),
    ("astra-0751dc4e0b9b7bc13c1f", "https://wavedash.com/games/dungeon-of-astra"),
)
TARGETS = tuple(entry[0] for entry in DIRECT + HIDDEN)
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
    """只建独立内存 SQLite；任意主键、完整项目字段和评分哨兵不连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_direct_entries", ROOT / "alembic/versions/0105_catalog_direct_entries.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT, author_url TEXT, icon_upload_id INTEGER, "
            "sort_order INTEGER, is_visible BOOLEAN, created_at TEXT, updated_at TEXT, "
            "view_count BIGINT NOT NULL DEFAULT 0)"
        )
        entries = [*DIRECT, *HIDDEN, ("unrelated-visible", "https://example.com/a"),
                   ("unrelated-hidden", "https://example.com/b")]
        for index, entry in enumerate(entries):
            connection.execute(
                sa.text(
                    "INSERT INTO catalog_projects VALUES (:id, :category_id, :slug, :name, "
                    ":url, :kind, :description, :author, :author_url, :icon_id, :sort_order, "
                    ":visible, :created_at, :updated_at, :views)"
                ),
                {
                    "id": 9000 + index * 37, "category_id": index % 3 + 1, "slug": entry[0],
                    "name": f"人工名称{index}", "url": entry[1], "kind": "external",
                    "description": f"人工简介{index}", "author": f"作者{index}",
                    "author_url": f"https://example.com/author/{index}",
                    "icon_id": None if index % 2 else 700 + index,
                    "sort_order": 90 - index, "visible": entry[0] != "unrelated-hidden",
                    "created_at": f"旧创建时间{index}", "updated_at": f"人工修改时间{index}",
                    "views": index * 113 + 41,
                },
            )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (id INTEGER PRIMARY KEY, project_id INTEGER, "
            "ip_digest TEXT, score INTEGER, created_at TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_ratings VALUES "
            "(1, 9000, 'visitor-a', 5, '原评分时间'), (2, 9111, 'visitor-b', 3, '另一评分时间')"
        )
        # AI 表只放不应被写入的原值哨兵；这不是完整 AI schema 的集成测试。
        for table in AI_TABLES:
            connection.exec_driver_sql(
                f"CREATE TABLE {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                sa.text(f"INSERT INTO {table} VALUES (:id, :payload)"),
                {"id": f"original-{table}", "payload": '{"original_score": 8.25}'},
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
    """读取全部项目及用户/AI 评分原值，用于验证仅授权字段变化和事务失败回滚。"""

    return {
        table: [dict(row) for row in connection.execute(
            sa.text(f"SELECT * FROM {table} ORDER BY id")
        ).mappings()]
        for table in ("catalog_projects", "catalog_ratings", *AI_TABLES)
    }


def expected_snapshot(before):
    """依据需求独立构造唯一允许的三条入口与九条隐藏变化，其余字节保持原值。"""

    expected = {table: [dict(row) for row in rows] for table, rows in before.items()}
    direct_urls = {entry[0]: entry[2] for entry in DIRECT}
    hidden_slugs = {entry[0] for entry in HIDDEN}
    for row in expected["catalog_projects"]:
        if row["slug"] in direct_urls:
            row["destination_url"] = direct_urls[row["slug"]]
        if row["slug"] in hidden_slugs:
            row["is_visible"] = 0
    return expected


def test_only_three_urls_and_nine_visibility_flags_change(migration_store):
    migration, connection, statements = migration_store
    assert migration.revision == "0105_catalog_direct_entries"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0104_add_classic_web_games"
    before = snapshot(connection)
    statements.clear()
    migration.upgrade()
    updates = [sql for sql in statements if sql.startswith("UPDATE ")]
    assert len(updates) == 12
    assert sum(
        sql.startswith("UPDATE catalog_projects SET destination_url =") for sql in updates
    ) == 3
    assert sum(sql.startswith("UPDATE catalog_projects SET is_visible =") for sql in updates) == 9
    assert not any(
        sql.startswith(("INSERT ", "DELETE ", "CREATE ", "ALTER ", "DROP ")) for sql in statements
    )
    assert snapshot(connection) == expected_snapshot(before)


def test_repeat_and_non_destructive_downgrade_do_not_write(migration_store):
    migration, connection, statements = migration_store
    migration.upgrade()
    expected = snapshot(connection)
    statements.clear()
    migration.upgrade()
    migration.downgrade()
    assert not any(sql.startswith("UPDATE ") for sql in statements)
    assert snapshot(connection) == expected
    # 回退也不得覆盖收录调整之后的人工入口或重新展示已隐藏项目。
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET destination_url = 'https://example.com/manual' "
        "WHERE slug = 'gd-spectrum'"
    )
    expected = snapshot(connection)
    migration.downgrade()
    assert snapshot(connection) == expected


@pytest.mark.parametrize("entry", DIRECT, ids=[entry[0] for entry in DIRECT])
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_original_url_trailing_slash_variants_are_accepted(migration_store, entry, trailing_slash):
    migration, connection, _statements = migration_store
    slug, old_url, _new_url = entry
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE slug = :slug"),
        {"slug": slug, "url": old_url.rstrip("/") + ("/" if trailing_slash else "")},
    )
    before = snapshot(connection)
    migration.upgrade()
    assert snapshot(connection) == expected_snapshot(before)


@pytest.mark.parametrize("entry", DIRECT, ids=[entry[0] for entry in DIRECT])
def test_already_direct_url_is_not_updated_again(migration_store, entry):
    migration, connection, statements = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE slug = :slug"),
        {"slug": entry[0], "url": entry[2]},
    )
    before = snapshot(connection)
    statements.clear()
    migration.upgrade()
    assert sum(sql.startswith("UPDATE ") for sql in statements) == 11
    assert snapshot(connection) == expected_snapshot(before)


def test_preexisting_hidden_flags_and_hidden_game_urls_are_preserved(migration_store):
    migration, connection, statements = migration_store
    connection.exec_driver_sql("UPDATE catalog_projects SET is_visible = FALSE")
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET destination_url = 'https://example.com/custom-hidden' "
        "WHERE slug = 'gd-fungi-run'"
    )
    before = snapshot(connection)
    statements.clear()
    migration.upgrade()
    assert sum(sql.startswith("UPDATE ") for sql in statements) == 3
    assert snapshot(connection) == expected_snapshot(before)


@pytest.mark.parametrize("slug", TARGETS)
def test_missing_any_target_fails_before_first_update(migration_store, slug):
    migration, connection, statements = migration_store
    connection.execute(sa.text("DELETE FROM catalog_projects WHERE slug = :slug"), {"slug": slug})
    before = snapshot(connection)
    statements.clear()
    with pytest.raises(RuntimeError, match=f"0105 missing catalog projects: {slug}"):
        migration.upgrade()
    assert not any(sql.startswith("UPDATE ") for sql in statements)
    assert snapshot(connection) == before


@pytest.mark.parametrize("entry", DIRECT, ids=[entry[0] for entry in DIRECT])
def test_unexpected_manual_url_fails_before_first_update(migration_store, entry):
    migration, connection, statements = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE slug = :slug"),
        {"slug": entry[0], "url": "https://example.com/manual"},
    )
    before = snapshot(connection)
    statements.clear()
    with pytest.raises(RuntimeError, match=f"unexpected destination_url for: {entry[0]}"):
        migration.upgrade()
    assert not any(sql.startswith("UPDATE ") for sql in statements)
    assert snapshot(connection) == before


@pytest.mark.parametrize("failed_update", [3, 12])
def test_compare_and_swap_miss_rolls_back_prior_batch_updates(migration_store, failed_update):
    migration, connection, _statements = migration_store
    before = snapshot(connection)
    update_count = 0

    def miss_one_update(_conn, _cursor, statement, parameters, _context, _many):
        nonlocal update_count
        if statement.startswith("UPDATE catalog_projects "):
            update_count += 1
            if update_count == failed_update:
                # 模拟首写前读取之后原值已变，CAS 返回零行；不冒充真实并发数据库验收。
                return statement + " AND 1 = 0", parameters
        return statement, parameters

    sa.event.listen(connection, "before_cursor_execute", miss_one_update, retval=True)
    with pytest.raises(RuntimeError, match="0105 concurrent catalog change for:"):
        migration.upgrade()
    assert update_count == failed_update
    assert snapshot(connection) == before


def test_database_failure_rolls_back_prior_batch_updates(migration_store):
    migration, connection, _statements = migration_store
    before = snapshot(connection)
    update_count = 0

    def fail_midway(_conn, _cursor, statement, parameters, _context, _many):
        nonlocal update_count
        if statement.startswith("UPDATE catalog_projects "):
            update_count += 1
            if update_count == 6:
                raise sa.exc.OperationalError(
                    statement, parameters, RuntimeError("simulated database failure")
                )

    sa.event.listen(connection, "before_cursor_execute", fail_midway)
    with pytest.raises(sa.exc.OperationalError, match="simulated database failure"):
        migration.upgrade()
    assert update_count == 6
    assert snapshot(connection) == before
