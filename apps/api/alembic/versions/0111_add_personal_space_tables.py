"""创建个人空间手账与轻量记账表。

Revision ID: 0111_add_personal_space_tables
Revises: 0110_add_six_featured_games
Create Date: 2026-11-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0111_add_personal_space_tables"
down_revision: str | None = "0110_add_six_featured_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "space_settings",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
            comment="主键 ID；数据库使用数值自增 BIGINT，API 层按字符串返回。",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="所属用户 ID。",
        ),
        sa.Column(
            "space_title",
            sa.String(80),
            nullable=False,
            server_default="",
            comment="个人空间自定义标题；为空时前端使用昵称默认名称。",
        ),
        sa.Column(
            "space_subtitle",
            sa.String(200),
            nullable=False,
            server_default="",
            comment="个人空间顶栏签名或心情寄语。",
        ),
        sa.Column(
            "cover_preset",
            sa.String(32),
            nullable=False,
            server_default="aurora",
            comment="个人空间封面主题预设标识，如 aurora、sunset、meadow、paper、starlight。",
        ),
        sa.Column(
            "monthly_budget_cents",
            sa.BigInteger(),
            nullable=False,
            server_default="300000",
            comment="个人账本月度预算金额（单位：分），仅用户本人可见。",
        ),
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
        sa.UniqueConstraint("user_id", name="uq_space_settings_user_id"),
        comment="个人空间个性化设置，保存封面主题、签名与月度记账预算。",
    )
    op.create_index("ix_space_settings_user_id", "space_settings", ["user_id"])

    op.create_table(
        "space_journal_entries",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
            comment="主键 ID；数据库使用数值自增 BIGINT，API 层按字符串返回。",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="手账作者用户 ID。",
        ),
        sa.Column(
            "entry_date",
            sa.String(10),
            nullable=False,
            comment="手账归属日期（YYYY-MM-DD），用于心情日历与按日检索。",
        ),
        sa.Column(
            "title",
            sa.String(160),
            nullable=False,
            server_default="",
            comment="手账可选短标题；为空表示纯闪念/碎碎念卡片。",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="手账正文内容，支持轻量文本与标签记录。",
        ),
        sa.Column(
            "mood",
            sa.String(32),
            nullable=False,
            server_default="happy",
            comment="当日心情贴纸标识，如 happy、focused、calm、cozy、inspired、tired、rainy、celebrate。",
        ),
        sa.Column(
            "weather",
            sa.String(32),
            nullable=False,
            server_default="sunny",
            comment="当日天气或状态图标标识，如 sunny、cloudy、breezy、rainy、snowy、night。",
        ),
        sa.Column(
            "location",
            sa.String(80),
            nullable=False,
            server_default="",
            comment="手账可选地点或场景小标，如 书桌前、咖啡馆、通勤路上。",
        ),
        sa.Column(
            "visibility",
            sa.String(16),
            nullable=False,
            server_default="public",
            comment="可见性范围：public 表示公开到个人空间与圈子，private 表示仅自己可见。",
        ),
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="是否在个人空间置顶展示。",
        ),
        sa.Column(
            "card_theme",
            sa.String(32),
            nullable=False,
            server_default="paper",
            comment="手账信纸视觉主题：paper、sky、mint、sunset、lavender、grid。",
        ),
        sa.Column(
            "tags",
            sa.JSON(),
            nullable=False,
            comment="手账关联的标签字符串数组。",
        ),
        sa.Column(
            "media_urls",
            sa.JSON(),
            nullable=False,
            comment="手账配图 URL 列表（最多 9 张）。",
        ),
        sa.Column(
            "checklist",
            sa.JSON(),
            nullable=False,
            comment="手账内嵌打卡/待办清单项列表，每项包含 id、text、done。",
        ),
        sa.Column(
            "ledger_snapshot",
            sa.JSON(),
            nullable=True,
            comment="可选关联的记账摘要或月度账单快照卡片数据；为空表示普通手账。",
        ),
        sa.Column(
            "likes_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="手账收到的暖心点赞互动次数。",
        ),
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
        comment="个人空间手账与日常闪念记录，保存心情、天气、配图、清单及公开/私密范围。",
    )
    op.create_index(
        "ix_space_journal_entries_user_date",
        "space_journal_entries",
        ["user_id", "entry_date"],
    )
    op.create_index(
        "ix_space_journal_entries_user_vis_created",
        "space_journal_entries",
        ["user_id", "visibility", "created_at"],
    )
    op.create_index(
        "ix_space_journal_entries_vis_created",
        "space_journal_entries",
        ["visibility", "created_at"],
    )

    op.create_table(
        "space_ledger_entries",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
            comment="主键 ID；数据库使用数值自增 BIGINT，API 层按字符串返回。",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="记账所属用户 ID；账本明细严格仅本人可见。",
        ),
        sa.Column(
            "entry_date",
            sa.String(10),
            nullable=False,
            comment="记账发生日期（YYYY-MM-DD）。",
        ),
        sa.Column(
            "kind",
            sa.String(16),
            nullable=False,
            server_default="expense",
            comment="收支类型：expense（支出）或 income（收入）。",
        ),
        sa.Column(
            "amount_cents",
            sa.BigInteger(),
            nullable=False,
            comment="记账金额（单位：分，正整数）。",
        ),
        sa.Column(
            "category",
            sa.String(32),
            nullable=False,
            server_default="dining",
            comment="收支分类标识，如 dining、coffee、gaming、shopping、transit、entertainment、housing、salary、other。",
        ),
        sa.Column(
            "note",
            sa.String(200),
            nullable=False,
            server_default="",
            comment="记账一句话备注。",
        ),
        sa.Column(
            "payment_method",
            sa.String(32),
            nullable=False,
            server_default="wechat",
            comment="支付或入账方式标识，如 wechat、alipay、card、cash。",
        ),
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
        comment="个人空间轻量记账明细，保存收支分类、金额与备注（严格仅本人可见）。",
    )
    op.create_index(
        "ix_space_ledger_entries_user_date",
        "space_ledger_entries",
        ["user_id", "entry_date"],
    )
    op.create_index(
        "ix_space_ledger_entries_user_kind_date",
        "space_ledger_entries",
        ["user_id", "kind", "entry_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_space_ledger_entries_user_kind_date", table_name="space_ledger_entries")
    op.drop_index("ix_space_ledger_entries_user_date", table_name="space_ledger_entries")
    op.drop_table("space_ledger_entries")

    op.drop_index("ix_space_journal_entries_vis_created", table_name="space_journal_entries")
    op.drop_index("ix_space_journal_entries_user_vis_created", table_name="space_journal_entries")
    op.drop_index("ix_space_journal_entries_user_date", table_name="space_journal_entries")
    op.drop_table("space_journal_entries")

    op.drop_index("ix_space_settings_user_id", table_name="space_settings")
    op.drop_table("space_settings")
