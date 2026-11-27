import json
import sqlite3
from datetime import timedelta
from io import StringIO
from pathlib import Path
from secrets import token_hex

import httpx
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.core.config import Settings, get_settings
from app.core.security import create_token
from app.db.base import utcnow
from app.db.session import get_session
from app.models.user import User, UserSession
from app.models.workspace import UserWorkspaceConfig

PATH = "/api/v1/workspace/config"


class _IsolatedSession:
    """以内存 SQLite 执行真实 ORM 语句；仅在首创重复键用例模拟 MySQL 错误码。"""

    def __init__(self, db):
        self.db = db

    async def get(self, *args, **kwargs):
        return self.db.get(*args, **kwargs)

    async def execute(self, statement):
        try:
            return self.db.execute(statement)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
                raise IntegrityError(
                    exc.statement, None, Exception(1062, "test duplicate")
                ) from None
            raise

    async def scalar(self, statement):
        return self.db.scalar(statement)

    async def commit(self):
        self.db.commit()

    async def rollback(self):
        self.db.rollback()


@pytest.fixture
async def workspace():
    from app.main import create_app

    engine = create_engine("sqlite:///:memory:")
    for model in (User, UserSession, UserWorkspaceConfig):
        model.__table__.create(engine)
    settings = Settings(_env_file=None, jwt_secret_key=token_hex(32), unified_auth_enabled=False)
    now = utcnow()
    with Session(engine, expire_on_commit=False) as db:
        for uid, status in (("1", "active"), ("2", "active"), ("3", "disabled")):
            db.add(
                User(
                    id=uid,
                    username=f"user-{uid}",
                    email=f"user-{uid}@example.com",
                    hashed_password="fixture",
                    status=status,
                )
            )
        for sid, uid in (
            ("10", "1"),
            ("11", "1"),
            ("12", "1"),
            ("13", "1"),
            ("20", "2"),
            ("30", "3"),
        ):
            db.add(
                UserSession(
                    id=sid,
                    user_id=uid,
                    refresh_token_hash="fixture",
                    last_seen_at=now,
                    created_at=now - timedelta(days=31 if sid == "13" else 0),
                    revoked_at=now if sid == "12" else None,
                )
            )
        db.commit()

        async def isolated_session():
            try:
                yield _IsolatedSession(db)
            finally:
                db.rollback()

        def auth(uid="1", sid="10", *, kind="access", expires=300):
            token = create_token(
                subject=uid,
                token_type=kind,
                settings=settings,
                expires_delta=timedelta(seconds=expires),
                session_id=sid,
            )
            return {"Authorization": f"Bearer {token}"}

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_session] = isolated_session
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://fixture.invalid"
        ) as client:
            yield client, auth, db
    engine.dispose()


def _payload(revision="0", config=None, version=1):
    return {
        "expected_revision": revision,
        "schema_version": version,
        "config": config if config is not None else {"list": [], "tabList": []},
    }


async def test_two_devices_compare_and_save_without_overwriting_conflicts(workspace):
    client, auth, db = workspace
    device_a, device_b = auth(), auth(sid="11")
    empty = await client.get(PATH, headers=device_a)
    assert empty.json() == {
        "data": {"revision": "0", "schema_version": 1, "config": None, "updated_at": None},
        "meta": {},
    }
    assert empty.headers["Cache-Control"] == "private, no-store"
    assert db.scalar(select(UserWorkspaceConfig.user_id)) is None
    db.rollback()

    initial = {"global": {"siteTitle": "我的工作台"}}
    created = await client.put(PATH, headers=device_a, json=_payload(config=initial))
    assert created.status_code == 201
    assert created.json()["data"]["revision"] == "1"
    assert created.json()["data"]["updated_at"].endswith("+08:00")
    first_conflict = await client.put(PATH, headers=device_b, json=_payload())
    assert first_conflict.status_code == 409
    assert first_conflict.json()["error"]["details"] == {
        "expected_revision": "0",
        "current_revision": "1",
    }

    # 即使配置内容相同，匹配的保存也是一次成功写入，revision 前进一格。
    saved = await client.put(PATH, headers=device_a, json=_payload("1", initial))
    assert saved.status_code == 200
    assert saved.json()["data"]["revision"] == "2"
    conflict = await client.put(PATH, headers=device_b, json=_payload("1"))
    assert conflict.status_code == 409
    assert conflict.json()["error"] == {
        "code": "workspace_revision_conflict",
        "message": "云端配置已变更，当前修改未保存。请获取最新版本后再保存。",
        "details": {"expected_revision": "1", "current_revision": "2"},
    }
    assert "我的工作台" not in conflict.text
    assert "no-store" in conflict.headers["Cache-Control"]
    assert (await client.get(PATH, headers=device_a)).json()["data"] == saved.json()["data"]


async def test_account_isolation_cannot_choose_owner(workspace):
    client, auth, _ = workspace
    a, b = auth(), auth("2", "20")
    config = {"global": {"siteTitle": "仅账号 A"}}
    assert (await client.put(PATH, headers=a, json=_payload(config=config))).status_code == 201
    assert (await client.get(PATH, headers=b)).json()["data"]["config"] is None
    empty_conflict = await client.put(PATH, headers=b, json=_payload("1"))
    assert empty_conflict.json()["error"]["details"]["current_revision"] == "0"
    assert (
        await client.put(PATH, headers=b, json={**_payload(), "user_id": "1"})
    ).status_code == 422
    assert (await client.put(PATH, headers=b, json=_payload())).status_code == 201
    assert (await client.get(PATH, headers=a)).json()["data"]["config"] == config


async def test_only_revocable_active_main_sessions_can_read_or_write(workspace):
    client, auth, _ = workspace
    for headers in (
        {},
        auth(sid=None),
        auth(sid="20"),
        auth(sid="12"),
        auth(sid="13"),
        auth("3", "30"),
        auth(kind="refresh"),
        auth(expires=-1),
    ):
        lookup = await client.get(PATH, headers=headers)
        saved = await client.put(PATH, headers=headers, json=_payload())
        assert lookup.status_code == saved.status_code == 401
        assert saved.headers["WWW-Authenticate"] == "Bearer"
        assert saved.headers["Cache-Control"] == "private, no-store"


async def test_workspace_byte_limits_before_persistence(workspace):
    client, auth, _ = workspace
    headers = {**auth(), "Content-Type": "application/json"}

    async def chunked():
        yield b" " * (160 * 1024)
        yield b" " * (97 * 1024)

    oversized = await client.put(PATH, headers=headers, content=chunked())
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "workspace_request_too_large"

    # 这里用真实 UTF-8，且整个请求小于 256 KiB，仅配置本身过限。
    config = {"global": {"siteTitle": "字" * (44 * 1024)}}
    encoded = json.dumps(_payload(config=config), ensure_ascii=False).encode("utf-8")
    rejected = await client.put(PATH, headers=headers, content=encoded)
    assert rejected.status_code == 413
    assert rejected.json()["error"]["code"] == "workspace_config_too_large"
    unsupported = await client.put(
        PATH, headers={**headers, "Content-Encoding": "gzip"}, content=b"x"
    )
    assert unsupported.status_code == 415
    assert (await client.get(PATH, headers=auth())).json()["data"]["revision"] == "0"


@pytest.mark.parametrize(
    "payload",
    [
        _payload(0),
        _payload("01"),
        _payload("1\n"),
        _payload("9223372036854775808"),
        _payload(version=True),
        _payload(version=2),
        _payload(config=[]),
        _payload(config={"global": {"background": "url(https://fixture.invalid/image.png)"}}),
        _payload(config={"global": {"privateKey": "PRIVATE-CONFIG-SENTINEL"}}),
        _payload(config={"list": [{"i": "a", "material": "Anything"}]}),
        _payload(config={"list": [{"i": "a", "material": "Clock", "actionSetting": {}}]}),
        _payload(
            config={
                "affix": [
                    {"i": "n", "material": "Editor", "componentSetting": {"markdown": "local note"}}
                ]
            }
        ),
        _payload(
            config={
                "list": [
                    {
                        "i": "t",
                        "material": "TodoList",
                        "componentSetting": {"todo": {"x": "local task"}},
                    }
                ]
            }
        ),
        _payload(
            config={
                "list": [{"i": "b", "material": "Bookmark", "componentSetting": {"jumpType": 3}}]
            }
        ),
        _payload(
            config={
                "list": [
                    {
                        "i": "b",
                        "material": "Bookmark",
                        "componentSetting": {
                            "bookmark": [
                                {
                                    "id": "l",
                                    "url": "https://untrusted.invalid/image",
                                    "iconType": "network",
                                }
                            ],
                        },
                    }
                ]
            }
        ),
    ],
)
async def test_invalid_payloads_do_not_echo_values_or_create_rows(workspace, payload):
    client, auth, _ = workspace
    result = await client.put(PATH, headers=auth(), json=payload)
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "workspace_config_invalid"
    assert "PRIVATE-CONFIG-SENTINEL" not in result.text
    assert (await client.get(PATH, headers=auth())).json()["data"]["revision"] == "0"


async def test_safe_preset_projection_preserves_values_and_null_tab_data(workspace):
    client, auth, _ = workspace
    config = {
        "global": {
            "background": "linear-gradient(90deg, #123 0%, rgba(1,2,3,0.5) 100%)",
            "css": "",
            "loadHarmonyOSFont": False,
        },
        "list": [
            {"i": "c", "material": "Clock", "x": 0, "affixInfo": {"mode": 1, "x": 0, "y": 0}},
            {
                "i": "s",
                "material": "AiSearch",
                "componentSetting": {
                    "shortcuts": [
                        {
                            "id": "p",
                            "name": "写周报",
                            "prompt": "请整理以下内容",
                            "autoSend": False,
                        },
                    ]
                },
            },
            {
                "i": "b",
                "material": "Bookmark",
                "componentSetting": {
                    "jumpType": 1,
                    "bookmark": [
                        {
                            "id": "f",
                            "type": "folder",
                            "children": [
                                {
                                    "id": "l",
                                    "type": "icon",
                                    "url": "https://fixture.invalid/",
                                    "iconType": "text",
                                },
                            ],
                        },
                    ],
                },
            },
        ],
        "affix": [],
        "tabList": [{"id": "page-1", "selected": True, "data": None}],
        "showTabSwitchBtn": 0,
    }
    result = await client.put(PATH, headers=auth(), json=_payload(config=config))
    assert result.status_code == 201
    assert (await client.get(PATH, headers=auth())).json()["data"]["config"] == config


def test_workspace_migration_has_one_head_and_matches_model_mysql_ddl():
    directory = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "alembic"))
    assert directory.get_heads() == ["0116_user_workspace_configs"]
    revision = directory.get_revision("0116_user_workspace_configs")
    assert revision.down_revision == "0115_add_three_browser_games"
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        revision.module.upgrade()
    migrated = output.getvalue()
    model = str(CreateTable(UserWorkspaceConfig.__table__).compile(dialect=mysql.dialect()))
    for clause in [
        "user_id BIGINT NOT NULL",
        "config_json JSON NOT NULL",
        "revision BIGINT NOT NULL DEFAULT 1",
        "updated_at DATETIME(6) NOT NULL",
        "FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE",
        "CHECK (UPPER(JSON_TYPE(config_json)) = 'OBJECT')",
        "ENGINE=InnoDB",
        "CHARSET=utf8mb4",
    ]:
        assert clause in migrated and clause in model
