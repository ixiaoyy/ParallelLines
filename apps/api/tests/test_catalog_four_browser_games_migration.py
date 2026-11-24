import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

MIGRATION = (
    Path(__file__).resolve().parents[1] / "alembic/versions/0114_add_four_browser_games.py"
)
GAMES = (
    ("racing", "polytrack", "PolyTrack", "https://www.kodub.com/apps/polytrack", "Kodub"),
    (
        "shooting", "space-huggers", "Space Huggers",
        "https://killedbyapixel.github.io/SpaceHuggers/", "Frank Force（KilledByAPixel）",
    ),
    (
        "rpg", "a-dark-room", "小黑屋（A Dark Room）",
        "https://adarkroom.doublespeakgames.com/?lang=zh_cn",
        "Michael Townsend / doublespeak games",
    ),
    (
        "rts", "evolution-of-trust", "信任的进化", "https://dccxi.com/trust/",
        "Nicky Case（原作） / 吴桐、唐鳳（简中译版署名）",
    ),
)


@pytest.fixture
def store(monkeypatch):
    """使用独立内存数据库，不读取真实 API 配置。"""
    spec = importlib.util.spec_from_file_location("catalog_four_browser_games", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE catalog_categories (id INTEGER PRIMARY KEY, slug TEXT UNIQUE)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_categories VALUES (1, 'racing'), (2, 'shooting'), "
            "(3, 'rpg'), (4, 'rts')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id INTEGER PRIMARY KEY, category_id INTEGER, "
            "slug TEXT UNIQUE, name TEXT, destination_url TEXT, destination_kind TEXT, "
            "description TEXT, author_name TEXT, author_url TEXT, icon_upload_id INTEGER, "
            "sort_order INTEGER, is_visible BOOLEAN, created_at TEXT, updated_at TEXT, "
            "view_count INTEGER NOT NULL DEFAULT 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO catalog_projects VALUES "
            "(31, 1, 'old-race', '旧赛车', 'https://example.test/race', 'external', "
            "'人工简介', '人工作者', 'https://example.test/author', 8, 9, 1, 'old', 'old', 17), "
            "(32, 1, 'hidden-race', '隐藏游戏', '/play/old', 'internal', "
            "NULL, NULL, NULL, NULL, 12, 0, 'old', 'old', 32)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id INTEGER, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (31, 4), (32, 5)")
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
        yield migration, connection
    engine.dispose()


def test_exact_entries_and_preserved_state(store):
    migration, connection = store
    before = connection.exec_driver_sql("SELECT * FROM catalog_projects ORDER BY id").all()
    migration.upgrade()
    added = connection.exec_driver_sql(
        "SELECT c.slug, p.slug, p.name, p.destination_url, p.author_name, p.destination_kind, "
        "p.icon_upload_id, p.sort_order, p.is_visible, p.view_count "
        "FROM catalog_projects p JOIN catalog_categories c ON c.id = p.category_id "
        "WHERE p.id > 32 ORDER BY p.id"
    ).all()
    assert added == [
        (*game, "external", None, order, 1, 0)
        for game, order in zip(GAMES, (13, 0, 0, 0), strict=True)
    ]
    after = connection.exec_driver_sql("SELECT * FROM catalog_projects ORDER BY id").all()
    assert after[:2] == before
    ratings = connection.exec_driver_sql(
        "SELECT * FROM catalog_ratings ORDER BY project_id"
    ).all()
    assert ratings == [(31, 4), (32, 5)]
    assert connection.exec_driver_sql("SELECT COUNT(*) FROM catalog_categories").scalar() == 4
    migration.upgrade()
    migration.downgrade()
    assert connection.exec_driver_sql("SELECT * FROM catalog_projects ORDER BY id").all() == after


def test_hidden_slug_and_url_keep_existing_records_without_merging_language(store):
    migration, connection = store
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET slug = 'space-huggers' WHERE id = 32"
    )
    connection.exec_driver_sql(
        "UPDATE catalog_projects SET destination_url = 'https://www.kodub.com/apps/polytrack/', "
        "category_id = 3 WHERE id = 31"
    )
    connection.exec_driver_sql(
        "INSERT INTO catalog_projects (slug, category_id, destination_url, is_visible, sort_order) "
        "VALUES ('dark-room-en', 4, 'https://adarkroom.doublespeakgames.com/?lang=en', 0, 0)"
    )
    before = connection.exec_driver_sql("SELECT * FROM catalog_projects ORDER BY id").all()
    migration.upgrade()
    after = connection.exec_driver_sql("SELECT * FROM catalog_projects ORDER BY id").all()
    assert after[:3] == before
    assert [row.slug for row in after[3:]] == ["a-dark-room", "evolution-of-trust"]


def test_missing_category_stops_before_writing(store):
    migration, connection = store
    connection.exec_driver_sql("DELETE FROM catalog_categories WHERE slug = 'rts'")
    with pytest.raises(RuntimeError, match="requires catalog categories"):
        migration.upgrade()
    assert connection.exec_driver_sql("SELECT id FROM catalog_projects ORDER BY id").all() == [
        (31,), (32,),
    ]


def test_one_failed_insert_rolls_back_entire_batch(store):
    migration, connection = store
    connection.exec_driver_sql(
        "CREATE TRIGGER fail_trust BEFORE INSERT ON catalog_projects "
        "WHEN NEW.slug = 'evolution-of-trust' "
        "BEGIN SELECT RAISE(ABORT, 'fixture insertion failure'); END"
    )
    with pytest.raises(sa.exc.IntegrityError, match="fixture insertion failure"):
        migration.upgrade()
    assert connection.exec_driver_sql("SELECT id FROM catalog_projects ORDER BY id").all() == [
        (31,), (32,),
    ]
