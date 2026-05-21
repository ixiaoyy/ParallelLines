from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.base import utcnow
from app.models.admin import SiteSetting
from app.models.email import EmailDeliveryEvent, InboundEmail, UserEmailPreference
from app.models.forum import Topic
from app.models.interaction import Notification
from app.models.user import User
from app.schemas.email import (
    EmailDeliveryEventResponse,
    EmailDeliveryWebhookRequest,
    EmailPreferenceResponse,
    EmailPreferenceUpdateRequest,
    InboundEmailResponse,
    InboundEmailWebhookRequest,
)
from app.services.background_jobs import BackgroundJobService
from app.services.email import EmailService

NOTIFICATION_EMAIL_KINDS = {
    "replied": "notify_replied",
    "mentioned": "notify_mentioned",
    "liked": "notify_liked",
    "topic_new_post": "notify_topic_new_post",
    "board_new_topic": "notify_board_new_topic",
}

NOTIFICATION_TITLES = {
    "replied": "有人回复了你的主题",
    "mentioned": "有人提到了你",
    "liked": "有人赞同了你的帖子",
    "topic_new_post": "关注主题有新回复",
    "board_new_topic": "关注版块有新主题",
}

DEFAULT_EMAIL_TEMPLATES = {
    "email_notification_subject": "[{site_title}] {notification_title}",
    "email_notification_body": (
        "{username}，你好：\n\n"
        "{notification_title}\n"
        "主题：{topic_title}\n"
        "触发人：{actor_name}\n\n"
        "打开链接：{target_url}\n\n"
        "如果不想收到这类邮件，可在邮件偏好中关闭。"
    ),
    "email_digest_subject": "[{site_title}] {digest_title}",
    "email_digest_body": (
        "{username}，你好：\n\n"
        "这里是你的{digest_title}：\n\n"
        "{digest_items}\n\n"
        "可在邮件偏好中关闭摘要邮件。"
    ),
}


class EmailNotificationService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def get_preferences(self, current_user: User) -> EmailPreferenceResponse:
        preference = await self._get_or_create_preference(current_user)
        return EmailPreferenceResponse.from_model(preference)

    async def update_preferences(
        self,
        current_user: User,
        payload: EmailPreferenceUpdateRequest,
    ) -> EmailPreferenceResponse:
        preference = await self._get_or_create_preference(current_user)
        if payload.email_enabled is not None:
            preference.email_enabled = payload.email_enabled
            if payload.email_enabled:
                preference.delivery_status = "ok"
                preference.disabled_reason = None
            elif preference.delivery_status == "ok":
                preference.delivery_status = "disabled"
                preference.disabled_reason = "user_disabled"
        for field_name in (
            "notify_replied",
            "notify_mentioned",
            "notify_liked",
            "notify_topic_new_post",
            "notify_board_new_topic",
        ):
            value = getattr(payload, field_name)
            if value is not None:
                setattr(preference, field_name, value)
        if payload.digest_frequency is not None:
            preference.digest_frequency = payload.digest_frequency
        await self.session.commit()
        await self.session.refresh(preference)
        return EmailPreferenceResponse.from_model(preference)

    async def enqueue_notification_email(
        self,
        notification: Notification,
        *,
        commit: bool = True,
    ) -> None:
        if notification.type not in NOTIFICATION_EMAIL_KINDS:
            return
        if not await self._can_send_notification_email(notification.user_id, notification.type):
            return
        await BackgroundJobService(self.session).enqueue(
            "send_notification_email",
            queue="mail",
            payload={"notification_id": notification.id},
            idempotency_key=f"email-notification:{notification.id}",
            priority=40,
            max_attempts=5,
            commit=commit,
        )

    async def send_notification_email(self, notification_id: str) -> dict[str, object]:
        notification = await self.session.scalar(
            select(Notification)
            .options(selectinload(Notification.user), selectinload(Notification.actor))
            .where(Notification.id == notification_id)
        )
        if notification is None:
            raise NotFoundError("notification_not_found", "Notification not found")
        if not await self._can_send_notification_email(notification.user_id, notification.type):
            return {"skipped": True, "reason": "preference_disabled"}

        site_title = await self._site_setting("site_title", "平行线")
        notification_title = NOTIFICATION_TITLES.get(notification.type, "你有一条新通知")
        topic_title = self._string_from_data(notification.data, "topic_title") or "未命名主题"
        actor_name = (
            notification.actor.username
            if notification.actor
            else self._string_from_data(
                notification.data,
                "actor_name",
            )
        )
        target_url = self._target_url(notification)
        subject_template = await self._site_setting(
            "email_notification_subject",
            DEFAULT_EMAIL_TEMPLATES["email_notification_subject"],
        )
        body_template = await self._site_setting(
            "email_notification_body",
            DEFAULT_EMAIL_TEMPLATES["email_notification_body"],
        )
        subject = _render_template(
            subject_template,
            {
                "site_title": site_title,
                "notification_title": notification_title,
                "topic_title": topic_title,
                "actor_name": actor_name or "系统",
                "username": notification.user.username,
                "target_url": target_url,
            },
        )
        body = _render_template(
            body_template,
            {
                "site_title": site_title,
                "notification_title": notification_title,
                "topic_title": topic_title,
                "actor_name": actor_name or "系统",
                "username": notification.user.username,
                "target_url": target_url,
            },
        )
        kind = f"notification_{notification.type}"
        await EmailService(self.settings).send_message(
            to_email=notification.user.email,
            subject=subject,
            body=body,
            kind=kind,
            secret=notification.id,
        )
        self._record_delivery_event(
            user_id=notification.user_id,
            email=notification.user.email,
            event_type="sent",
            kind=kind,
            provider_message_id=notification.id,
            reason=None,
            payload={"notification_id": notification.id},
        )
        await self.session.flush()
        return {"sent": True, "kind": kind}

    async def send_digest_emails(self) -> dict[str, object]:
        now = utcnow()
        preferences = list(
            await self.session.scalars(
                select(UserEmailPreference)
                .options(selectinload(UserEmailPreference.user))
                .where(
                    UserEmailPreference.email_enabled.is_(True),
                    UserEmailPreference.delivery_status == "ok",
                    UserEmailPreference.digest_frequency != "off",
                )
            )
        )
        sent_count = 0
        skipped_count = 0
        for preference in preferences:
            user = preference.user
            if user.status != "active" or not self._digest_due(preference):
                skipped_count += 1
                continue
            period_start = self._digest_period_start(preference)
            notifications = list(
                await self.session.scalars(
                    select(Notification)
                    .where(
                        Notification.user_id == user.id,
                        Notification.created_at >= period_start,
                    )
                    .order_by(desc(Notification.created_at))
                    .limit(20)
                )
            )
            if not notifications:
                preference.last_digest_sent_at = now
                skipped_count += 1
                continue
            await self._send_digest(user, preference, notifications)
            preference.last_digest_sent_at = now
            sent_count += 1
        await self.session.flush()
        return {"sent_count": sent_count, "skipped_count": skipped_count}

    async def record_delivery_webhook(
        self,
        payload: EmailDeliveryWebhookRequest,
    ) -> EmailDeliveryEventResponse:
        email = str(payload.email).lower()
        user = await self.session.scalar(select(User).where(func.lower(User.email) == email))
        event = self._record_delivery_event(
            user_id=user.id if user else None,
            email=email,
            event_type=payload.event_type,
            kind=payload.kind,
            provider_message_id=payload.provider_message_id,
            reason=payload.reason,
            payload=payload.payload,
        )
        if user and payload.event_type in {"bounce", "complaint", "dropped"}:
            preference = await self._get_or_create_preference(user)
            preference.email_enabled = False
            if payload.event_type == "bounce":
                preference.delivery_status = "bounced"
            elif payload.event_type == "complaint":
                preference.delivery_status = "complained"
            else:
                preference.delivery_status = "disabled"
            preference.disabled_reason = payload.reason or payload.event_type
        await self.session.commit()
        await self.session.refresh(event)
        return EmailDeliveryEventResponse.from_model(event)

    async def record_inbound_reply(
        self,
        payload: InboundEmailWebhookRequest,
    ) -> InboundEmailResponse:
        email = str(payload.from_email).lower()
        user = await self.session.scalar(select(User).where(func.lower(User.email) == email))
        topic = await self.session.get(Topic, payload.topic_id) if payload.topic_id else None
        status = "accepted"
        reason = None
        if user is None or user.status != "active":
            status = "unknown_sender"
            reason = "No active user matches from_email"
        elif payload.topic_id and topic is None:
            status = "topic_not_found"
            reason = "Topic was not found"
        elif not payload.topic_id:
            status = "recorded"
            reason = "No topic_id supplied"
        inbound = InboundEmail(
            from_email=email,
            user_id=user.id if user else None,
            topic_id=topic.id if topic else None,
            post_id=payload.post_id,
            provider_message_id=payload.provider_message_id,
            raw_md=payload.raw_md.strip(),
            status=status,
            reason=reason,
            payload=payload.payload,
            created_at=utcnow(),
        )
        self.session.add(inbound)
        await self.session.commit()
        await self.session.refresh(inbound)
        return InboundEmailResponse.from_model(inbound)

    async def _send_digest(
        self,
        user: User,
        preference: UserEmailPreference,
        notifications: list[Notification],
    ) -> None:
        site_title = await self._site_setting("site_title", "平行线")
        digest_title = "每周摘要" if preference.digest_frequency == "weekly" else "每日摘要"
        digest_items = "\n".join(
            f"- {NOTIFICATION_TITLES.get(item.type, '新通知')}："
            f"{self._string_from_data(item.data, 'topic_title') or '未命名主题'}"
            for item in notifications
        )
        subject = _render_template(
            await self._site_setting(
                "email_digest_subject",
                DEFAULT_EMAIL_TEMPLATES["email_digest_subject"],
            ),
            {"site_title": site_title, "digest_title": digest_title, "username": user.username},
        )
        body = _render_template(
            await self._site_setting(
                "email_digest_body",
                DEFAULT_EMAIL_TEMPLATES["email_digest_body"],
            ),
            {
                "site_title": site_title,
                "digest_title": digest_title,
                "username": user.username,
                "digest_items": digest_items,
            },
        )
        await EmailService(self.settings).send_message(
            to_email=user.email,
            subject=subject,
            body=body,
            kind="email_digest",
            secret=user.id,
        )
        self._record_delivery_event(
            user_id=user.id,
            email=user.email,
            event_type="sent",
            kind="email_digest",
            provider_message_id=None,
            reason=None,
            payload={"notification_count": len(notifications)},
        )

    async def _get_or_create_preference(self, user: User) -> UserEmailPreference:
        preference = await self.session.scalar(
            select(UserEmailPreference).where(UserEmailPreference.user_id == user.id)
        )
        if preference is not None:
            return preference
        preference = UserEmailPreference(user_id=user.id)
        self.session.add(preference)
        await self.session.flush()
        return preference

    async def _can_send_notification_email(self, user_id: str, kind: str) -> bool:
        field_name = NOTIFICATION_EMAIL_KINDS.get(kind)
        if field_name is None:
            return False
        user = await self.session.get(User, user_id)
        if user is None or user.status != "active":
            return False
        preference = await self._get_or_create_preference(user)
        return (
            preference.email_enabled
            and preference.delivery_status == "ok"
            and bool(getattr(preference, field_name))
        )

    def _digest_due(self, preference: UserEmailPreference) -> bool:
        if preference.last_digest_sent_at is None:
            return True
        elapsed = utcnow() - preference.last_digest_sent_at
        if preference.digest_frequency == "weekly":
            return elapsed >= timedelta(days=7)
        return elapsed >= timedelta(days=1)

    def _digest_period_start(self, preference: UserEmailPreference) -> datetime:
        if preference.last_digest_sent_at:
            return preference.last_digest_sent_at
        days = 7 if preference.digest_frequency == "weekly" else 1
        return utcnow() - timedelta(days=days)

    async def _site_setting(self, key: str, fallback: str) -> str:
        setting = await self.session.scalar(select(SiteSetting).where(SiteSetting.key == key))
        if setting is not None and isinstance(setting.value, str) and setting.value.strip():
            return setting.value
        return fallback

    def _record_delivery_event(
        self,
        *,
        user_id: str | None,
        email: str,
        event_type: str,
        kind: str | None,
        provider_message_id: str | None,
        reason: str | None,
        payload: dict[str, object],
    ) -> EmailDeliveryEvent:
        event = EmailDeliveryEvent(
            user_id=user_id,
            email=email.lower(),
            event_type=event_type,
            kind=kind,
            provider_message_id=provider_message_id,
            reason=reason,
            payload=payload,
            created_at=utcnow(),
        )
        self.session.add(event)
        return event

    def _target_url(self, notification: Notification) -> str:
        topic_slug = self._string_from_data(notification.data, "topic_slug")
        if notification.topic_id and topic_slug:
            return f"/topics/{notification.topic_id}/{topic_slug}"
        board_slug = self._string_from_data(notification.data, "board_slug")
        if board_slug:
            return f"/b/{board_slug}"
        return "/"

    def _string_from_data(self, data: dict[str, object], key: str) -> str | None:
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None


def _render_template(template: str, values: dict[str, object]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered
