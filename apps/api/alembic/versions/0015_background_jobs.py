"""add background job queue

Revision ID: 0015_background_jobs
Revises: 0014_admin_site_settings
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_background_jobs"
down_revision: str | None = "0014_admin_site_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("queue", sa.String(length=64), nullable=False, comment="任务队列名称。"),
        sa.Column("task_name", sa.String(length=128), nullable=False, comment="任务处理器名称。"),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
            comment="任务 JSON 载荷；不包含密码或大正文，邮件任务可含一次性发送密钥。",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="任务状态：queued、running、succeeded 或 dead。",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=255),
            nullable=True,
            comment="幂等键；非空时相同键只允许一个任务。",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, comment="任务优先级。"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, comment="最早可执行时间。"),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="已尝试执行次数。"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, comment="最大尝试次数。"),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="任务被 worker 领取时间；为空表示未锁定。",
        ),
        sa.Column(
            "locked_by",
            sa.String(length=128),
            nullable=True,
            comment="领取任务的 worker 标识。",
        ),
        sa.Column("last_error", sa.Text(), nullable=True, comment="最近一次失败错误摘要。"),
        sa.Column("result", sa.JSON(), nullable=True, comment="任务结果摘要。"),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="任务最终完成或进入死信时间。",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        comment="后台任务队列，保存待执行、重试、成功和死信任务。",
    )
    op.create_index(
        "ix_background_jobs_status_run",
        "background_jobs",
        ["status", "run_at", "priority", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_background_jobs_task_status",
        "background_jobs",
        ["task_name", "status"],
        unique=False,
    )
    op.create_table(
        "background_job_logs",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("job_id", sa.BigInteger(), nullable=False, comment="关联后台任务 ID。"),
        sa.Column("event", sa.String(length=64), nullable=False, comment="任务事件类型。"),
        sa.Column("message", sa.Text(), nullable=False, comment="事件说明。"),
        sa.Column(
            "data",
            sa.JSON(),
            nullable=False,
            comment="事件结构化上下文，不包含密码、令牌或邮件密钥。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="事件发生时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="后台任务执行事件日志，用于排查失败、重试和死信。",
    )
    op.create_index(
        "ix_background_job_logs_job_created",
        "background_job_logs",
        ["job_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_background_job_logs_job_created", table_name="background_job_logs")
    op.drop_table("background_job_logs")
    op.drop_index("ix_background_jobs_task_status", table_name="background_jobs")
    op.drop_index("ix_background_jobs_status_run", table_name="background_jobs")
    op.drop_table("background_jobs")
