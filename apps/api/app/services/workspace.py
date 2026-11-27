from typing import Never

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.base import utcnow
from app.models.workspace import UserWorkspaceConfig
from app.schemas.workspace import (
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceConfigSnapshot,
    WorkspaceConfigUpdate,
)

# 该表只有 user_id 一个唯一键。只把 MySQL 的重复键错误作为并发首创冲突。
MYSQL_DUPLICATE_KEY = 1062


class WorkspaceConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: str) -> WorkspaceConfigSnapshot:
        """按已鉴权的账号读取一行；未创建时返回空快照，不隐式写入。"""
        row = await self.session.get(UserWorkspaceConfig, user_id)
        if row is None:
            return WorkspaceConfigSnapshot(
                revision="0", schema_version=WORKSPACE_SCHEMA_VERSION, config=None, updated_at=None
            )
        return WorkspaceConfigSnapshot(
            revision=str(row.revision),
            schema_version=row.schema_version,
            config=row.config_json,
            updated_at=row.updated_at,
        )

    async def save(self, user_id: str, payload: WorkspaceConfigUpdate) -> WorkspaceConfigSnapshot:
        """首次只插入；后续只更新匹配基准版本的本人配置，提交后才返回新快照。"""
        expected = int(payload.expected_revision)
        now = utcnow()
        table = UserWorkspaceConfig.__table__
        values = {
            "config_json": payload.config,
            "schema_version": payload.schema_version,
            "updated_at": now,
        }
        if expected == 0:
            try:
                await self.session.execute(
                    insert(table).values(user_id=user_id, created_at=now, revision=1, **values)
                )
            except IntegrityError as exc:
                if getattr(exc.orig, "args", ())[:1] != (MYSQL_DUPLICATE_KEY,):
                    raise
                await self._raise_conflict(user_id, payload.expected_revision)
        else:
            # 在同一条 UPDATE 内比较并递增，避免先查再覆盖另一台设备的写入。
            result = await self.session.execute(
                update(table)
                .where(table.c.user_id == user_id, table.c.revision == expected)
                .values(revision=table.c.revision + 1, **values)
            )
            if result.rowcount == 0:
                await self._raise_conflict(user_id, payload.expected_revision)
            if result.rowcount != 1:
                raise RuntimeError("Unexpected workspace config update rowcount")
        await self.session.commit()
        return WorkspaceConfigSnapshot(
            revision=str(expected + 1),
            schema_version=payload.schema_version,
            config=payload.config,
            updated_at=now,
        )

    async def _raise_conflict(self, user_id: str, expected_revision: str) -> Never:
        """先释放失败写入和原快照，再单查当前用户的版本，不返回配置正文。"""
        await self.session.rollback()
        table = UserWorkspaceConfig.__table__
        revision = await self.session.scalar(
            select(table.c.revision).where(table.c.user_id == user_id)
        )
        raise ConflictError(
            "workspace_revision_conflict",
            "云端配置已变更，当前修改未保存。请获取最新版本后再保存。",
            {
                "expected_revision": expected_revision,
                "current_revision": str(revision) if revision is not None else "0",
            },
        ) from None
