from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn, cast
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError as SchemaValidationError
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.v1.dependencies import get_current_user, get_session
from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.personas import (
    PERSONA_IDENTITIES,
    PERSONA_KIND_COMMENT,
    normalize_persona_kind,
    persona_identity,
    resolve_persona_update,
)
from app.db.schema_comments import COLUMN_COMMENTS
from app.main import create_app
from app.models.forum import Board, Post, Topic
from app.models.user import User
from app.schemas.admin import AdminUserResponse, AdminUserUpdateRequest
from app.schemas.forum import PostResponse, TopicResponse
from app.schemas.migrations import MigrationRowResult, MigrationUserRecord
from app.schemas.users import UserProfileUpdateRequest
from app.services.admin import AdminService
from app.services.badges import BadgeTrustService
from app.services.growth import GrowthService
from app.services.living_forum import LivingForumService
from app.services.migrations import MigrationService
from app.services.seo import SeoService, SeoSiteIdentity
from app.services.seo_renderer import render_post_section, render_semantic_fallback
from app.services.users import UserContentCounts, UserProfileService, UserRelationshipCounts

NOW = datetime(2026, 9, 3, 8, tzinfo=UTC)


@pytest.fixture(autouse=True)
def reject_database_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any accidental sync/async engine connection fail before network IO."""

    def reject(*_args: object, **_kwargs: object) -> NoReturn:
        """Reject ignored engine arguments; these tests must use memory doubles."""

        raise AssertionError("Persona unit tests must not connect to a database")

    monkeypatch.setattr(Engine, "connect", reject)
    monkeypatch.setattr(AsyncEngine, "connect", reject)


def memory_user(
    *, managed: bool = True, kind: str | None = "editorial", user_id: str = "101"
) -> User:
    """Return a fully initialized transient User for the requested identity."""

    return User(
        id=user_id,
        username=f"member{user_id}",
        email=f"member{user_id}@example.com",
        hashed_password="unused-test-hash",
        avatar_url=None,
        display_name=None,
        bio="原来的简介",
        website_url=None,
        location=None,
        role="user",
        level=0,
        trust_level=0,
        points_balance=0,
        experience_total=0,
        is_persona=managed,
        persona_kind=kind,
        status="active",
        profile_visibility="public",
        show_activity=True,
        two_factor_enabled=False,
        created_at=NOW,
        updated_at=NOW,
    )


def memory_session(user: User | None = None) -> SimpleNamespace:
    """Return async method doubles yielding user, without an engine or connection."""

    return SimpleNamespace(
        get=AsyncMock(return_value=user),
        scalar=AsyncMock(return_value=user),
        execute=AsyncMock(),
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )


def memory_topic(author: User) -> Topic:
    """Return a transient public topic with explicit counters and loaded authors."""

    board = Board(id="10", slug="lounge", name="闲聊", color="#409EFF", visibility="public")
    topic = Topic(
        id="20",
        board_id=board.id,
        board=board,
        user_id=author.id,
        author=author,
        title="公开身份测试主题",
        slug="identity-topic",
        tags=[],
        topic_type="regular",
        visibility="public",
        status="open",
        pinned=False,
        featured=False,
        view_count=10,
        reply_count=0,
        like_count=2,
        hot_score=1.0,
        answer_mode=False,
        vote_score=0,
        vote_count=0,
        last_posted_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    topic.posts = [memory_post(topic, author, floor=1)]
    return topic


def memory_post(topic: Topic, author: User, *, floor: int) -> Post:
    """Return one transient floor attached to topic, preserving known source text."""

    return Post(
        id=str(30 + floor),
        topic_id=topic.id,
        topic=topic,
        user_id=author.id,
        author=author,
        post_number=floor,
        raw_md="原文不应改写",
        cooked_html="<p>原文不应改写</p>",
        reply_count=0,
        like_count=0,
        vote_score=0,
        vote_count=0,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize(
    ("managed", "kind", "label"),
    [
        (True, "editorial", "官方栏目"),
        (True, "automation", "自动账号"),
        (True, "fictional", "创作角色"),
        (True, None, "运营角色"),
        (True, "future-kind", "运营角色"),
        (True, {}, "运营角色"),
        (False, "editorial", None),
        (False, None, None),
    ],
)
def test_public_identity_never_infers_ownership(
    managed: bool, kind: object, label: str | None
) -> None:
    """The flag governs identity; invalid kinds retain a managed fallback only."""

    identity = persona_identity(managed, kind)
    assert (identity.label if identity else None) == label
    assert normalize_persona_kind(managed, kind) == (
        kind if managed and isinstance(kind, str) and kind in PERSONA_IDENTITIES else None
    )


@pytest.mark.parametrize(
    ("current", "kind", "flag", "requested", "provided", "expected"),
    [
        (True, "editorial", None, None, False, (True, "editorial")),
        (False, "stale-kind", None, None, False, (False, "stale-kind")),
        (True, "editorial", True, None, False, (True, "editorial")),
        (False, "editorial", True, None, False, (True, None)),
        (True, "editorial", None, None, True, (True, None)),
        (True, "editorial", False, None, False, (False, None)),
        (True, "editorial", False, None, True, (False, None)),
        (True, None, None, "automation", True, (True, "automation")),
        (False, None, True, "fictional", True, (True, "fictional")),
    ],
)
def test_identity_update_presence_and_reactivation(
    current: bool,
    kind: str | None,
    flag: bool | None,
    requested: object,
    provided: bool,
    expected: tuple[bool, str | None],
) -> None:
    """Omission/null and flag transitions must follow the approved state table."""

    assert (
        resolve_persona_update(
            current,
            kind,
            requested_is_persona=flag,
            requested_kind=requested,
            kind_provided=provided,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("flag", "kind", "code"),
    [
        (False, "editorial", "persona_kind_requires_persona"),
        (True, "invalid", "persona_kind_invalid"),
        (True, {}, "persona_kind_invalid"),
    ],
)
def test_identity_update_rejects_conflicts(flag: bool, kind: object, code: str) -> None:
    """Invalid writes raise the expected domain error without producing state."""

    with pytest.raises(ValidationError) as error:
        resolve_persona_update(
            False, None, requested_is_persona=flag, requested_kind=kind, kind_provided=True
        )
    assert error.value.code == code


def test_write_schemas_preserve_presence_and_privilege_boundaries() -> None:
    """Only admin/import schemas expose kinds; null and omission remain distinct."""

    assert "persona_kind" not in AdminUserUpdateRequest().model_fields_set
    assert "persona_kind" in AdminUserUpdateRequest(persona_kind=None).model_fields_set
    with pytest.raises(SchemaValidationError):
        AdminUserUpdateRequest.model_validate({"persona_kind": "not-a-kind"})
    with pytest.raises(SchemaValidationError):
        MigrationUserRecord.model_validate(
            {"username": "imported", "email": "imported@example.com", "persona_kind": "editorial"}
        )
    ordinary = UserProfileUpdateRequest.model_validate(
        {"bio": "unchanged privileges", "is_persona": True, "persona_kind": "editorial"}
    )
    assert "is_persona" not in ordinary.model_dump()
    assert "persona_kind" not in ordinary.model_dump()


@pytest.mark.asyncio
async def test_invalid_import_identity_returns_a_serializable_422() -> None:
    """An invalid identity must produce a JSON 422, not an exception in the error handler."""

    admin = memory_user(managed=False, kind=None, user_id="999")
    admin.role = "admin"
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_session] = lambda: memory_session()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/migrations/import/preview",
            json={
                "users": [
                    {
                        "username": "bad_operator",
                        "email": "bad_operator@example.com",
                        "persona_kind": "editorial",
                    }
                ],
            },
        )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["errors"][0]["type"] == "persona_kind_requires_persona"


@pytest.mark.asyncio
async def test_admin_conflict_does_not_partially_mutate_role_or_status() -> None:
    """A subtype conflict must occur before any other account or audit mutation."""

    user = memory_user(managed=False, kind=None)
    session = memory_session(user)
    admin = memory_user(managed=False, kind=None, user_id="999")
    admin.role = "admin"
    service = AdminService(cast(AsyncSession, session), Settings(_env_file=None))
    with pytest.raises(ValidationError, match="运营/测试"):
        await service.update_user(
            user.id,
            AdminUserUpdateRequest(role="moderator", status="suspended", persona_kind="editorial"),
            admin,
        )
    assert (user.role, user.status, user.is_persona, user.persona_kind) == (
        "user",
        "active",
        False,
        None,
    )
    session.commit.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_non_admin_cannot_assign_a_persona_kind() -> None:
    """The new metadata must remain behind the existing administrator gate."""

    session = memory_session(memory_user())
    service = AdminService(cast(AsyncSession, session), Settings(_env_file=None))
    with pytest.raises(PermissionDeniedError):
        await service.update_user(
            "101", AdminUserUpdateRequest(persona_kind="automation"), memory_user(user_id="102")
        )
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_updates_kind_and_audits_before_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A legal subtype-only edit preserves ownership/roles and audits both values."""

    user = memory_user()
    session = memory_session(user)
    service = AdminService(cast(AsyncSession, session), Settings(_env_file=None))
    admin = memory_user(managed=False, kind=None, user_id="999")
    admin.role = "admin"
    monkeypatch.setattr(GrowthService, "adjust_user", AsyncMock())
    monkeypatch.setattr(BadgeTrustService, "recompute_trust", AsyncMock())
    monkeypatch.setattr(
        service, "get_user", AsyncMock(side_effect=lambda *_: AdminUserResponse.from_model(user))
    )
    response = await service.update_user(
        user.id, AdminUserUpdateRequest(persona_kind="automation"), admin
    )
    assert response.is_persona is True
    assert response.persona_kind == "automation"
    assert user.role == "user"
    audit = session.add.call_args.args[0]
    assert audit.data["before"]["persona_kind"] == "editorial"
    assert audit.data["after"]["persona_kind"] == "automation"
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("kind", ["editorial", "automation", "fictional", None, "future-kind"])
def test_topic_and_post_projection_preserves_text_and_identity(kind: str | None) -> None:
    """Both public serializers project the same known subtype without rewriting text."""

    topic = memory_topic(memory_user(kind=kind))
    topic_data = TopicResponse.from_model(topic)
    post_data = PostResponse.from_model(topic.posts[0])
    expected = normalize_persona_kind(True, kind)
    assert topic_data.author_is_persona is True
    assert post_data.author_is_persona is True
    assert topic_data.author_persona_kind == post_data.author_persona_kind == expected
    assert post_data.raw_md == "原文不应改写"
    topic.posts[0].deleted_at = NOW
    hidden = PostResponse.from_model(topic.posts[0])
    assert hidden.raw_md == hidden.cooked_html == ""
    assert hidden.author_persona_kind == expected


@pytest.mark.asyncio
async def test_profile_and_directory_expose_identity_without_private_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Profile privacy does not hide operator status or leak protected profile copy."""

    user = memory_user(kind="fictional")
    user.profile_visibility = "private"
    session = memory_session(user)
    service = UserProfileService(cast(AsyncSession, session))
    monkeypatch.setattr(BadgeTrustService, "list_user_badges", AsyncMock(return_value=[]))
    response = await service._profile_response(
        user,
        counts=UserContentCounts(1, 2),
        relationship_counts=UserRelationshipCounts(0, 0),
        current_user=None,
    )
    assert response.is_persona is True
    assert response.persona_kind == "fictional"
    assert response.bio is None
    assert "email" not in response.model_dump()
    user.profile_visibility = "public"
    session.execute.return_value = SimpleNamespace(all=Mock(return_value=[(user, 1, 2)]))
    directory = await service.list_directory(sort="active", limit=10)
    assert directory[0].persona_kind == "fictional"
    assert directory[0].is_persona is True


@pytest.mark.parametrize(
    ("existing_kind", "record_kind", "action", "result_kind"),
    [
        ("editorial", None, "skipped", "editorial"),
        (None, "editorial", "updated", "editorial"),
        ("editorial", "editorial", "skipped", "editorial"),
        ("editorial", "automation", "error", "editorial"),
    ],
)
@pytest.mark.asyncio
async def test_import_keeps_existing_classification(
    existing_kind: str | None,
    record_kind: str | None,
    action: str,
    result_kind: str | None,
) -> None:
    """Imports may fill an empty kind but never silently clear or replace a choice."""

    user = memory_user(kind=existing_kind)
    session = memory_session(user)
    service = MigrationService(cast(AsyncSession, session))
    record = MigrationUserRecord.model_validate(
        {
            "username": user.username,
            "email": user.email,
            "is_persona": True,
            "persona_kind": record_kind,
        }
    )
    rows: list[MigrationRowResult] = []
    await service._import_users([record], rows)
    assert rows[0].action == action
    assert user.persona_kind == result_kind
    assert service._export_user(user)["persona_kind"] == result_kind
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_old_document_and_new_user_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """An old import leaves metadata alone; a new managed user retains its subtype."""

    user = memory_user(kind="fictional")
    service = MigrationService(cast(AsyncSession, memory_session(user)))
    rows: list[MigrationRowResult] = []
    await service._import_users(
        [MigrationUserRecord(username=user.username, email=user.email)], rows
    )
    assert (user.is_persona, user.persona_kind) == (True, "fictional")
    session = memory_session()
    monkeypatch.setattr("app.services.migrations.hash_password", Mock(return_value="test-hash"))
    new_service = MigrationService(cast(AsyncSession, session))
    record = MigrationUserRecord(
        username="new_operator",
        email="new_operator@example.com",
        is_persona=True,
        persona_kind="automation",
    )
    created = await new_service._import_users([record], [])
    exported = new_service._export_user(created["new_operator"])
    restored = MigrationUserRecord.model_validate(exported)
    assert restored.is_persona is True
    assert restored.persona_kind == "automation"


@pytest.mark.asyncio
async def test_runtime_persona_refresh_preserves_subtype() -> None:
    """The existing runtime refresh must not reset an administrator's classification."""

    user = memory_user(kind="fictional")
    user.username = "老槐"
    user.email = "old-huai-tree@pingxingxian.space"
    session = memory_session(user)
    service = LivingForumService(cast(AsyncSession, session), Settings(_env_file=None))
    assert await service._ensure_persona("老槐") is user
    assert user.persona_kind == "fictional"
    assert user.is_persona is True


@pytest.mark.parametrize("kind", ["editorial", "automation", "fictional", None])
def test_managed_topics_keep_rendered_content_without_forum_schema(kind: str | None) -> None:
    """Every managed kind remains visible without being represented as organic UGC."""

    author = memory_user(kind=kind)
    topic = memory_topic(author)
    service = SeoService(cast(AsyncSession, object()))
    post = service._page_post(topic.posts[0], modified_at=NOW)
    assert service._topic_structured_data(topic, (post,), "https://example.com") is None
    body = "\n".join(render_post_section((post,)))
    identity = persona_identity(True, kind)
    assert identity is not None
    assert identity.label in body
    assert "原文不应改写" in body


def test_mixed_replies_preserve_counts_without_inventing_people() -> None:
    """A member topic retains forum schema but operator comments are not Person nodes."""

    member = memory_user(managed=False, kind=None)
    topic = memory_topic(member)
    topic.reply_count = 2
    managed = memory_post(topic, memory_user(kind="automation", user_id="102"), floor=2)
    organic = memory_post(topic, memory_user(managed=False, kind=None, user_id="103"), floor=3)
    service = SeoService(cast(AsyncSession, object()))
    posts = tuple(
        service._page_post(post, modified_at=NOW) for post in [topic.posts[0], managed, organic]
    )
    schema = service._topic_structured_data(topic, posts, "https://example.com")
    assert schema is not None
    assert schema["@type"] == "DiscussionForumPosting"
    assert schema["commentCount"] == 2
    comments = cast(list[dict[str, object]], schema["comment"])
    assert len(comments) == 1
    assert comments[0]["author"] == {
        "@type": "Person",
        "name": "member103",
        "url": "https://example.com/members/103",
    }
    assert "member102" in "\n".join(render_post_section(posts))


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [True, False])
async def test_profile_seo_notice_preserves_bio_and_indexability(
    managed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Public operator profiles keep canonical/indexability and their original bio."""

    user = memory_user(managed=managed, kind="editorial")
    service = SeoService(cast(AsyncSession, object()))
    monkeypatch.setattr(service, "_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(
        service,
        "_site_identity",
        AsyncMock(return_value=SeoSiteIdentity("平行线", "说明", "/logo-lines-mark.png")),
    )
    monkeypatch.setattr(service, "_public_topic_count_for_user", AsyncMock(return_value=1))
    monkeypatch.setattr(service, "_public_post_count_for_user", AsyncMock(return_value=2))
    monkeypatch.setattr(service, "_public_topics", AsyncMock(return_value=[]))
    document = await service.profile_page(user.id, "https://example.com")
    assert document.status_code == 200
    assert document.meta.robots == "index,follow"
    assert document.meta.canonical_url == "https://example.com/members/101"
    assert document.intro == user.bio
    if managed:
        assert document.page_structured_data is None
        assert "官方栏目" in (document.identity_notice or "")
        assert "用于栏目内容发布" in render_semantic_fallback(document)
    else:
        assert document.identity_notice is None
        assert document.page_structured_data is not None
        assert document.page_structured_data["@type"] == "ProfilePage"
    user.profile_visibility = "private"
    restricted = await service.profile_page(user.id, "https://example.com")
    assert restricted.page_structured_data is None
    assert restricted.identity_notice is None
    assert "原来的简介" not in render_semantic_fallback(restricted)


def test_migration_is_only_a_nullable_column_without_running_it() -> None:
    """Statically inspect the approved migration; never invoke upgrade or an engine."""

    path = Path(__file__).parents[1] / "alembic/versions/0072_add_user_persona_kind.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    revision_values = {
        node.target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id in {"revision", "down_revision"}
    }
    assert revision_values == {
        "revision": "0072_add_user_persona_kind",
        "down_revision": "0071_seed_page_margin_light_persona",
    }
    upgrade = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    operations = [
        node
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
    ]
    assert len(operations) == 1
    assert operations[0].func.attr == "add_column"
    assert ast.literal_eval(operations[0].args[0]) == "users"
    column = operations[0].args[1]
    assert isinstance(column, ast.Call)
    assert ast.literal_eval(column.args[0]) == "persona_kind"
    assert any(
        keyword.arg == "nullable" and ast.literal_eval(keyword.value) is True
        for keyword in column.keywords
    )
    mapped_column = User.__table__.c.persona_kind
    assert mapped_column.nullable is True
    assert mapped_column.type.length == 24
    assert mapped_column.server_default is None
    assert mapped_column.comment == COLUMN_COMMENTS["users"]["persona_kind"] == PERSONA_KIND_COMMENT
