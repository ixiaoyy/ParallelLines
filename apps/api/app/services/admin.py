from __future__ import annotations

import asyncio
import copy
import re
from dataclasses import dataclass

from sqlalchemy import desc, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.growth import clamp_display_level
from app.core.permissions import is_admin
from app.db.base import utcnow
from app.models.admin import SiteSetting
from app.models.background_job import BackgroundJob
from app.models.badge import UserBadge
from app.models.forum import Board, Post, Topic
from app.models.moderation import AuditLog, Flag, SpamAction
from app.models.user import User
from app.schemas.admin import (
    AdminBackgroundJobLogResponse,
    AdminBackgroundJobResponse,
    AdminEmailLogResponse,
    AdminServiceStatusResponse,
    AdminStatsResponse,
    AdminSystemOverviewResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    PublicSiteSettingsResponse,
    SiteSettingResponse,
    SiteSettingUpdateRequest,
)
from app.schemas.badges import BadgeResponse, UserBadgeResponse
from app.schemas.moderation import AuditLogResponse
from app.services.background_jobs import BackgroundJobService
from app.services.badges import BadgeTrustService
from app.services.email import EMAIL_OUTBOX
from app.services.growth import GrowthService


@dataclass(frozen=True)
class DefaultSiteSetting:
    key: str
    value: object
    data_type: str
    category: str
    description: str
    public: bool = False


HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
I18N_KEY_PATTERN = re.compile(r"^[a-z0-9_.-]{1,80}$")
BRAND_COLOR_SETTING_KEYS = {"brand_primary_color", "brand_accent_color"}
URL_SETTING_KEYS = {"brand_logo_url", "brand_favicon_url"}


DEFAULT_SITE_SETTINGS: dict[str, DefaultSiteSetting] = {
    "site_title": DefaultSiteSetting(
        key="site_title",
        value="平行线",
        data_type="string",
        category="brand",
        description="站点名称，显示在前端顶栏和基础品牌区域。",
        public=True,
    ),
    "site_tagline": DefaultSiteSetting(
        key="site_tagline",
        value="让答案可追溯",
        data_type="string",
        category="brand",
        description="站点副标题，显示在前端品牌标识下方。",
        public=True,
    ),
    "brand_primary_color": DefaultSiteSetting(
        key="brand_primary_color",
        value="#409EFF",
        data_type="string",
        category="brand",
        description="主品牌色，供前端主题预览和后续主题能力使用。",
        public=True,
    ),
    "brand_accent_color": DefaultSiteSetting(
        key="brand_accent_color",
        value="#10B981",
        data_type="string",
        category="brand",
        description="品牌辅助色，供前端主题预览、焦点和点缀元素使用。",
        public=True,
    ),
    "brand_logo_url": DefaultSiteSetting(
        key="brand_logo_url",
        value="/logo-lines.png",
        data_type="string",
        category="brand",
        description="站点 Logo URL，可使用站内相对路径或 http(s) 地址。",
        public=True,
    ),
    "brand_favicon_url": DefaultSiteSetting(
        key="brand_favicon_url",
        value="/favicon.svg",
        data_type="string",
        category="brand",
        description="浏览器标签页图标 URL，可使用站内相对路径或 http(s) 地址。",
        public=True,
    ),
    "site_text_overrides": DefaultSiteSetting(
        key="site_text_overrides",
        value={},
        data_type="json",
        category="text",
        description="前端 i18n 文案覆盖，格式为 key 到中文文案的 JSON 对象。",
        public=True,
    ),
    "registration_enabled": DefaultSiteSetting(
        key="registration_enabled",
        value=True,
        data_type="boolean",
        category="access",
        description="是否允许新用户注册。",
        public=True,
    ),
    "upload_max_bytes": DefaultSiteSetting(
        key="upload_max_bytes",
        value=5 * 1024 * 1024,
        data_type="integer",
        category="uploads",
        description="单个帖子附件最大字节数。",
    ),
    "upload_max_avatar_bytes": DefaultSiteSetting(
        key="upload_max_avatar_bytes",
        value=2 * 1024 * 1024,
        data_type="integer",
        category="uploads",
        description="单个头像文件最大字节数。",
    ),
    "email_notification_subject": DefaultSiteSetting(
        key="email_notification_subject",
        value="[{site_title}] {notification_title}",
        data_type="string",
        category="email",
        description="通知邮件主题模板，支持 site_title、notification_title 等占位符。",
    ),
    "email_notification_body": DefaultSiteSetting(
        key="email_notification_body",
        value=(
            "{username}，你好：\n\n"
            "{notification_title}\n"
            "主题：{topic_title}\n"
            "触发人：{actor_name}\n\n"
            "打开链接：{target_url}\n\n"
            "如果不想收到这类邮件，可在邮件偏好中关闭。"
        ),
        data_type="string",
        category="email",
        description="通知邮件正文模板。",
    ),
    "email_digest_subject": DefaultSiteSetting(
        key="email_digest_subject",
        value="[{site_title}] {digest_title}",
        data_type="string",
        category="email",
        description="摘要邮件主题模板。",
    ),
    "email_digest_body": DefaultSiteSetting(
        key="email_digest_body",
        value=(
            "{username}，你好：\n\n"
            "这里是你的{digest_title}：\n\n"
            "{digest_items}\n\n"
            "可在邮件偏好中关闭摘要邮件。"
        ),
        data_type="string",
        category="email",
        description="摘要邮件正文模板。",
    ),
}


class SiteSettingService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def list_site_settings(self, current_user: User) -> list[SiteSettingResponse]:
        self._require_admin(current_user)
        await self._ensure_default_settings()
        settings = list(
            await self.session.scalars(
                select(SiteSetting)
                .options(selectinload(SiteSetting.updated_by))
                .order_by(SiteSetting.category, SiteSetting.key)
            )
        )
        return [SiteSettingResponse.from_model(setting) for setting in settings]

    async def public_site_settings(self) -> PublicSiteSettingsResponse:
        await self._ensure_default_settings()
        settings = list(
            await self.session.scalars(
                select(SiteSetting).where(SiteSetting.public.is_(True)).order_by(SiteSetting.key)
            )
        )
        updated_at = max((setting.updated_at for setting in settings), default=None)
        return PublicSiteSettingsResponse(
            settings={setting.key: setting.value for setting in settings},
            updated_at=updated_at,
        )

    async def update_site_setting(
        self,
        key: str,
        payload: SiteSettingUpdateRequest,
        current_user: User,
    ) -> SiteSettingResponse:
        self._require_admin(current_user)
        setting = await self._get_or_create_default_setting(key)
        old_value = copy.deepcopy(setting.value)
        setting.value = self._coerce_value(setting, payload.value)
        setting.updated_by_id = current_user.id
        self._add_audit_log(
            actor_id=current_user.id,
            action="site_setting_updated",
            target_type="site_setting",
            target_id=setting.id,
            data={"key": setting.key, "old_value": old_value, "new_value": setting.value},
        )
        await self.session.commit()
        setting = await self.session.scalar(
            select(SiteSetting)
            .options(selectinload(SiteSetting.updated_by))
            .where(SiteSetting.id == setting.id)
        )
        if setting is None:
            raise NotFoundError("site_setting_not_found", "Site setting not found")
        return SiteSettingResponse.from_model(setting)

    async def registration_enabled(self) -> bool:
        value = await self._setting_value("registration_enabled")
        return value is True

    async def upload_limit_bytes(self, *, kind: str, fallback: int) -> int:
        key = "upload_max_avatar_bytes" if kind == "avatar" else "upload_max_bytes"
        value = await self._setting_value(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return fallback
        return value

    async def _setting_value(self, key: str) -> object:
        default = DEFAULT_SITE_SETTINGS.get(key)
        setting = await self.session.scalar(select(SiteSetting).where(SiteSetting.key == key))
        if setting:
            return setting.value
        if default is None:
            return None
        await self._ensure_default_settings()
        return copy.deepcopy(default.value)

    async def _ensure_default_settings(self) -> None:
        existing_keys = set(await self.session.scalars(select(SiteSetting.key)))
        missing = [
            setting for key, setting in DEFAULT_SITE_SETTINGS.items() if key not in existing_keys
        ]
        if not missing:
            return
        for setting in missing:
            value = self._default_value(setting)
            if setting.key == "upload_max_bytes":
                value = self.settings.upload_max_bytes
            elif setting.key == "upload_max_avatar_bytes":
                value = self.settings.upload_max_avatar_bytes
            self.session.add(
                SiteSetting(
                    key=setting.key,
                    value=value,
                    data_type=setting.data_type,
                    category=setting.category,
                    description=setting.description,
                    public=setting.public,
                )
            )
        await self.session.commit()

    async def _get_or_create_default_setting(self, key: str) -> SiteSetting:
        await self._ensure_default_settings()
        setting = await self.session.scalar(select(SiteSetting).where(SiteSetting.key == key))
        if setting is None:
            raise NotFoundError("site_setting_not_found", "Site setting not found")
        return setting

    def _coerce_value(self, setting: SiteSetting, value: object) -> object:
        if setting.data_type == "boolean":
            if not isinstance(value, bool):
                raise ValidationError("invalid_site_setting_value", "Expected a boolean value")
            return value
        if setting.data_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError("invalid_site_setting_value", "Expected an integer value")
            if value <= 0:
                raise ValidationError(
                    "invalid_site_setting_value",
                    "Expected a positive integer value",
                )
            return value
        if setting.data_type == "string":
            return self._coerce_string_setting(setting, value)
        if setting.data_type == "json":
            return self._coerce_json_setting(setting, value)
        return value

    def _coerce_string_setting(self, setting: SiteSetting, value: object) -> str:
        if not isinstance(value, str):
            raise ValidationError("invalid_site_setting_value", "Expected a string value")
        trimmed = value.strip()
        if not trimmed:
            raise ValidationError("invalid_site_setting_value", "Value cannot be empty")
        max_length = 4000 if setting.key.endswith("_body") else 512
        if len(trimmed) > max_length:
            raise ValidationError("invalid_site_setting_value", "Value is too long")
        if setting.key in BRAND_COLOR_SETTING_KEYS and HEX_COLOR_PATTERN.fullmatch(trimmed) is None:
            raise ValidationError(
                "invalid_site_setting_value",
                "Expected a hex color such as #409EFF",
            )
        if setting.key in URL_SETTING_KEYS and not self._is_safe_asset_url(trimmed):
            raise ValidationError(
                "invalid_site_setting_value",
                "Expected a relative or http(s) asset URL",
            )
        return trimmed

    def _coerce_json_setting(self, setting: SiteSetting, value: object) -> object:
        if setting.key == "site_text_overrides":
            if not isinstance(value, dict):
                raise ValidationError(
                    "invalid_site_setting_value",
                    "Expected an object of i18n keys",
                )
            if len(value) > 100:
                raise ValidationError("invalid_site_setting_value", "Too many text overrides")
            normalized: dict[str, str] = {}
            for raw_key, raw_text in value.items():
                if not isinstance(raw_key, str) or I18N_KEY_PATTERN.fullmatch(raw_key) is None:
                    raise ValidationError("invalid_site_setting_value", "Invalid i18n key")
                if not isinstance(raw_text, str):
                    raise ValidationError("invalid_site_setting_value", "Expected text values")
                text = raw_text.strip()
                if not text:
                    continue
                if len(text) > 500:
                    raise ValidationError("invalid_site_setting_value", "Text override is too long")
                normalized[raw_key] = text
            return normalized
        if not isinstance(value, dict | list):
            raise ValidationError("invalid_site_setting_value", "Expected a JSON object or array")
        return value

    def _is_safe_asset_url(self, value: str) -> bool:
        if any(char.isspace() for char in value):
            return False
        return value.startswith("/") or value.startswith("https://") or value.startswith("http://")

    def _default_value(self, setting: DefaultSiteSetting) -> object:
        return copy.deepcopy(setting.value)

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _add_audit_log(
        self,
        *,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                board_id=None,
                data=data,
                created_at=utcnow(),
            )
        )


class AdminService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def list_users(
        self,
        current_user: User,
        *,
        query: str | None = None,
        role: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AdminUserResponse]:
        self._require_admin(current_user)
        statement = select(User).order_by(desc(User.created_at)).limit(limit)
        if query:
            token = f"%{query.strip().lower()}%"
            statement = statement.where(
                or_(func.lower(User.username).like(token), func.lower(User.email).like(token))
            )
        if role:
            statement = statement.where(User.role == role)
        if status:
            statement = statement.where(User.status == status)
        users = list(await self.session.scalars(statement))
        return await self._users_to_responses(users)

    async def get_user(self, user_id: str, current_user: User) -> AdminUserResponse:
        self._require_admin(current_user)
        user = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("user_not_found", "User not found")
        return (await self._users_to_responses([user]))[0]

    async def update_user(
        self,
        user_id: str,
        payload: AdminUserUpdateRequest,
        current_user: User,
    ) -> AdminUserResponse:
        self._require_admin(current_user)
        user = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("user_not_found", "User not found")
        if current_user.id == user.id:
            if payload.status and payload.status != "active":
                raise ValidationError("cannot_moderate_self", "Cannot change your own status")
            if payload.role and payload.role != "admin":
                raise ValidationError(
                    "cannot_remove_own_admin",
                    "Cannot remove your own admin role",
                )

        before = {
            "role": user.role,
            "status": user.status,
            "level": user.level,
            "trust_level": user.trust_level,
            "points_balance": user.points_balance,
            "experience_total": user.experience_total,
        }
        if payload.role is not None:
            user.role = payload.role
        if payload.status is not None:
            user.status = payload.status
        if payload.level is not None:
            user.level = clamp_display_level(payload.level)
        await GrowthService(self.session).adjust_user(
            user,
            points_delta=payload.points_delta or 0,
            experience_delta=payload.experience_delta or 0,
            actor_id=current_user.id,
            note=payload.adjustment_reason,
        )
        await BadgeTrustService(self.session).recompute_trust(
            user,
            source_type="admin_user_update",
            source_id=user.id,
            actor_id=current_user.id,
            note=payload.adjustment_reason or "管理员更新用户状态或成长值",
        )
        after = {
            "role": user.role,
            "status": user.status,
            "level": user.level,
            "trust_level": user.trust_level,
            "points_balance": user.points_balance,
            "experience_total": user.experience_total,
        }
        self._add_audit_log(
            actor_id=current_user.id,
            action="user_admin_updated",
            target_type="user",
            target_id=user.id,
            data={"before": before, "after": after},
        )
        await self.session.commit()
        await self.session.refresh(user)
        return await self.get_user(user.id, current_user)

    async def list_badges(self, current_user: User) -> list[BadgeResponse]:
        self._require_admin(current_user)
        return await BadgeTrustService(self.session).list_badges()

    async def grant_user_badge(
        self,
        user_id: str,
        *,
        badge_slug: str,
        note: str | None,
        current_user: User,
    ) -> AdminUserResponse:
        self._require_admin(current_user)
        target_user = await self.session.get(User, user_id)
        if not target_user:
            raise NotFoundError("user_not_found", "User not found")
        user_badge = await BadgeTrustService(self.session).grant_badge(
            user_id=target_user.id,
            badge_slug=badge_slug,
            source_type="admin_manual",
            source_id=None,
            actor_id=current_user.id,
            note=note,
            idempotency_key=f"badge:admin:{target_user.id}:{badge_slug}:{utcnow().timestamp()}",
        )
        self._add_audit_log(
            actor_id=current_user.id,
            action="user_badge_granted",
            target_type="user",
            target_id=target_user.id,
            data={
                "badge_slug": badge_slug,
                "user_badge_id": user_badge.id if user_badge else None,
                "note": note or "",
            },
        )
        await self.session.commit()
        return await self.get_user(target_user.id, current_user)

    async def revoke_user_badge(
        self,
        user_id: str,
        *,
        badge_slug: str,
        reason: str | None,
        current_user: User,
    ) -> AdminUserResponse:
        self._require_admin(current_user)
        if await self.session.get(User, user_id) is None:
            raise NotFoundError("user_not_found", "User not found")
        user_badge = await BadgeTrustService(self.session).revoke_badge(
            user_id=user_id,
            badge_slug=badge_slug,
            actor_id=current_user.id,
            reason=reason,
        )
        self._add_audit_log(
            actor_id=current_user.id,
            action="user_badge_revoked",
            target_type="user",
            target_id=user_id,
            data={
                "badge_slug": badge_slug,
                "user_badge_id": user_badge.id,
                "reason": reason or "",
            },
        )
        await self.session.commit()
        return await self.get_user(user_id, current_user)

    async def system_overview(self, current_user: User) -> AdminSystemOverviewResponse:
        self._require_admin(current_user)
        services = [
            await self._database_status(),
            await self._redis_status(),
            AdminServiceStatusResponse(
                name="mail",
                status="ok" if self.settings.email_delivery_mode == "memory" else "unknown",
                detail=f"delivery={self.settings.email_delivery_mode}",
            ),
            AdminServiceStatusResponse(
                name="workers",
                status="ok",
                detail=(
                    "unified background worker; poll="
                    f"{self.settings.background_job_poll_seconds}s, "
                    f"batch={self.settings.background_job_batch_size}"
                ),
            ),
        ]
        queue_summary = await self._queue_summary()
        dead_jobs = list(
            await self.session.scalars(
                select(BackgroundJob)
                .where(BackgroundJob.status == "dead")
                .order_by(desc(BackgroundJob.updated_at))
                .limit(8)
            )
        )
        recent_errors = [
            {
                "id": job.id,
                "task_name": job.task_name,
                "error": job.last_error or "",
                "occurred_at": job.updated_at,
            }
            for job in dead_jobs
        ]
        return AdminSystemOverviewResponse(
            version="0.1.0",
            environment=self.settings.environment,
            services=services,
            stats=await self._stats(),
            queue={
                **queue_summary,
                "worker": "app.workers.background_jobs",
                "poll_seconds": self.settings.background_job_poll_seconds,
                "batch_size": self.settings.background_job_batch_size,
                "retry_delay_seconds": self.settings.background_job_retry_delay_seconds,
                "hot_rank_interval_seconds": self.settings.background_hot_rank_interval_seconds,
                "upload_cleanup_interval_seconds": (
                    self.settings.background_upload_cleanup_interval_seconds
                ),
                "session_cleanup_interval_seconds": (
                    self.settings.background_session_cleanup_interval_seconds
                ),
                "digest_interval_seconds": self.settings.background_digest_interval_seconds,
                "frontier_news_interval_seconds": (
                    self.settings.background_frontier_news_interval_seconds
                ),
            },
            recent_audit_logs=await self.list_audit_logs(current_user, limit=8),
            recent_email_logs=self.email_logs(limit=8),
            recent_errors=recent_errors,
        )

    async def list_background_jobs(
        self,
        current_user: User,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AdminBackgroundJobResponse]:
        self._require_admin(current_user)
        jobs = await BackgroundJobService(self.session).list_jobs(status=status, limit=limit)
        return [AdminBackgroundJobResponse.from_model(job) for job in jobs]

    async def list_background_job_logs(
        self,
        job_id: str,
        current_user: User,
    ) -> list[AdminBackgroundJobLogResponse]:
        self._require_admin(current_user)
        if await self.session.get(BackgroundJob, job_id) is None:
            raise NotFoundError("background_job_not_found", "Background job not found")
        logs = await BackgroundJobService(self.session).list_logs(job_id)
        return [AdminBackgroundJobLogResponse.from_model(log) for log in logs]

    async def list_audit_logs(
        self,
        current_user: User,
        *,
        limit: int = 50,
    ) -> list[AuditLogResponse]:
        self._require_admin(current_user)
        logs = list(
            await self.session.scalars(
                select(AuditLog)
                .options(selectinload(AuditLog.actor))
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
            )
        )
        return [AuditLogResponse.from_model(log) for log in logs]

    def email_logs(
        self,
        *,
        limit: int = 50,
        current_user: User | None = None,
    ) -> list[AdminEmailLogResponse]:
        if current_user is not None:
            self._require_admin(current_user)
        return [
            AdminEmailLogResponse(
                to_email=mask_email(email.to_email),
                subject=email.subject,
                kind=email.kind,
                sent_at=email.sent_at,
            )
            for email in reversed(EMAIL_OUTBOX[-limit:])
        ]

    async def _users_to_responses(self, users: list[User]) -> list[AdminUserResponse]:
        if not users:
            return []
        user_ids = [user.id for user in users]
        topic_counts = await self._count_by_user(Topic.user_id, Topic, user_ids)
        post_counts = await self._count_by_user(Post.user_id, Post, user_ids)
        badges_by_user = await self._badges_by_user(user_ids)
        return [
            AdminUserResponse.from_model(
                user,
                topic_count=topic_counts.get(user.id, 0),
                post_count=post_counts.get(user.id, 0),
                badges=badges_by_user.get(user.id, []),
            )
            for user in users
        ]

    async def _badges_by_user(self, user_ids: list[str]) -> dict[str, list[UserBadgeResponse]]:
        user_badges = list(
            await self.session.scalars(
                select(UserBadge)
                .options(selectinload(UserBadge.badge))
                .where(UserBadge.user_id.in_(user_ids), UserBadge.revoked_at.is_(None))
                .order_by(UserBadge.created_at.desc())
            )
        )
        grouped: dict[str, list[UserBadgeResponse]] = {user_id: [] for user_id in user_ids}
        for user_badge in user_badges:
            grouped.setdefault(user_badge.user_id, []).append(
                UserBadgeResponse.from_model(user_badge)
            )
        return grouped

    async def _count_by_user(self, column, model, user_ids: list[str]) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(column, func.count()).where(column.in_(user_ids)).group_by(column)
            )
        ).all()
        return {str(user_id): int(count) for user_id, count in rows}

    async def _database_status(self) -> AdminServiceStatusResponse:
        try:
            await self.session.scalar(select(literal(1)))
            return AdminServiceStatusResponse(name="database", status="ok", detail="select(1) ok")
        except Exception as exc:
            return AdminServiceStatusResponse(
                name="database",
                status="degraded",
                detail=type(exc).__name__,
            )

    async def _redis_status(self) -> AdminServiceStatusResponse:
        try:
            from redis import asyncio as redis

            client = redis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            try:
                await asyncio.wait_for(client.ping(), timeout=0.3)
                return AdminServiceStatusResponse(name="cache", status="ok", detail="redis ping ok")
            finally:
                await client.aclose()
        except Exception as exc:
            return AdminServiceStatusResponse(
                name="cache",
                status="degraded",
                detail=type(exc).__name__,
            )

    async def _stats(self) -> AdminStatsResponse:
        return AdminStatsResponse(
            users=await self._count(User),
            boards=await self._count(Board),
            topics=await self._count(Topic),
            posts=await self._count(Post),
            pending_flags=await self._count(Flag, Flag.status == "pending"),
            audit_logs=await self._count(AuditLog),
            spam_actions=await self._count(SpamAction),
        )

    async def _queue_summary(self) -> dict[str, object]:
        rows = (
            await self.session.execute(
                select(BackgroundJob.status, func.count(BackgroundJob.id)).group_by(
                    BackgroundJob.status
                )
            )
        ).all()
        counts = {str(status): int(count) for status, count in rows}
        return {
            "counts": counts,
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "dead": counts.get("dead", 0),
        }

    async def _count(self, model, *where_clauses) -> int:
        statement = select(func.count(model.id))
        for clause in where_clauses:
            statement = statement.where(clause)
        return int(await self.session.scalar(statement) or 0)

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _add_audit_log(
        self,
        *,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                board_id=None,
                data=data,
                created_at=utcnow(),
            )
        )


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local) <= 2:
        masked_local = f"{local[:1]}***"
    else:
        masked_local = f"{local[:2]}***{local[-1:]}"
    return f"{masked_local}@{domain}"
