from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.draft import Draft


class DraftService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_draft(self, user_id: str, target_type: str, target_id: str) -> Draft | None:
        return await self.session.scalar(
            select(Draft).where(
                Draft.user_id == user_id,
                Draft.target_type == target_type,
                Draft.target_id == target_id,
            )
        )

    async def list_drafts_by_user(self, user_id: str) -> list[Draft]:
        statement = select(Draft).where(Draft.user_id == user_id).order_by(Draft.updated_at.desc())
        return list(await self.session.scalars(statement))

    async def save_draft(
        self,
        user_id: str,
        target_type: str,
        target_id: str,
        draft_type: str,
        data: dict[str, Any],
        version: int,
    ) -> Draft:
        existing = await self.get_draft(user_id, target_type, target_id)
        if existing:
            if version <= existing.version:
                raise ConflictError(
                    code="draft_conflict",
                    message="A newer draft version exists on the server.",
                    details={"server_version": existing.version, "client_version": version},
                )
            existing.draft_type = draft_type
            existing.data = data
            existing.version = version
            await self.session.commit()
            return existing
        else:
            draft = Draft(
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                draft_type=draft_type,
                data=data,
                version=version,
            )
            self.session.add(draft)
            await self.session.commit()
            return draft

    async def delete_draft(self, user_id: str, target_type: str, target_id: str) -> bool:
        draft = await self.get_draft(user_id, target_type, target_id)
        if draft:
            await self.session.delete(draft)
            await self.session.commit()
            return True
        return False
