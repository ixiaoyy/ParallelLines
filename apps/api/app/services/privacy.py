from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.core.security import hash_password
from app.db.base import utcnow
from app.models.background_job import BackgroundJob
from app.models.chat import ChatChannelMember, ChatPresence
from app.models.draft import Draft
from app.models.email import EmailDeliveryEvent, InboundEmail, UserEmailPreference
from app.models.forum import Board, BoardInvitation, BoardMember
from app.models.integration import ApiKey, WebhookEndpoint
from app.models.interaction import Notification
from app.models.moderation import AuditLog, RateLimitEvent, SpamAction
from app.models.search import SearchDocument, SearchLog
from app.models.social import PrivateMessageParticipant, UserRelationship
from app.models.upload import Upload
from app.models.user import (
    EmailVerificationCode,
    User,
    UserRecoveryCode,
    UserSecurityToken,
    UserSession,
)
from app.schemas.privacy import PrivacyActionResponse, RetentionPolicyResponse

ANON_USERNAME_PREFIX = "anonymous"
DELETED_EMAIL_DOMAIN = "deleted.invalid"
DELETED_UPLOAD_FILENAME = "deleted-upload"


@dataclass(frozen=True)
class PrivacyCleanupCounts:
    revoked_sessions: int = 0
    deleted_security_tokens: int = 0
    deleted_recovery_codes: int = 0
    deleted_email_codes: int = 0
    deleted_drafts: int = 0
    deleted_notifications: int = 0
    removed_relationships: int = 0
    removed_board_memberships: int = 0
    removed_board_invitations: int = 0
    removed_private_message_participations: int = 0
    disabled_api_keys: int = 0
    disabled_webhooks: int = 0
    deleted_uploads: int = 0
    retained_uploads: int = 0
    anonymized_logs: int = 0


class PrivacyService:
    """Privacy workflows for exports, anonymization, and account deletion."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def retention_policy(self) -> RetentionPolicyResponse:
        return RetentionPolicyResponse(
            user_export_available=True,
            account_deletion_mode="anonymize_and_revoke",
            retained_content=(
                "Topics, posts, and attached uploads remain readable under a non-identifying "
                "anonymous author placeholder."
            ),
            removed_private_data=(
                "Login credentials, sessions, security tokens, recovery codes, drafts, personal "
                "notifications, relationships, private-message participation rows, avatar and "
                "temporary uploads are removed or disabled."
            ),
            export_redaction=(
                "Exports redact password, token, secret, code, and sensitive hash fields."
            ),
            upload_retention=(
                "Avatar and temporary uploads are deleted; post attachments are retained to keep "
                "topics readable, with owner filename metadata anonymized."
            ),
        )

    async def anonymize_user(
        self,
        user_id: str,
        *,
        actor: User,
        reason: str | None = None,
        action: str = "user_anonymized",
    ) -> PrivacyActionResponse:
        self._require_admin(actor)
        if actor.id == user_id:
            raise ValidationError("cannot_anonymize_self", "Cannot anonymize your own account")
        user = await self._require_user(user_id)
        return await self._anonymize(user, actor=actor, reason=reason, action=action)

    async def delete_user(
        self,
        user_id: str,
        *,
        actor: User,
        reason: str | None = None,
    ) -> PrivacyActionResponse:
        self._require_admin(actor)
        if actor.id == user_id:
            raise ValidationError("cannot_delete_self", "Cannot delete your own account")
        user = await self._require_user(user_id)
        return await self._anonymize(
            user,
            actor=actor,
            reason=reason,
            action="user_account_deleted_by_admin",
        )

    async def delete_current_user(
        self,
        current_user: User,
        *,
        reason: str | None = None,
    ) -> PrivacyActionResponse:
        return await self._anonymize(
            current_user,
            actor=current_user,
            reason=reason,
            action="user_account_deleted_self_service",
        )

    async def _anonymize(
        self,
        user: User,
        *,
        actor: User,
        reason: str | None,
        action: str,
    ) -> PrivacyActionResponse:
        old_username = user.username
        old_email = user.email
        anonymous_username = anonymous_username_for(user.id)
        anonymous_email = anonymous_email_for(user.id)
        now = utcnow()

        if user.status == "deleted" and user.username == anonymous_username:
            return PrivacyActionResponse(
                user_id=user.id,
                username=user.username,
                email=user.email,
                status=user.status,
                anonymized=True,
                reason=reason,
                **PrivacyCleanupCounts().__dict__,
            )

        before_status = user.status
        user.username = anonymous_username
        user.email = anonymous_email
        user.hashed_password = hash_password(secrets.token_urlsafe(48))
        user.avatar_url = None
        user.display_name = None
        user.bio = None
        user.website_url = None
        user.location = None
        user.role = "user"
        user.level = 0
        user.trust_level = 0
        user.trust_level_changed_at = now
        user.points_balance = 0
        user.experience_total = 0
        user.status = "deleted"
        user.last_seen_at = None
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.profile_visibility = "private"
        user.show_activity = False
        user.interface_theme = "system"
        user.locale = "zh-CN"

        counts = await self._cleanup_related_private_data(
            user,
            old_email=old_email,
            anonymous_email=anonymous_email,
            actor_id=actor.id,
        )
        await self._anonymize_search_documents(user.id, anonymous_username)
        self._add_audit_log(
            actor_id=actor.id,
            action=action,
            target_type="user",
            target_id=user.id,
            data={
                "from_status": before_status,
                "to_status": "deleted",
                "reason": reason or "",
                "old_username_redacted": bool(old_username),
                "old_email_redacted": bool(old_email),
            },
        )
        await self.session.commit()
        return PrivacyActionResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            status=user.status,
            anonymized=True,
            reason=reason,
            **counts.__dict__,
        )

    async def _cleanup_related_private_data(
        self,
        user: User,
        *,
        old_email: str,
        anonymous_email: str,
        actor_id: str,
    ) -> PrivacyCleanupCounts:
        now = utcnow()
        revoked_sessions = await self._revoke_sessions(user.id, now)
        deleted_security_tokens = await self._delete_rows(
            UserSecurityToken, UserSecurityToken.user_id == user.id
        )
        deleted_recovery_codes = await self._delete_rows(
            UserRecoveryCode, UserRecoveryCode.user_id == user.id
        )
        deleted_email_codes = await self._delete_rows(
            EmailVerificationCode, EmailVerificationCode.user_id == user.id
        )
        deleted_drafts = await self._delete_rows(Draft, Draft.user_id == user.id)
        deleted_notifications = await self._delete_rows(
            Notification, Notification.user_id == user.id
        )
        await self.session.execute(
            update(Notification)
            .where(Notification.actor_id == user.id)
            .values(actor_id=None)
            .execution_options(synchronize_session=False)
        )
        removed_relationships = await self._delete_rows(
            UserRelationship,
            or_(
                UserRelationship.actor_user_id == user.id,
                UserRelationship.target_user_id == user.id,
            ),
        )
        removed_board_memberships = await self._delete_rows(
            BoardMember, BoardMember.user_id == user.id
        )
        await self.session.execute(
            update(Board)
            .where(Board.owner_id == user.id)
            .values(owner_id=None)
            .execution_options(synchronize_session=False)
        )
        removed_board_invitations = await self._delete_rows(
            BoardInvitation,
            or_(
                BoardInvitation.inviter_id == user.id,
                BoardInvitation.invitee_id == user.id,
                BoardInvitation.revoked_by_id == user.id,
            ),
        )
        removed_pm_participants = await self._delete_rows(
            PrivateMessageParticipant,
            PrivateMessageParticipant.user_id == user.id,
        )
        await self._delete_rows(ChatChannelMember, ChatChannelMember.user_id == user.id)
        await self._delete_rows(ChatPresence, ChatPresence.user_id == user.id)
        disabled_api_keys = await self._disable_api_keys(user.id, actor_id, now)
        disabled_webhooks = await self._disable_webhooks(user.id, actor_id, now)
        deleted_uploads, retained_uploads = await self._process_uploads(user.id, now)
        anonymized_logs = await self._anonymize_email_and_activity_logs(
            user.id,
            old_email=old_email,
            anonymous_email=anonymous_email,
        )
        await self._disable_email_preferences(user.id)
        await self._clear_search_logs(user.id)
        await self._redact_background_email_payloads(old_email, anonymous_email)
        return PrivacyCleanupCounts(
            revoked_sessions=revoked_sessions,
            deleted_security_tokens=deleted_security_tokens,
            deleted_recovery_codes=deleted_recovery_codes,
            deleted_email_codes=deleted_email_codes,
            deleted_drafts=deleted_drafts,
            deleted_notifications=deleted_notifications,
            removed_relationships=removed_relationships,
            removed_board_memberships=removed_board_memberships,
            removed_board_invitations=removed_board_invitations,
            removed_private_message_participations=removed_pm_participants,
            disabled_api_keys=disabled_api_keys,
            disabled_webhooks=disabled_webhooks,
            deleted_uploads=deleted_uploads,
            retained_uploads=retained_uploads,
            anonymized_logs=anonymized_logs,
        )

    async def _revoke_sessions(self, user_id: str, now) -> int:
        sessions = list(
            await self.session.scalars(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                )
            )
        )
        for session in sessions:
            session.revoked_at = now
        return len(sessions)

    async def _disable_api_keys(self, user_id: str, actor_id: str, now) -> int:
        keys = list(
            await self.session.scalars(
                select(ApiKey).where(
                    ApiKey.disabled_at.is_(None),
                    or_(ApiKey.owner_user_id == user_id, ApiKey.created_by_id == user_id),
                )
            )
        )
        for key in keys:
            key.disabled_at = now
            key.disabled_by_id = actor_id
            key.note = self._append_privacy_note(key.note)
        return len(keys)

    async def _disable_webhooks(self, user_id: str, actor_id: str, now) -> int:
        webhooks = list(
            await self.session.scalars(
                select(WebhookEndpoint).where(
                    WebhookEndpoint.active.is_(True),
                    WebhookEndpoint.created_by_id == user_id,
                )
            )
        )
        for webhook in webhooks:
            webhook.active = False
            webhook.disabled_at = now
            webhook.disabled_by_id = actor_id
            webhook.note = self._append_privacy_note(webhook.note)
        return len(webhooks)

    async def _process_uploads(self, user_id: str, now) -> tuple[int, int]:
        uploads = list(await self.session.scalars(select(Upload).where(Upload.user_id == user_id)))
        deleted_count = 0
        retained_count = 0
        for upload in uploads:
            upload.original_filename = f"{DELETED_UPLOAD_FILENAME}-{upload.id[:8]}"
            if upload.status in {"avatar", "temporary"} or upload.kind == "avatar":
                if upload.status != "deleted":
                    deleted_count += 1
                upload.status = "deleted"
                upload.deleted_at = upload.deleted_at or now
                self._delete_local_upload_file(upload)
            else:
                retained_count += 1
        return deleted_count, retained_count

    async def _anonymize_email_and_activity_logs(
        self,
        user_id: str,
        *,
        old_email: str,
        anonymous_email: str,
    ) -> int:
        count = 0
        email_events = list(
            await self.session.scalars(
                select(EmailDeliveryEvent).where(
                    or_(
                        EmailDeliveryEvent.user_id == user_id, EmailDeliveryEvent.email == old_email
                    )
                )
            )
        )
        for event in email_events:
            event.email = anonymous_email
            event.payload = redact_email_from_mapping(event.payload, old_email, anonymous_email)
            count += 1
        inbound_rows = list(
            await self.session.scalars(
                select(InboundEmail).where(
                    or_(InboundEmail.user_id == user_id, InboundEmail.from_email == old_email)
                )
            )
        )
        for inbound in inbound_rows:
            inbound.from_email = anonymous_email
            inbound.payload = redact_email_from_mapping(inbound.payload, old_email, anonymous_email)
            count += 1
        spam_actions = list(
            await self.session.scalars(
                select(SpamAction).where(
                    or_(SpamAction.user_id == user_id, SpamAction.email == old_email)
                )
            )
        )
        for action in spam_actions:
            action.email = anonymous_email
            action.data = redact_email_from_mapping(action.data, old_email, anonymous_email)
            count += 1
        rate_events = list(
            await self.session.scalars(
                select(RateLimitEvent).where(RateLimitEvent.user_id == user_id)
            )
        )
        for event in rate_events:
            if event.identity_type in {"email", "account", "user"}:
                event.identity_key = anonymous_email
            count += 1
        return count

    async def _disable_email_preferences(self, user_id: str) -> None:
        preference = await self.session.scalar(
            select(UserEmailPreference).where(UserEmailPreference.user_id == user_id)
        )
        if preference is None:
            return
        preference.email_enabled = False
        preference.notify_replied = False
        preference.notify_mentioned = False
        preference.notify_liked = False
        preference.notify_topic_new_post = False
        preference.notify_board_new_topic = False
        preference.digest_frequency = "off"
        preference.delivery_status = "disabled"
        preference.disabled_reason = "account_deleted"
        preference.quiet_hours_start = 0
        preference.quiet_hours_end = 0

    async def _clear_search_logs(self, user_id: str) -> None:
        logs = list(
            await self.session.scalars(select(SearchLog).where(SearchLog.user_id == user_id))
        )
        for log in logs:
            log.user_id = None
            log.query = "[redacted]"
            log.normalized_query = "[redacted]"
            log.filters = {}

    async def _redact_background_email_payloads(self, old_email: str, anonymous_email: str) -> None:
        jobs = list(await self.session.scalars(select(BackgroundJob)))
        for job in jobs:
            job.payload = redact_email_from_mapping(job.payload or {}, old_email, anonymous_email)
            if job.result:
                job.result = redact_email_from_mapping(job.result, old_email, anonymous_email)
            if job.idempotency_key and old_email in job.idempotency_key:
                job.idempotency_key = job.idempotency_key.replace(old_email, anonymous_email)

    async def _anonymize_search_documents(self, user_id: str, anonymous_username: str) -> None:
        await self.session.execute(
            update(SearchDocument)
            .where(SearchDocument.author_id == user_id)
            .values(author_username=anonymous_username)
            .execution_options(synchronize_session=False)
        )

    async def _delete_rows(self, model, *conditions) -> int:
        result = await self.session.execute(
            delete(model).where(*conditions).execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)

    def _delete_local_upload_file(self, upload: Upload) -> None:
        if upload.storage_backend != "local" or self.settings.upload_storage_backend != "local":
            return
        root = Path(self.settings.upload_storage_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        root = root.resolve()
        path = (root / upload.storage_key).resolve()
        if root in path.parents and path.exists():
            path.unlink()

    async def _require_user(self, user_id: str) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("user_not_found", "User not found")
        return user

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

    def _append_privacy_note(self, note: str | None) -> str:
        suffix = "disabled by privacy deletion"
        if not note:
            return suffix
        if suffix in note:
            return note
        return f"{note[:430]} | {suffix}"


def anonymous_username_for(user_id: str) -> str:
    compact = "".join(char for char in user_id.lower() if char.isalnum())
    return f"{ANON_USERNAME_PREFIX}-{compact[:18]}"


def anonymous_email_for(user_id: str) -> str:
    compact = "".join(char for char in user_id.lower() if char.isalnum())
    return f"deleted-{compact}@{DELETED_EMAIL_DOMAIN}"


def redact_email_from_mapping(
    value: dict[str, object],
    old_email: str,
    anonymous_email: str,
) -> dict[str, object]:
    return {
        str(key): redact_email_value(child, old_email, anonymous_email)
        for key, child in (value or {}).items()
    }


def redact_email_value(value: object, old_email: str, anonymous_email: str) -> object:
    if isinstance(value, str):
        return value.replace(old_email, anonymous_email)
    if isinstance(value, dict):
        return redact_email_from_mapping(value, old_email, anonymous_email)
    if isinstance(value, list):
        return [redact_email_value(item, old_email, anonymous_email) for item in value]
    return value
