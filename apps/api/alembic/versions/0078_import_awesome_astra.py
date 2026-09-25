"""Import the pinned Awesome GPT-6 Astra game directory.

Revision ID: 0078_import_awesome_astra
Revises: 0077_catalog_submissions
Create Date: 2026-09-26
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import op

revision: str = "0078_import_awesome_astra"
down_revision: str | None = "0077_catalog_submissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_COMMIT = "96b5360c69edf6f7ef59ac96072c6cdf9e93e5b1"
SOURCE_URL = (
    "https://raw.githubusercontent.com/MartinDelophy/awesome-gpt-6-astra/"
    f"{SOURCE_COMMIT}/README.zh-CN.md"
)
SOURCE_PAGE = (
    "https://github.com/MartinDelophy/awesome-gpt-6-astra/blob/"
    f"{SOURCE_COMMIT}/README.zh-CN.md?plain=1"
)
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "awesome_astra_96b5360.json"

# 保留来源目录的六个玩法分类；新分类只追加到管理员现有排序之后。
SOURCE_CATEGORIES: tuple[tuple[str, str, int], ...] = (
    ("动作与街机", "astra-action-arcade", 48),
    ("解谜与益智", "astra-puzzle-brain", 11),
    ("策略与模拟", "astra-strategy-simulation", 37),
    ("RPG 与冒险", "astra-rpg-adventure", 19),
    ("平台跳跃与竞速", "astra-platform-racing", 34),
    ("实验玩法与多人游戏", "astra-experimental-multiplayer", 12),
)


def _is_https_url(value: str) -> bool:
    """检查公开项目或作者主页链接是否为无凭据的 HTTPS 地址。"""

    if not value.startswith("https://") or "\\" in value or any(char.isspace() for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and parsed.port != 0
        )
    except ValueError:
        return False


def _load_entries() -> list[dict[str, object]]:
    """读取并验证固定快照，返回来源顺序的 161 个目录条目。"""

    # 迁移只读取随镜像打包的固定快照，不在部署或升级时访问外网。
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if (
        payload.get("source_commit") != SOURCE_COMMIT
        or payload.get("source_url") != SOURCE_URL
        or not isinstance(entries, list)
        or len(entries) != 161
    ):
        raise RuntimeError("0078 source snapshot is missing or inconsistent")

    counts = {name: 0 for name, _, _ in SOURCE_CATEGORIES}
    seen_urls: set[str] = set()
    seen_lines: set[int] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise RuntimeError("0078 source snapshot has an invalid entry")
        category = item.get("source_category")
        name = item.get("name")
        url = item.get("url")
        description = item.get("description")
        author_name = item.get("author_name")
        author_url = item.get("author_url")
        source_line = item.get("source_line")
        if (
            not isinstance(category, str)
            or category not in counts
            or not isinstance(name, str)
            or not 1 <= len(name) <= 120
            or not isinstance(url, str)
            or len(url) > 2048
            or not _is_https_url(url)
            or not isinstance(description, str)
            or not 1 <= len(description) <= 300
            or not isinstance(author_name, str)
            or not 1 <= len(author_name) <= 120
            or not isinstance(source_line, int)
            or source_line <= 0
            or (author_url is not None and not isinstance(author_url, str))
            or url in seen_urls
            or source_line in seen_lines
        ):
            raise RuntimeError("0078 source snapshot has an invalid or duplicate entry")
        # 来源未提供 HTTPS 作者主页时，署名链接指向该条目的固定 README 行。
        resolved_author_url = (
            author_url
            if isinstance(author_url, str) and _is_https_url(author_url)
            else f"{SOURCE_PAGE}#L{source_line}"
        )
        if len(resolved_author_url) > 2048:
            raise RuntimeError("0078 author URL exceeds catalog column length")
        item["author_url"] = resolved_author_url
        counts[category] += 1
        seen_urls.add(url)
        seen_lines.add(source_line)

    if any(counts[name] != expected for name, _, expected in SOURCE_CATEGORIES):
        raise RuntimeError("0078 source snapshot category counts changed")
    return entries


def upgrade() -> None:
    """导入 157 个新网址，按精确网址给已有项目补缺失的作者信息。"""

    entries = _load_entries()
    bind = op.get_bind()
    now = datetime.now(UTC)
    next_category_order = int(
        bind.scalar(sa.text("SELECT COALESCE(MAX(sort_order), -1) FROM catalog_categories"))
    ) + 1

    select_category = sa.text("SELECT id FROM catalog_categories WHERE slug = :slug")
    insert_category = sa.text(
        "INSERT INTO catalog_categories "
        "(slug, name, sort_order, is_visible, created_at, updated_at) "
        "VALUES (:slug, :name, :sort_order, TRUE, :now, :now)"
    )
    category_ids: dict[str, int] = {}
    next_project_order: dict[str, int] = {}
    for name, slug, _ in SOURCE_CATEGORIES:
        category_id = bind.scalar(select_category, {"slug": slug})
        if category_id is None:
            # 同标识分类已由管理员创建时保留名称、排序、图标和可见性。
            bind.execute(
                insert_category,
                {"slug": slug, "name": name, "sort_order": next_category_order, "now": now},
            )
            next_category_order += 1
            category_id = bind.scalar(select_category, {"slug": slug})
        if category_id is None:
            raise RuntimeError(f"0078 could not resolve catalog category {slug}")
        category_ids[name] = category_id
        next_project_order[name] = int(
            bind.scalar(
                sa.text(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
        ) + 1

    select_matching_url = sa.text(
        "SELECT id, destination_url, author_name, author_url FROM catalog_projects "
        "WHERE destination_url = :url ORDER BY id"
    )
    fill_missing_name = sa.text(
        "UPDATE catalog_projects SET author_name = :author_name, updated_at = :now "
        "WHERE id = :id AND (author_name IS NULL OR author_name = '')"
    )
    fill_matching_author_url = sa.text(
        "UPDATE catalog_projects SET author_url = :author_url, updated_at = :now "
        "WHERE id = :id AND (author_url IS NULL OR author_url = '') "
        "AND BINARY author_name = BINARY :author_name"
    )
    select_slug = sa.text("SELECT destination_url FROM catalog_projects WHERE slug = :slug")
    insert_project = sa.text(
        "INSERT INTO catalog_projects "
        "(category_id, slug, name, destination_url, destination_kind, "
        "description, author_name, author_url, sort_order, is_visible, created_at, updated_at) "
        "VALUES (:category_id, :slug, :name, :url, 'external', "
        ":description, :author_name, :author_url, :sort_order, TRUE, :now, :now)"
    )
    for item in entries:
        url = item["url"]
        # 数据库可能按不区分大小写的规则查出候选，Python 再核对完整 URL。
        matching_projects = [
            row
            for row in bind.execute(select_matching_url, {"url": url}).mappings()
            if row["destination_url"] == url
        ]
        if matching_projects:
            # 已收录网址只补空署名；人工署名不同于 README 时，不关联到其他人的主页。
            for project in matching_projects:
                missing_name = project["author_name"] in (None, "")
                if missing_name:
                    bind.execute(
                        fill_missing_name,
                        {"id": project["id"], "author_name": item["author_name"], "now": now},
                    )
                if project["author_url"] in (None, "") and (
                    missing_name or project["author_name"] == item["author_name"]
                ):
                    # 仅原作者一致时补链接；SQL 再按字节比较，避免大小写宽松排序误关联。
                    bind.execute(
                        fill_matching_author_url,
                        {
                            "id": project["id"],
                            "author_name": item["author_name"],
                            "author_url": item["author_url"],
                            "now": now,
                        },
                    )
            continue

        slug = "astra-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        if bind.scalar(select_slug, {"slug": slug}) is not None:
            # 极低概率哈希碰撞或管理员占用标识时停止，不能覆盖其他项目。
            raise RuntimeError(f"0078 catalog project slug collision: {slug}")
        category_name = item["source_category"]
        bind.execute(
            insert_project,
            {
                "category_id": category_ids[category_name],
                "slug": slug,
                "name": item["name"],
                "url": url,
                "description": item["description"],
                "author_name": item["author_name"],
                "author_url": item["author_url"],
                "sort_order": next_project_order[category_name],
                "now": now,
            },
        )
        next_project_order[category_name] += 1

    # 两个既有站点作品只在尚无人工署名时显示原创，不改项目地址与展示分类。
    bind.execute(
        sa.text(
            "UPDATE catalog_projects SET author_name = :author_name, updated_at = :now "
            "WHERE slug IN ('generals-soldiers', 'fablespace') AND author_name IS NULL"
        ),
        {"author_name": "原创", "now": now},
    )


def downgrade() -> None:
    """保留目录数据，避免删除管理员在导入后编辑过的项目。"""

    # 需要下线时由管理员隐藏；自动删除会带走后续人工修改和评分。
    pass
