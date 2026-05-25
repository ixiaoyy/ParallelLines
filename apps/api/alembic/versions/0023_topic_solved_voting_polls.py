"""add topic solved voting polls

Revision ID: 0023_topic_solved_voting
Revises: 0022_board_management
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_topic_solved_voting"
down_revision: str | None = "0022_board_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("topics") as batch_op:
        batch_op.add_column(
            sa.Column(
                "accepted_answer_post_id",
                sa.BigInteger(),
                nullable=True,
                comment="被采纳为解决方案的回复帖子 ID；为空表示未解决。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "solved_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="主题被标记为已解决的时间；为空表示未解决。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "solved_by_id",
                sa.BigInteger(),
                nullable=True,
                comment="执行采纳或最后标记解决的用户 ID；为空表示未解决或用户已删除。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "answer_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="是否启用问答排序提示；有采纳答案时通常为 true。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "vote_score",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="主题赞成票减反对票的缓存分数。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "vote_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="主题有效投票数量缓存。",
            )
        )
        batch_op.create_foreign_key(
            "fk_topics_solved_by_id_users",
            "users",
            ["solved_by_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("posts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "vote_score",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="帖子赞成票减反对票的缓存分数。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "vote_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="帖子有效投票数量缓存。",
            )
        )

    op.create_table(
        "votes",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
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
            "target_type",
            sa.String(length=32),
            nullable=False,
            comment="投票目标类型：topic 或 post。",
        ),
        sa.Column("target_id", sa.BigInteger(), nullable=False, comment="投票目标 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="投票用户 ID。"),
        sa.Column(
            "value", sa.Integer(), nullable=False, comment="投票值：1 表示赞成，-1 表示反对。"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_type", "target_id", "user_id", name="uq_votes_target_user"),
        comment="用户对主题或帖子的赞成/反对投票记录。",
    )
    op.create_index("ix_votes_target", "votes", ["target_type", "target_id"])
    op.create_index("ix_votes_user_created", "votes", ["user_id", "created_at"])

    op.create_table(
        "polls",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
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
            "topic_id",
            sa.BigInteger(),
            nullable=False,
            comment="关联主题 ID；首版每个主题最多一个 Poll。",
        ),
        sa.Column("question", sa.String(length=240), nullable=False, comment="Poll 问题文本。"),
        sa.Column(
            "multiple_choice",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否允许多选。",
        ),
        sa.Column(
            "closes_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Poll 截止时间；为空表示不自动截止。",
        ),
        sa.Column(
            "total_votes",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="参与投票的去重用户数量缓存。",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id"),
        comment="主题内简单 Poll 投票组件。",
    )
    op.create_index("ix_polls_topic", "polls", ["topic_id"])

    op.create_table(
        "poll_options",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("poll_id", sa.BigInteger(), nullable=False, comment="所属 Poll ID。"),
        sa.Column("label", sa.String(length=160), nullable=False, comment="选项展示文本。"),
        sa.Column("position", sa.Integer(), nullable=False, comment="选项排序，从 1 开始。"),
        sa.Column(
            "vote_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="选择该选项的投票数量缓存。",
        ),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_id", "position", name="uq_poll_options_poll_position"),
        comment="Poll 的有序候选项。",
    )
    op.create_index("ix_poll_options_poll", "poll_options", ["poll_id"])

    op.create_table(
        "poll_votes",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
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
        sa.Column("poll_id", sa.BigInteger(), nullable=False, comment="所属 Poll ID。"),
        sa.Column(
            "option_id", sa.BigInteger(), nullable=False, comment="被选择的 Poll 选项 ID。"
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="投票用户 ID。"),
        sa.ForeignKeyConstraint(["option_id"], ["poll_options.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("option_id", "user_id", name="uq_poll_votes_option_user"),
        comment="用户对 Poll 选项的选择记录。",
    )
    op.create_index("ix_poll_votes_poll_user", "poll_votes", ["poll_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_poll_votes_poll_user", table_name="poll_votes")
    op.drop_table("poll_votes")
    op.drop_index("ix_poll_options_poll", table_name="poll_options")
    op.drop_table("poll_options")
    op.drop_index("ix_polls_topic", table_name="polls")
    op.drop_table("polls")
    op.drop_index("ix_votes_user_created", table_name="votes")
    op.drop_index("ix_votes_target", table_name="votes")
    op.drop_table("votes")

    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_column("vote_count")
        batch_op.drop_column("vote_score")

    with op.batch_alter_table("topics") as batch_op:
        batch_op.drop_constraint("fk_topics_solved_by_id_users", type_="foreignkey")
        batch_op.drop_column("vote_count")
        batch_op.drop_column("vote_score")
        batch_op.drop_column("answer_mode")
        batch_op.drop_column("solved_by_id")
        batch_op.drop_column("solved_at")
        batch_op.drop_column("accepted_answer_post_id")
