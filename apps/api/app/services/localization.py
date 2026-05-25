from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.permissions import BOARD_MODERATOR_ROLES, is_global_moderator
from app.db.base import utcnow
from app.models.forum import BoardMember, Topic
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.localization import TopicLocalizationResponse, TopicLocalizationUpdateRequest
from app.services.forum import ForumService

LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2}$")


class LocalizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def topic_localization(
        self,
        topic_id: str,
        locale: str,
        current_user: User | None,
    ) -> TopicLocalizationResponse:
        normalized_locale = self._normalize_locale(locale)
        topic = await ForumService(self.session).get_topic(topic_id, current_user=current_user)
        return self._topic_response(topic, normalized_locale)

    async def update_topic_localization(
        self,
        topic_id: str,
        locale: str,
        payload: TopicLocalizationUpdateRequest,
        current_user: User,
    ) -> TopicLocalizationResponse:
        normalized_locale = self._normalize_locale(locale)
        topic = await ForumService(self.session).get_topic(topic_id, current_user=current_user)
        if not await self._can_localize_topic(topic, current_user):
            raise PermissionDeniedError(
                "content_localization_forbidden",
                "Moderator or board owner permission required",
            )

        localizations = dict(topic.title_localizations or {})
        previous = localizations.get(normalized_locale)
        title = payload.title.strip() if payload.title is not None else None
        if title:
            if len(title) < 2:
                raise ValidationError(
                    "invalid_localized_title",
                    "Localized topic title must contain at least 2 characters",
                )
            localizations[normalized_locale] = title[:180]
        else:
            localizations.pop(normalized_locale, None)

        topic.title_localizations = localizations or None
        topic.updated_at = utcnow()
        self.session.add(
            AuditLog(
                actor_id=current_user.id,
                action="topic_localization_updated",
                target_type="topic",
                target_id=topic.id,
                board_id=topic.board_id,
                data={
                    "locale": normalized_locale,
                    "previous_title": previous,
                    "next_title": localizations.get(normalized_locale),
                },
                created_at=utcnow(),
            )
        )
        await self.session.commit()
        refreshed = await ForumService(self.session).get_topic(topic_id, current_user=current_user)
        return self._topic_response(refreshed, normalized_locale)

    async def _can_localize_topic(self, topic: Topic, current_user: User) -> bool:
        if is_global_moderator(current_user) or topic.board.owner_id == current_user.id:
            return True
        member_role = await self.session.scalar(
            select(BoardMember.role).where(
                BoardMember.board_id == topic.board_id,
                BoardMember.user_id == current_user.id,
            )
        )
        return member_role in BOARD_MODERATOR_ROLES

    def _topic_response(self, topic: Topic, locale: str) -> TopicLocalizationResponse:
        localizations = dict(topic.title_localizations or {})
        title = localizations.get(locale)
        if title is None and "-" in locale:
            title = localizations.get(locale.split("-", 1)[0])
        return TopicLocalizationResponse(
            topic_id=topic.id,
            locale=locale,
            title=title or topic.title,
            fallback_title=topic.title,
            fallback_used=title is None,
            available_locales=sorted(localizations),
        )

    def _normalize_locale(self, locale: str) -> str:
        candidate = locale.strip().replace("_", "-")
        if not LOCALE_PATTERN.fullmatch(candidate):
            raise ValidationError("invalid_locale", "Locale must look like zh-CN or en-US")
        parts = candidate.split("-")
        normalized = [parts[0].lower()]
        for part in parts[1:]:
            normalized.append(part.upper() if len(part) == 2 else part)
        return "-".join(normalized)
