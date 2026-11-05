import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.core.exceptions import ValidationError
from app.services.catalog import CatalogService

ROOT = Path(__file__).resolve().parents[1]
GAME_URL = "/games/birdland/index.html"
OLD_DESCRIPTION = (
    "英文文字互动剧情：少女 Bridget 在夏令营中暗恋女孩 Bell，"
    "在奇幻梦境与日常交流间探索感情和自我认同；包含粗口与成熟话题。"
)
NEW_DESCRIPTION = (
    "中文汉化文字互动剧情：少女 Bridget 在夏令营中暗恋女孩 Bell，"
    "在奇幻梦境与日常交流间探索感情和自我认同；包含粗口与成熟话题。"
)


@pytest.fixture
def migration_store(monkeypatch):
    """用独立内存 SQLite 验证入口更新，不读取配置或连接项目数据库。"""

    spec = importlib.util.spec_from_file_location(
        "catalog_birdland_localized", ROOT / "alembic/versions/0109_birdland_localized_entry.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE COLLATE NOCASE, name TEXT, "
            "destination_url TEXT COLLATE NOCASE, destination_kind TEXT COLLATE NOCASE, "
            "description TEXT COLLATE NOCASE, author_name TEXT, author_url TEXT, "
            "icon_upload_id INTEGER, sort_order INTEGER, is_visible BOOLEAN, "
            "created_at TEXT, updated_at TEXT, view_count BIGINT)"
        )
        connection.execute(
            sa.text(
                "INSERT INTO catalog_projects VALUES "
                "(242, 1, 'birdland', 'BIRDLAND', 'https://birdland.camp/', 'external', "
                ":description, 'Brendan Patrick Hennessy / Izzy Marbella', "
                "'https://bphennessy.com/', 123, 7, 1, '旧创建时间', '人工修改时间', 99), "
                "(243, 5, 'hidden-other', '其他隐藏', 'https://example.com/manual', "
                "'external', '人工简介', '人工作者', 'https://example.com/author', "
                "456, 11, 0, '旧创建时间', '旧修改时间', 24)"
            ),
            {"description": OLD_DESCRIPTION},
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_ratings VALUES (242, 5), (242, 3), (243, 4)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ai_ratings (project_id INTEGER, assessment TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_ai_ratings VALUES (242, '保留原AI评分'), (243, '隐藏项目AI评分')"
        )
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def snapshots(connection):
    """按稳定顺序读取项目与评分，核对迁移只改获准字段。"""

    return {
        table: [dict(row) for row in connection.execute(sa.text(query)).mappings()]
        for table, query in (
            ("projects", "SELECT * FROM catalog_projects ORDER BY id"),
            ("ratings", "SELECT * FROM catalog_ratings ORDER BY project_id, score"),
            ("ai_ratings", "SELECT * FROM catalog_ai_ratings ORDER BY project_id"),
        )
    }


@pytest.mark.parametrize("old_url", ["https://birdland.camp", "https://birdland.camp/"])
@pytest.mark.parametrize("visible", [False, True])
def test_localized_entry_reuses_project_and_preserves_all_other_data(
    migration_store, old_url, visible
):
    migration, connection = migration_store
    assert migration.revision == "0109_birdland_localized_entry"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0108_add_five_browser_games"
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET destination_url = :url, is_visible = :visible "
            "WHERE id = 242"
        ),
        {"url": old_url, "visible": visible},
    )
    expected = snapshots(connection)
    expected["projects"][0].update(
        destination_url=GAME_URL, destination_kind="internal", description=NEW_DESCRIPTION
    )
    migration.upgrade()
    assert snapshots(connection) == expected
    migration.upgrade()
    migration.downgrade()
    migration.upgrade()
    assert snapshots(connection) == expected


@pytest.mark.parametrize(
    "description",
    [None, "", "人工简介", OLD_DESCRIPTION + " ", OLD_DESCRIPTION.replace("Bridget", "BRIDGET")],
)
def test_only_exact_default_description_is_replaced(migration_store, description):
    migration, connection = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET description = :description WHERE id = 242"),
        {"description": description},
    )
    expected = snapshots(connection)
    expected["projects"][0].update(destination_url=GAME_URL, destination_kind="internal")
    migration.upgrade()
    assert snapshots(connection) == expected


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        (GAME_URL, "internal"),
        ("/games/manual/index.html", "internal"),
        ("https://example.com/manual", "external"),
        ("https://birdland.camp/?manual=1", "external"),
        ("https://BIRDLAND.camp/", "external"),
        ("https://birdland.camp/", "internal"),
        ("https://birdland.camp/", "EXTERNAL"),
    ],
)
def test_manual_or_already_internal_entry_is_not_overwritten(migration_store, url, kind):
    migration, connection = migration_store
    connection.execute(
        sa.text(
            "UPDATE catalog_projects SET destination_url = :url, destination_kind = :kind "
            "WHERE id = 242"
        ),
        {"url": url, "kind": kind},
    )
    # 无须迁移的记录不因其他项目占用目标入口而阻塞。
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 243"),
        {"url": GAME_URL},
    )
    before = snapshots(connection)
    migration.upgrade()
    migration.downgrade()
    assert snapshots(connection) == before


@pytest.mark.parametrize("slug", ["missing-birdland", "BIRDLAND"])
def test_missing_exact_slug_is_not_recreated_or_blocked_by_conflict(migration_store, slug):
    migration, connection = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET slug = :slug WHERE id = 242"), {"slug": slug}
    )
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 243"),
        {"url": GAME_URL},
    )
    before = snapshots(connection)
    migration.upgrade()
    assert snapshots(connection) == before


@pytest.mark.parametrize(
    "url",
    [
        GAME_URL,
        GAME_URL + "/",
        "/games/birdland/",
        "/games/birdland",
        "https://pingxingxian.space" + GAME_URL,
        "https://pingxingxian.space" + GAME_URL + "/",
        "https://pingxingxian.space/games/birdland/",
        "https://pingxingxian.space/games/birdland",
    ],
)
def test_hidden_other_project_using_target_stops_before_any_write(migration_store, url):
    migration, connection = migration_store
    connection.execute(
        sa.text("UPDATE catalog_projects SET destination_url = :url WHERE id = 243"),
        {"url": url},
    )
    before = snapshots(connection)
    with pytest.raises(RuntimeError, match="already used by another project"):
        migration.upgrade()
    assert snapshots(connection) == before


def test_source_changed_after_precheck_is_not_overwritten(migration_store):
    migration, connection = migration_store
    expected = snapshots(connection)
    expected["projects"][0]["destination_url"] = "https://example.com/concurrent"
    changed = False

    def change_source_before_update(conn, cursor, statement, parameters, context, executemany):
        """在条件更新前模拟人工改入口，核对迁移仍以读取到的原值为前提。"""

        nonlocal changed
        if not changed and statement.startswith("UPDATE catalog_projects SET destination_url ="):
            changed = True
            cursor.execute(
                "UPDATE catalog_projects SET destination_url = 'https://example.com/concurrent' "
                "WHERE id = 242"
            )

    sa.event.listen(connection, "before_cursor_execute", change_source_before_update)
    try:
        migration.upgrade()
    finally:
        sa.event.remove(connection, "before_cursor_execute", change_source_before_update)
    assert changed
    assert snapshots(connection) == expected


@pytest.mark.parametrize(
    "url",
    [
        GAME_URL,
        "/play/generals-soldiers",
        "/play/snake-escape",
        "/play/flappy-dunk",
        "/games/illusion-prototype/index.html",
    ],
)
def test_new_and_existing_exact_internal_game_entries_are_allowed(url):
    CatalogService._validate_destination("internal", url)


@pytest.mark.parametrize(
    "url",
    [
        "/games/birdland/",
        "/games/birdland/index.html/",
        "/games/birdland/other.html",
        "/games/birdland/index.html?manual=1",
        "/play/birdland",
        "https://pingxingxian.space" + GAME_URL,
        "/admin",
    ],
)
def test_internal_entry_allowlist_is_not_broadened(url):
    with pytest.raises(ValidationError):
        CatalogService._validate_destination("internal", url)


def test_existing_external_https_contract_is_unchanged():
    CatalogService._validate_destination("external", "https://birdland.camp/")
    with pytest.raises(ValidationError):
        CatalogService._validate_destination("external", "http://birdland.camp/")
