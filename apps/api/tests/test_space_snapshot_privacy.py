"""账单快照输出脱敏的无数据库回归；会话替身不创建任何数据库连接。"""

from collections import deque
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.models.space import SpaceJournalEntry
from app.models.user import User
from app.schemas.space import SpaceJournalCreateRequest, SpaceJournalUpdateRequest
from app.services.space import SpaceService, _serialize_journal


STAMP = datetime(2026, 11, 17, tzinfo=UTC)


def make_snapshot(hidden: bool | None) -> dict:
    """构造包含旧金额字段的快照；None 表示旧记录未设置隐藏开关。"""
    snapshot = {
        "month": "2026-11",
        "entry_count": 2,
        "total_expense_cents": 12345,
        "total_income_cents": 98765,
        "monthly_budget_cents": 300000,
        "top_categories": [
            {"category": "coffee", "ratio_percent": 100, "amount_cents": 12345}
        ],
        "single_entry": {
            "kind": "expense",
            "category": "coffee",
            "amount_cents": 12345,
            "note": "咖啡",
        },
    }
    if hidden is not None:
        snapshot["hide_exact_amount"] = hidden
    return snapshot


def make_entry(snapshot: dict | None, visibility: str = "public") -> SpaceJournalEntry:
    """构造已持久化形态的手账，不使用数据库或自动填充业务数据。"""
    return SpaceJournalEntry(
        id="7",
        user_id="42",
        entry_date="2026-11-17",
        title="账单",
        content="共记录 2 笔收支。",
        mood="",
        weather="",
        location="",
        visibility=visibility,
        is_pinned=False,
        card_theme="paper",
        tags=[],
        media_urls=[],
        checklist=[],
        ledger_snapshot=snapshot,
        likes_count=0,
        reactions={},
        unlock_at=None,
        created_at=STAMP,
        updated_at=STAMP,
    )


def assert_snapshot_output(actual: dict, original: dict, hidden: bool | None) -> None:
    """核对隐藏投影或完整保留合同，不能用零金额代替被隐藏的字段。"""
    if not hidden:
        assert actual == original
        return
    assert actual == {
        "month": "2026-11",
        "entry_count": 2,
        "hide_exact_amount": True,
        "top_categories": [{"category": "coffee", "ratio_percent": 100}],
        "single_entry": {"kind": "expense", "category": "coffee", "note": "咖啡"},
    }


class Rows(list):
    """提供服务真实调用的结果接口，不执行 SQL。"""

    def unique(self):
        return self


class MemorySession:
    """按入口预置查询结果，仅记录内存写入，不构造引擎或连接。"""

    def __init__(self, entry, author, *, scalar_values=(), row_values=()):
        self.entry = entry
        self.author = author
        self.scalar_values = deque(scalar_values)
        self.row_values = deque(row_values)

    async def scalar(self, _statement):
        return self.scalar_values.popleft()

    async def scalars(self, _statement):
        return Rows(self.row_values.popleft())

    async def execute(self, _statement):
        return SimpleNamespace(all=lambda: [])

    async def get(self, model, _identifier):
        return self.author if model is User else self.entry

    def add(self, entry):
        self.entry = entry

    async def commit(self):
        pass

    async def refresh(self, entry):
        if entry.id is None:
            entry.id = "7"
        entry.created_at = STAMP
        entry.updated_at = STAMP


@pytest.mark.parametrize("hidden", [True, False, None])
@pytest.mark.parametrize("visibility", ["public", "friends", "private"])
def test_serialization_projects_hidden_amounts_without_mutating_old_snapshot(hidden, visibility):
    """所有可见性下隐藏快照均脱敏，未隐藏快照及底层 JSON 保持原样。"""
    snapshot = make_snapshot(hidden)
    before = deepcopy(snapshot)
    entry = make_entry(snapshot, visibility)

    response = _serialize_journal(entry)

    assert_snapshot_output(response.model_dump()["ledger_snapshot"], before, hidden)
    assert response.visibility == visibility
    assert entry.ledger_snapshot is snapshot
    assert snapshot == before


@pytest.mark.parametrize("hidden", [True, False, None])
@pytest.mark.parametrize(
    "entrypoint", ["create", "update", "workspace", "profile", "feed", "like", "react"]
)
async def test_every_journal_service_output_obeys_snapshot_privacy(hidden, entrypoint):
    """真实服务入口共用脱敏出口，包括公开列表、主页和互动返回值。"""
    snapshot = make_snapshot(hidden)
    before = deepcopy(snapshot)
    entry = make_entry(snapshot)
    author = User(
        id="42", username="snapshot-owner", level=1, status="active", avatar_url=None
    )
    entry.user = author
    scalar_values = {
        "workspace": [None],
        "profile": [author, None, 1],
        "like": [None],
        "react": [None],
    }.get(entrypoint, [])
    row_values = {
        "workspace": [[entry], []],
        "profile": [[entry]],
        "feed": [[entry]],
    }.get(entrypoint, [])
    session = MemorySession(entry, author, scalar_values=scalar_values, row_values=row_values)
    service = SpaceService(session)

    if entrypoint == "create":
        response = await service.create_journal(
            author,
            SpaceJournalCreateRequest(
                entry_date="2026-11-17", content="共记录 2 笔收支。", ledger_snapshot=snapshot
            ),
        )
    elif entrypoint == "update":
        response = await service.update_journal(
            author, entry.id, SpaceJournalUpdateRequest(title="更新标题")
        )
    elif entrypoint == "workspace":
        response = (await service.get_my_workspace(author, month="2026-11")).journals[0]
    elif entrypoint == "profile":
        response = (await service.get_public_user_space(author.username)).journals[0]
    elif entrypoint == "feed":
        response = (await service.list_public_feed())[0]
    elif entrypoint == "like":
        response = await service.like_journal(entry.id)
    else:
        response = await service.react_journal(entry.id, "hug")

    assert_snapshot_output(response.model_dump()["ledger_snapshot"], before, hidden)
    assert session.entry.ledger_snapshot == before
    assert snapshot == before
    assert not session.scalar_values
    assert not session.row_values


def test_locked_capsule_still_hides_the_entire_snapshot():
    """时间胶囊未拆封时继续隐藏全部快照，不因金额投影暴露内容。"""
    snapshot = make_snapshot(True)
    entry = make_entry(snapshot)
    entry.unlock_at = "9999-12-31"

    assert _serialize_journal(entry).ledger_snapshot is None
    assert entry.ledger_snapshot == snapshot


def test_plain_journal_keeps_absent_snapshot():
    """普通手账不生成快照或填充金额。"""
    assert _serialize_journal(make_entry(None)).ledger_snapshot is None


@pytest.mark.parametrize(
    ("visibility", "viewer_id", "mutual_count", "allowed"),
    [
        ("public", None, None, True),
        ("private", None, None, False),
        ("private", "42", None, True),
        ("private", "99", None, False),
        ("friends", None, None, False),
        ("friends", "42", None, True),
        ("friends", "99", 2, True),
        ("friends", "99", 0, False),
    ],
)
async def test_existing_visibility_permissions_are_unchanged(
    visibility, viewer_id, mutual_count, allowed
):
    """脱敏不能放宽私密或互关好友手账的访问条件。"""
    entry = make_entry(make_snapshot(True), visibility)
    viewer = SimpleNamespace(id=viewer_id) if viewer_id else None
    scalar_values = [] if mutual_count is None else [mutual_count]
    service = SpaceService(MemorySession(entry, None, scalar_values=scalar_values))

    if allowed:
        await service._ensure_entry_readable(entry, viewer)
    else:
        with pytest.raises(NotFoundError):
            await service._ensure_entry_readable(entry, viewer)
