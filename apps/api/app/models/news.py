from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type

if TYPE_CHECKING:
    from app.models.forum import Topic
    from app.models.moderation import Reviewable
    from app.models.user import User

FrontierNewsSourceKind = Literal[
    "rss",
    "arxiv",
    "hacker_news",
    "github_search",
    "xai_news",
    "arena_leaderboard",
]
FrontierNewsItemStatus = Literal[
    "collected",
    "ai_pending",
    "review_pending",
    "published",
    "rejected",
    "duplicate",
    "failed",
]
FrontierNewsAiRunStatus = Literal["succeeded", "failed"]


class FrontierNewsSource(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    """White-listed upstream feed or API used by the frontier news collector."""

    __tablename__ = "frontier_news_sources"
    __table_args__ = (
        UniqueConstraint("key", name="uq_frontier_news_sources_key"),
        Index("ix_frontier_news_sources_enabled_checked", "enabled", "last_checked_at"),
        {"comment": "前沿资讯白名单来源，保存抓取配置、频率和最近一次抓取状态。"},
    )

    key: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        comment="稳定来源键，用于默认来源幂等初始化。",
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, comment="来源显示名称。")
    kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="来源类型：rss、arxiv、hacker_news、github_search、xai_news 或 arena_leaderboard。",
    )
    url: Mapped[str] = mapped_column(String(1024), nullable=False, comment="抓取入口 URL。")
    config: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="来源特定配置，如关键词、分类、最大条数或 GitHub 查询。",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用该来源的定时抓取。",
    )
    trust_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="来源可信度评分，影响素材优先级；范围 0-100。",
    )
    fetch_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="该来源建议抓取间隔，单位分钟。",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="最近一次尝试抓取时间；为空表示尚未抓取。",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        comment="最近一次抓取失败摘要；成功后清空。",
    )

    items: Mapped[list[FrontierNewsItem]] = relationship(
        "FrontierNewsItem",
        back_populates="source",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class FrontierNewsItem(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    """Collected frontier-news material and its AI-prepared Chinese review draft."""

    __tablename__ = "frontier_news_items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_frontier_news_items_source_external"),
        UniqueConstraint("canonical_url_hash", name="uq_frontier_news_items_url_hash"),
        Index("ix_frontier_news_items_status_created", "status", "created_at"),
        Index("ix_frontier_news_items_source_published", "source_id", "published_at"),
        Index("ix_frontier_news_items_reviewable", "reviewable_id"),
        {"comment": "前沿资讯素材池，保存原文元数据、AI 中文整理结果和审核发布关联。"},
    )

    source_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("frontier_news_sources.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联资讯来源 ID。",
    )
    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="来源内唯一 ID；RSS 可用 guid/link，API 可用资源 ID。",
    )
    canonical_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="规范化原文 URL，用于去重和审核追溯。",
    )
    canonical_url_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="规范化 URL 的 SHA-256 哈希，用于跨来源去重。",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="原文标题。")
    summary: Mapped[str | None] = mapped_column(Text, comment="原文摘要或抓取摘录。")
    author_names: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="来源提供的作者名称列表。",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="来源原文发布时间；为空表示来源未提供。",
    )
    raw_payload: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="安全截断后的来源原始载荷，便于排查抓取解析问题。",
    )
    item_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="news",
        comment="AI 判定的内容类型，如 news、paper、tool、discussion。",
    )
    suggested_tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="AI 建议的论坛标签数组。",
    )
    ai_title_zh: Mapped[str | None] = mapped_column(
        String(180),
        comment="AI 整理后的中文标题，进入审核队列时作为主题标题。",
    )
    ai_summary_zh: Mapped[str | None] = mapped_column(
        Text,
        comment="AI 翻译整理后的中文摘要。",
    )
    ai_key_points: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="AI 提炼的中文要点列表。",
    )
    ai_why_it_matters: Mapped[str | None] = mapped_column(
        Text,
        comment="AI 对该资讯价值/影响的中文说明。",
    )
    ai_risk_flags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="AI 标记的审核风险，如信息不足、营销味重或需要事实核验。",
    )
    ai_review_suggestion: Mapped[str | None] = mapped_column(
        String(64),
        comment="AI 给人工审核的建议：ready、needs_edit 或 skip。",
    )
    ai_model_name: Mapped[str | None] = mapped_column(
        String(120),
        comment="执行整理的 AI 模型或本地策略名称。",
    )
    ai_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="AI 整理完成时间；为空表示尚未整理。",
    )
    ai_error: Mapped[str | None] = mapped_column(Text, comment="最近一次 AI 整理失败摘要。")
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="素材质量/相关性评分，影响审核优先级；范围 0-100。",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="collected",
        comment=(
            "素材状态：collected、ai_pending、review_pending、published、rejected、"
            "duplicate 或 failed。"
        ),
    )
    reviewable_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("reviewables.id", ondelete="SET NULL"),
        comment="进入统一审核队列后的审核对象 ID。",
    )
    topic_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("topics.id", ondelete="SET NULL"),
        comment="审核通过后自动发布生成的主题 ID。",
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="最终审核处理人 ID。",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="最终审核处理时间；未处理时为空。",
    )
    review_note: Mapped[str | None] = mapped_column(Text, comment="审核处理备注或拒绝原因。")

    source: Mapped[FrontierNewsSource] = relationship(
        "FrontierNewsSource",
        back_populates="items",
        lazy="selectin",
    )
    reviewable: Mapped[Reviewable | None] = relationship("Reviewable", lazy="selectin")
    topic: Mapped[Topic | None] = relationship("Topic", lazy="selectin")
    reviewed_by: Mapped[User | None] = relationship("User", lazy="selectin")
    ai_runs: Mapped[list[FrontierNewsAiRun]] = relationship(
        "FrontierNewsAiRun",
        back_populates="item",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class FrontierNewsAiRun(IntegerPrimaryKeyMixin, Base):
    """Audit trail for each AI pass that prepared a frontier news item."""

    __tablename__ = "frontier_news_ai_runs"
    __table_args__ = (
        Index("ix_frontier_news_ai_runs_item_created", "item_id", "created_at"),
        {"comment": "前沿资讯 AI 整理运行记录，保存模型、成本、状态和错误。"},
    )

    item_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("frontier_news_items.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联资讯素材 ID。",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="AI 运行状态：succeeded 或 failed。",
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="AI provider 标识；local 表示本地确定性整理。",
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, comment="模型或策略名称。")
    prompt_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="整理提示词/策略版本，便于后续复盘。",
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="输入 token 估算；本地策略为 0。",
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="输出 token 估算；本地策略为 0。",
    )
    cost_units: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="AI 成本单位，保留整数便于未来接入真实 provider。",
    )
    error: Mapped[str | None] = mapped_column(Text, comment="失败摘要；成功时为空。")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="AI 运行记录创建时间（UTC）。",
    )

    item: Mapped[FrontierNewsItem] = relationship(
        "FrontierNewsItem",
        back_populates="ai_runs",
        lazy="selectin",
    )
