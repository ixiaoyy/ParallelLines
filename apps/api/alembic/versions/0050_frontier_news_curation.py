"""frontier news curation

Revision ID: 0050_frontier_news_curation
Revises: 0049_topic_views
Create Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from secrets import token_urlsafe

import sqlalchemy as sa

from alembic import op

revision: str = "0050_frontier_news_curation"
down_revision: str | None = "0049_topic_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOT_USERNAME = "资讯机器人"
BOT_EMAIL = "frontier-news-bot@parallellines.local"
FRONTIER_BOARD_SLUG = "frontier"

users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("email", sa.String()),
    sa.column("hashed_password", sa.String()),
    sa.column("avatar_url", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("bio", sa.Text()),
    sa.column("website_url", sa.String()),
    sa.column("location", sa.String()),
    sa.column("role", sa.String()),
    sa.column("level", sa.Integer()),
    sa.column("trust_level", sa.Integer()),
    sa.column("trust_level_changed_at", sa.DateTime(timezone=True)),
    sa.column("points_balance", sa.Integer()),
    sa.column("experience_total", sa.Integer()),
    sa.column("status", sa.String()),
    sa.column("last_seen_at", sa.DateTime(timezone=True)),
    sa.column("two_factor_enabled", sa.Boolean()),
    sa.column("two_factor_secret", sa.String()),
    sa.column("profile_visibility", sa.String()),
    sa.column("show_activity", sa.Boolean()),
    sa.column("interface_theme", sa.String()),
    sa.column("locale", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("name_localizations", sa.JSON()),
    sa.column("description", sa.Text()),
    sa.column("color", sa.String()),
    sa.column("avatar_url", sa.String()),
    sa.column("owner_id", sa.BigInteger()),
    sa.column("parent_board_id", sa.BigInteger()),
    sa.column("visibility", sa.String()),
    sa.column("required_tags", sa.JSON()),
    sa.column("allowed_tags", sa.JSON()),
    sa.column("post_template", sa.Text()),
    sa.column("default_notification_level", sa.String()),
    sa.column("default_sort", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
    sa.column("follower_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

frontier_news_sources = sa.table(
    "frontier_news_sources",
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("kind", sa.String()),
    sa.column("url", sa.String()),
    sa.column("config", sa.JSON()),
    sa.column("enabled", sa.Boolean()),
    sa.column("trust_level", sa.Integer()),
    sa.column("fetch_interval_minutes", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


# upgrade creates the curation schema and seeds the ordinary bot user / frontier board when safe.
def upgrade() -> None:
    op.create_table(
        "frontier_news_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="主键 ID。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录创建时间（UTC）。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录最后更新时间（UTC）。",
        ),
        sa.Column(
            "key",
            sa.String(length=96),
            nullable=False,
            comment="稳定来源键，用于默认来源幂等初始化。",
        ),
        sa.Column("name", sa.String(length=120), nullable=False, comment="来源显示名称。"),
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            comment="来源类型：rss、arxiv、hacker_news 或 github_search。",
        ),
        sa.Column("url", sa.String(length=1024), nullable=False, comment="抓取入口 URL。"),
        sa.Column(
            "config",
            sa.JSON(),
            nullable=False,
            comment="来源特定配置，如关键词、分类、最大条数或 GitHub 查询。",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="是否启用该来源的定时抓取。",
        ),
        sa.Column(
            "trust_level",
            sa.Integer(),
            nullable=False,
            server_default="50",
            comment="来源可信度评分，影响素材优先级；范围 0-100。",
        ),
        sa.Column(
            "fetch_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
            comment="该来源建议抓取间隔，单位分钟。",
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最近一次尝试抓取时间；为空表示尚未抓取。",
        ),
        sa.Column(
            "last_error", sa.Text(), nullable=True, comment="最近一次抓取失败摘要；成功后清空。"
        ),
        sa.UniqueConstraint("key", name="uq_frontier_news_sources_key"),
        comment="前沿资讯白名单来源，保存抓取配置、频率和最近一次抓取状态。",
    )
    op.create_index(
        "ix_frontier_news_sources_enabled_checked",
        "frontier_news_sources",
        ["enabled", "last_checked_at"],
    )

    op.create_table(
        "frontier_news_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="主键 ID。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录创建时间（UTC）。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录最后更新时间（UTC）。",
        ),
        sa.Column("source_id", sa.BigInteger(), nullable=False, comment="关联资讯来源 ID。"),
        sa.Column(
            "external_id",
            sa.String(length=255),
            nullable=False,
            comment="来源内唯一 ID；RSS 可用 guid/link，API 可用资源 ID。",
        ),
        sa.Column(
            "canonical_url",
            sa.String(length=1024),
            nullable=False,
            comment="规范化原文 URL，用于去重和审核追溯。",
        ),
        sa.Column(
            "canonical_url_hash",
            sa.String(length=64),
            nullable=False,
            comment="规范化 URL 的 SHA-256 哈希，用于跨来源去重。",
        ),
        sa.Column("title", sa.String(length=500), nullable=False, comment="原文标题。"),
        sa.Column("summary", sa.Text(), nullable=True, comment="原文摘要或抓取摘录。"),
        sa.Column("author_names", sa.JSON(), nullable=False, comment="来源提供的作者名称列表。"),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="来源原文发布时间；为空表示来源未提供。",
        ),
        sa.Column(
            "raw_payload",
            sa.JSON(),
            nullable=False,
            comment="安全截断后的来源原始载荷，便于排查抓取解析问题。",
        ),
        sa.Column(
            "item_type",
            sa.String(length=32),
            nullable=False,
            server_default="news",
            comment="AI 判定的内容类型，如 news、paper、tool、discussion。",
        ),
        sa.Column("suggested_tags", sa.JSON(), nullable=False, comment="AI 建议的论坛标签数组。"),
        sa.Column(
            "ai_title_zh",
            sa.String(length=180),
            nullable=True,
            comment="AI 整理后的中文标题，进入审核队列时作为主题标题。",
        ),
        sa.Column("ai_summary_zh", sa.Text(), nullable=True, comment="AI 翻译整理后的中文摘要。"),
        sa.Column("ai_key_points", sa.JSON(), nullable=False, comment="AI 提炼的中文要点列表。"),
        sa.Column(
            "ai_why_it_matters",
            sa.Text(),
            nullable=True,
            comment="AI 对该资讯价值/影响的中文说明。",
        ),
        sa.Column(
            "ai_risk_flags",
            sa.JSON(),
            nullable=False,
            comment="AI 标记的审核风险，如信息不足、营销味重或需要事实核验。",
        ),
        sa.Column(
            "ai_review_suggestion",
            sa.String(length=64),
            nullable=True,
            comment="AI 给人工审核的建议：ready、needs_edit 或 skip。",
        ),
        sa.Column(
            "ai_model_name",
            sa.String(length=120),
            nullable=True,
            comment="执行整理的 AI 模型或本地策略名称。",
        ),
        sa.Column(
            "ai_processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="AI 整理完成时间；为空表示尚未整理。",
        ),
        sa.Column("ai_error", sa.Text(), nullable=True, comment="最近一次 AI 整理失败摘要。"),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="素材质量/相关性评分，影响审核优先级；范围 0-100。",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="collected",
            comment=(
                "素材状态：collected、ai_pending、review_pending、published、rejected、"
                "duplicate 或 failed。"
            ),
        ),
        sa.Column(
            "reviewable_id",
            sa.BigInteger(),
            nullable=True,
            comment="进入统一审核队列后的审核对象 ID。",
        ),
        sa.Column(
            "topic_id", sa.BigInteger(), nullable=True, comment="审核通过后自动发布生成的主题 ID。"
        ),
        sa.Column("reviewed_by_id", sa.BigInteger(), nullable=True, comment="最终审核处理人 ID。"),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最终审核处理时间；未处理时为空。",
        ),
        sa.Column("review_note", sa.Text(), nullable=True, comment="审核处理备注或拒绝原因。"),
        sa.ForeignKeyConstraint(["source_id"], ["frontier_news_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewable_id"], ["reviewables.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "source_id", "external_id", name="uq_frontier_news_items_source_external"
        ),
        sa.UniqueConstraint("canonical_url_hash", name="uq_frontier_news_items_url_hash"),
        comment="前沿资讯素材池，保存原文元数据、AI 中文整理结果和审核发布关联。",
    )
    op.create_index(
        "ix_frontier_news_items_status_created", "frontier_news_items", ["status", "created_at"]
    )
    op.create_index(
        "ix_frontier_news_items_source_published",
        "frontier_news_items",
        ["source_id", "published_at"],
    )
    op.create_index("ix_frontier_news_items_reviewable", "frontier_news_items", ["reviewable_id"])

    op.create_table(
        "frontier_news_ai_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="主键 ID。"),
        sa.Column("item_id", sa.BigInteger(), nullable=False, comment="关联资讯素材 ID。"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="AI 运行状态：succeeded 或 failed。",
        ),
        sa.Column(
            "provider",
            sa.String(length=64),
            nullable=False,
            comment="AI provider 标识；local 表示本地确定性整理。",
        ),
        sa.Column("model_name", sa.String(length=120), nullable=False, comment="模型或策略名称。"),
        sa.Column(
            "prompt_version",
            sa.String(length=32),
            nullable=False,
            comment="整理提示词/策略版本，便于后续复盘。",
        ),
        sa.Column(
            "input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="输入 token 估算；本地策略为 0。",
        ),
        sa.Column(
            "output_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="输出 token 估算；本地策略为 0。",
        ),
        sa.Column(
            "cost_units",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="AI 成本单位，保留整数便于未来接入真实 provider。",
        ),
        sa.Column("error", sa.Text(), nullable=True, comment="失败摘要；成功时为空。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="AI 运行记录创建时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["frontier_news_items.id"], ondelete="CASCADE"),
        comment="前沿资讯 AI 整理运行记录，保存模型、成本、状态和错误。",
    )
    op.create_index(
        "ix_frontier_news_ai_runs_item_created", "frontier_news_ai_runs", ["item_id", "created_at"]
    )

    bind = op.get_bind()
    bot_id = ensure_bot_user(bind)
    ensure_frontier_board(bind, bot_id)
    seed_default_sources(bind)


# downgrade drops the feature-owned tables but intentionally preserves seeded users/boards/content.
def downgrade() -> None:
    op.drop_index("ix_frontier_news_ai_runs_item_created", table_name="frontier_news_ai_runs")
    op.drop_table("frontier_news_ai_runs")
    op.drop_index("ix_frontier_news_items_reviewable", table_name="frontier_news_items")
    op.drop_index("ix_frontier_news_items_source_published", table_name="frontier_news_items")
    op.drop_index("ix_frontier_news_items_status_created", table_name="frontier_news_items")
    op.drop_table("frontier_news_items")
    op.drop_index("ix_frontier_news_sources_enabled_checked", table_name="frontier_news_sources")
    op.drop_table("frontier_news_sources")


# now returns an aware UTC timestamp for seeded records.
def now() -> datetime:
    return datetime.now(UTC)


# ensure_bot_user creates the ordinary publishing bot without sessions or API keys.
def ensure_bot_user(bind: sa.Connection) -> int | None:
    if not table_exists(bind, "users"):
        return None
    username_row = bind.execute(
        sa.select(users.c.id, users.c.email).where(users.c.username == BOT_USERNAME)
    ).first()
    email_row = bind.execute(
        sa.select(users.c.id, users.c.username).where(users.c.email == BOT_EMAIL)
    ).first()
    if username_row and email_row and username_row.id == email_row.id:
        return int(username_row.id)
    if username_row or email_row:
        return None
    from app.core.security import hash_password

    current_time = now()
    bind.execute(
        users.insert().values(
            username=BOT_USERNAME,
            email=BOT_EMAIL,
            hashed_password=hash_password(token_urlsafe(48)),
            avatar_url=None,
            display_name=BOT_USERNAME,
            bio=None,
            website_url=None,
            location=None,
            role="user",
            level=0,
            trust_level=0,
            trust_level_changed_at=None,
            points_balance=0,
            experience_total=0,
            status="active",
            last_seen_at=None,
            two_factor_enabled=False,
            two_factor_secret=None,
            profile_visibility="public",
            show_activity=True,
            interface_theme="system",
            locale="zh-CN",
            created_at=current_time,
            updated_at=current_time,
        )
    )
    return int(
        bind.execute(sa.select(users.c.id).where(users.c.username == BOT_USERNAME)).scalar_one()
    )


# ensure_frontier_board creates the selected board slug or safely renames the legacy news board.
def ensure_frontier_board(bind: sa.Connection, owner_id: int | None) -> None:
    if not table_exists(bind, "boards"):
        return
    existing = bind.execute(
        sa.select(boards.c.id).where(boards.c.slug == FRONTIER_BOARD_SLUG)
    ).first()
    if existing:
        return
    legacy = bind.execute(
        sa.select(boards.c.id).where(
            boards.c.slug == "news", boards.c.name.in_(["前沿快讯", "前沿资讯"])
        )
    ).first()
    if legacy:
        bind.execute(
            boards.update()
            .where(boards.c.id == legacy.id)
            .values(
                slug=FRONTIER_BOARD_SLUG,
                name="前沿资讯",
                description="自动汇集 AI、科技、研究论文与开源工具动态，经人工审核后发布。",
                updated_at=now(),
            )
        )
        return
    current_time = now()
    bind.execute(
        boards.insert().values(
            slug=FRONTIER_BOARD_SLUG,
            name="前沿资讯",
            name_localizations=None,
            description="自动汇集 AI、科技、研究论文与开源工具动态，经人工审核后发布。",
            color="#6366f1",
            avatar_url=None,
            owner_id=owner_id,
            parent_board_id=None,
            visibility="public",
            required_tags=None,
            allowed_tags=None,
            post_template=None,
            default_notification_level="normal",
            default_sort="latest",
            topic_count=0,
            post_count=0,
            follower_count=0,
            created_at=current_time,
            updated_at=current_time,
        )
    )


# seed_default_sources initializes a conservative white-list while allowing admins to edit later.
def seed_default_sources(bind: sa.Connection) -> None:
    current_time = now()
    rows = (
        {
            "key": "arxiv_ai_llm",
            "name": "arXiv AI / LLM 论文",
            "kind": "arxiv",
            "url": "https://export.arxiv.org/api/query",
            "config": {
                "categories": ["cs.AI", "cs.CL", "cs.LG"],
                "max_items": 12,
                "review_batch_size": 3,
            },
            "trust_level": 90,
            "fetch_interval_minutes": 240,
        },
        {
            "key": "hacker_news_ai",
            "name": "Hacker News AI 热点",
            "kind": "hacker_news",
            "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
            "config": {"max_items": 18, "candidate_items": 80, "review_batch_size": 3},
            "trust_level": 65,
            "fetch_interval_minutes": 120,
        },
        {
            "key": "github_ai_trending",
            "name": "GitHub AI 项目动态",
            "kind": "github_search",
            "url": "https://api.github.com/search/repositories",
            "config": {
                "query": "topic:llm stars:>100",
                "sort": "updated",
                "order": "desc",
                "max_items": 15,
                "review_batch_size": 3,
            },
            "trust_level": 70,
            "fetch_interval_minutes": 240,
        },
        {
            "key": "huggingface_blog",
            "name": "Hugging Face Blog",
            "kind": "rss",
            "url": "https://huggingface.co/blog/feed.xml",
            "config": {"max_items": 12, "review_batch_size": 3},
            "trust_level": 80,
            "fetch_interval_minutes": 240,
        },
    )
    for row in rows:
        exists = bind.execute(
            sa.select(frontier_news_sources.c.key).where(frontier_news_sources.c.key == row["key"])
        ).first()
        if exists:
            continue
        bind.execute(
            frontier_news_sources.insert().values(
                **row,
                enabled=True,
                created_at=current_time,
                updated_at=current_time,
            )
        )


# table_exists protects content seeding on unusual partial schemas during tests.
def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)
