from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import BOARD_MODERATOR_ROLES, is_admin, is_global_moderator
from app.db.base import utcnow
from app.models.forum import BoardMember, Post, Topic
from app.models.moderation import AuditLog, Flag
from app.models.user import User
from app.schemas.moderation import (
    AuditLogResponse,
    FlagCreateRequest,
    FlagResponse,
    FlagStatusUpdateRequest,
    HideContentRequest,
    ModerationActionResponse,
    ModerationTargetResponse,
    UserStatusResponse,
    UserStatusUpdateRequest,
)
from app.services.spam import SpamPreventionService

VALID_FLAG_STATUSES = {"pending", "resolved", "rejected"}


@dataclass(frozen=True)
class ModerationTarget:
    target_type: str
    target_id: str
    topic_id: str | None
    topic_slug: str | None
    post_number: int | None
    board_id: str
    board_slug: str
    board_name: str
    author_id: str
    author_name: str
    title: str
    excerpt: str
    hidden: bool
    topic: Topic | None = None
    post: Post | None = None

    def to_response(self) -> ModerationTargetResponse:
        return ModerationTargetResponse(
            target_type=self.target_type,
            target_id=self.target_id,
            topic_id=self.topic_id,
            topic_slug=self.topic_slug,
            post_number=self.post_number,
            board_id=self.board_id,
            board_slug=self.board_slug,
            board_name=self.board_name,
            author_id=self.author_id,
            author_name=self.author_name,
            title=self.title,
            excerpt=self.excerpt,
            hidden=self.hidden,
        )


class ModerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_flag(
        self,
        payload: FlagCreateRequest,
        current_user: User,
        request: Request | None = None,
    ) -> FlagResponse:
        await SpamPreventionService(self.session).enforce_flag(request, current_user=current_user)
        target = await self._resolve_target(payload.target_type, payload.target_id)
        existing_flag = await self.session.scalar(
            select(Flag)
            .options(selectinload(Flag.reporter), selectinload(Flag.resolved_by))
            .where(
                Flag.target_type == payload.target_type,
                Flag.target_id == payload.target_id,
                Flag.reporter_id == current_user.id,
                Flag.status == "pending",
            )
        )
        if existing_flag:
            return await self.get_flag(
                existing_flag.id,
                current_user=current_user,
                allow_reporter=True,
            )

        flag = Flag(
            target_type=payload.target_type,
            target_id=payload.target_id,
            board_id=target.board_id,
            reporter_id=current_user.id,
            reason=payload.reason,
            detail=payload.detail.strip() if payload.detail else None,
            status="pending",
        )
        self.session.add(flag)
        await self.session.flush()
        self._add_audit_log(
            actor_id=current_user.id,
            action="flag_created",
            target_type=payload.target_type,
            target_id=payload.target_id,
            board_id=target.board_id,
            data={"flag_id": flag.id, "reason": payload.reason},
        )
        await self.session.commit()
        return await self.get_flag(flag.id, current_user=current_user, allow_reporter=True)

    async def list_flags(
        self,
        current_user: User,
        *,
        status: str | None = "pending",
        limit: int = 50,
    ) -> list[FlagResponse]:
        board_ids = await self._moderatable_board_ids(current_user)
        statement = (
            select(Flag)
            .options(selectinload(Flag.reporter), selectinload(Flag.resolved_by))
            .order_by(desc(Flag.created_at))
            .limit(limit)
        )
        if status:
            if status not in VALID_FLAG_STATUSES:
                raise ValidationError("invalid_flag_status", "Flag status is invalid")
            statement = statement.where(Flag.status == status)
        if not self._is_global_moderator(current_user):
            if not board_ids:
                raise PermissionDeniedError(
                    "moderation_forbidden", "Moderation permission required"
                )
            statement = statement.where(Flag.board_id.in_(board_ids))

        flags = list(await self.session.scalars(statement))
        responses: list[FlagResponse] = []
        for flag in flags:
            target = await self._resolve_target(
                flag.target_type, flag.target_id, include_hidden=True
            )
            responses.append(FlagResponse.from_model(flag, target.to_response()))
        return responses

    async def get_flag(
        self,
        flag_id: str,
        *,
        current_user: User,
        allow_reporter: bool = False,
    ) -> FlagResponse:
        flag = await self._get_flag(flag_id)
        if allow_reporter and flag.reporter_id == current_user.id:
            target = await self._resolve_target(
                flag.target_type, flag.target_id, include_hidden=True
            )
            return FlagResponse.from_model(flag, target.to_response())
        await self._require_can_moderate_board(current_user, flag.board_id)
        target = await self._resolve_target(flag.target_type, flag.target_id, include_hidden=True)
        return FlagResponse.from_model(flag, target.to_response())

    async def update_flag_status(
        self,
        flag_id: str,
        payload: FlagStatusUpdateRequest,
        current_user: User,
    ) -> FlagResponse:
        flag = await self._get_flag(flag_id)
        await self._require_can_moderate_board(current_user, flag.board_id)
        previous_status = flag.status
        flag.status = payload.status
        flag.resolution_note = payload.resolution_note.strip() if payload.resolution_note else None
        if payload.status == "pending":
            flag.resolved_by_id = None
            flag.resolved_at = None
        else:
            flag.resolved_by_id = current_user.id
            flag.resolved_at = utcnow()
        self._add_audit_log(
            actor_id=current_user.id,
            action="flag_status_changed",
            target_type=flag.target_type,
            target_id=flag.target_id,
            board_id=flag.board_id,
            data={
                "flag_id": flag.id,
                "from_status": previous_status,
                "to_status": payload.status,
            },
        )
        await self.session.commit()
        return await self.get_flag(flag.id, current_user=current_user)

    async def hide_topic(
        self,
        topic_id: str,
        payload: HideContentRequest,
        current_user: User,
    ) -> ModerationActionResponse:
        target = await self._resolve_target("topic", topic_id, include_hidden=True)
        if not target.topic:
            raise NotFoundError("topic_not_found", "Topic not found")
        await self._require_can_moderate_board(current_user, target.board_id)
        target.topic.deleted_at = utcnow()
        target.topic.status = "hidden"
        self._add_audit_log(
            actor_id=current_user.id,
            action="topic_hidden",
            target_type="topic",
            target_id=topic_id,
            board_id=target.board_id,
            data={"note": payload.note or ""},
        )
        await self.session.commit()
        return ModerationActionResponse(
            target_type="topic", target_id=topic_id, hidden=True, status="hidden"
        )

    async def restore_topic(
        self,
        topic_id: str,
        payload: HideContentRequest,
        current_user: User,
    ) -> ModerationActionResponse:
        target = await self._resolve_target("topic", topic_id, include_hidden=True)
        if not target.topic:
            raise NotFoundError("topic_not_found", "Topic not found")
        await self._require_can_moderate_board(current_user, target.board_id)
        target.topic.deleted_at = None
        target.topic.status = "open"
        self._add_audit_log(
            actor_id=current_user.id,
            action="topic_restored",
            target_type="topic",
            target_id=topic_id,
            board_id=target.board_id,
            data={"note": payload.note or ""},
        )
        await self.session.commit()
        return ModerationActionResponse(
            target_type="topic", target_id=topic_id, hidden=False, status="open"
        )

    async def hide_post(
        self,
        post_id: str,
        payload: HideContentRequest,
        current_user: User,
    ) -> ModerationActionResponse:
        target = await self._resolve_target("post", post_id, include_hidden=True)
        if not target.post:
            raise NotFoundError("post_not_found", "Post not found")
        await self._require_can_moderate_board(current_user, target.board_id)
        target.post.deleted_at = utcnow()
        self._add_audit_log(
            actor_id=current_user.id,
            action="post_hidden",
            target_type="post",
            target_id=post_id,
            board_id=target.board_id,
            data={"note": payload.note or ""},
        )
        await self.session.commit()
        return ModerationActionResponse(target_type="post", target_id=post_id, hidden=True)

    async def restore_post(
        self,
        post_id: str,
        payload: HideContentRequest,
        current_user: User,
    ) -> ModerationActionResponse:
        target = await self._resolve_target("post", post_id, include_hidden=True)
        if not target.post:
            raise NotFoundError("post_not_found", "Post not found")
        await self._require_can_moderate_board(current_user, target.board_id)
        target.post.deleted_at = None
        self._add_audit_log(
            actor_id=current_user.id,
            action="post_restored",
            target_type="post",
            target_id=post_id,
            board_id=target.board_id,
            data={"note": payload.note or ""},
        )
        await self.session.commit()
        return ModerationActionResponse(target_type="post", target_id=post_id, hidden=False)

    async def update_user_status(
        self,
        user_id: str,
        payload: UserStatusUpdateRequest,
        current_user: User,
    ) -> UserStatusResponse:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")
        if current_user.id == user_id:
            raise ValidationError("cannot_moderate_self", "Cannot change your own status")
        user = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("user_not_found", "User not found")
        previous_status = user.status
        user.status = payload.status
        self._add_audit_log(
            actor_id=current_user.id,
            action="user_status_changed",
            target_type="user",
            target_id=user.id,
            board_id=None,
            data={
                "from_status": previous_status,
                "to_status": payload.status,
                "note": payload.note or "",
            },
        )
        await self.session.commit()
        return UserStatusResponse(user_id=user.id, username=user.username, status=user.status)

    async def list_audit_logs(
        self, current_user: User, *, limit: int = 50
    ) -> list[AuditLogResponse]:
        board_ids = await self._moderatable_board_ids(current_user)
        statement = (
            select(AuditLog)
            .options(selectinload(AuditLog.actor))
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        if not self._is_global_moderator(current_user):
            if not board_ids:
                raise PermissionDeniedError(
                    "moderation_forbidden", "Moderation permission required"
                )
            statement = statement.where(AuditLog.board_id.in_(board_ids))
        logs = list(await self.session.scalars(statement))
        return [AuditLogResponse.from_model(log) for log in logs]

    async def _get_flag(self, flag_id: str) -> Flag:
        flag = await self.session.scalar(
            select(Flag)
            .options(selectinload(Flag.reporter), selectinload(Flag.resolved_by))
            .where(Flag.id == flag_id)
        )
        if not flag:
            raise NotFoundError("flag_not_found", "Flag not found")
        return flag

    async def _resolve_target(
        self,
        target_type: str,
        target_id: str,
        *,
        include_hidden: bool = False,
    ) -> ModerationTarget:
        if target_type == "topic":
            topic = await self.session.scalar(
                select(Topic)
                .options(selectinload(Topic.board), selectinload(Topic.author))
                .where(Topic.id == target_id)
            )
            if not topic or (topic.deleted_at and not include_hidden):
                raise NotFoundError("topic_not_found", "Topic not found")
            return ModerationTarget(
                target_type="topic",
                target_id=topic.id,
                topic_id=topic.id,
                topic_slug=topic.slug,
                post_number=None,
                board_id=topic.board_id,
                board_slug=topic.board.slug,
                board_name=topic.board.name,
                author_id=topic.user_id,
                author_name=topic.author.username,
                title=topic.title,
                excerpt=topic.title,
                hidden=topic.deleted_at is not None or topic.status == "hidden",
                topic=topic,
            )

        if target_type == "post":
            post = await self.session.scalar(
                select(Post)
                .options(
                    selectinload(Post.author),
                    selectinload(Post.topic).selectinload(Topic.board),
                )
                .where(Post.id == target_id)
            )
            if not post or (post.deleted_at and not include_hidden):
                raise NotFoundError("post_not_found", "Post not found")
            topic = post.topic
            board = topic.board
            return ModerationTarget(
                target_type="post",
                target_id=post.id,
                topic_id=topic.id,
                topic_slug=topic.slug,
                post_number=post.post_number,
                board_id=topic.board_id,
                board_slug=board.slug,
                board_name=board.name,
                author_id=post.user_id,
                author_name=post.author.username,
                title=f"{topic.title} · #{post.post_number}",
                excerpt=post.raw_md[:180],
                hidden=post.deleted_at is not None,
                post=post,
            )

        raise ValidationError("invalid_flag_target", "Flag target type is invalid")

    async def _moderatable_board_ids(self, current_user: User) -> set[str]:
        if self._is_global_moderator(current_user):
            return set()
        result = await self.session.scalars(
            select(BoardMember.board_id).where(
                BoardMember.user_id == current_user.id,
                BoardMember.role.in_(BOARD_MODERATOR_ROLES),
            )
        )
        return set(result)

    async def _require_can_moderate_board(self, current_user: User, board_id: str) -> None:
        if self._is_global_moderator(current_user):
            return
        member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == board_id,
                BoardMember.user_id == current_user.id,
                BoardMember.role.in_(BOARD_MODERATOR_ROLES),
            )
        )
        if not member:
            raise PermissionDeniedError("moderation_forbidden", "Moderation permission required")

    def _is_global_moderator(self, current_user: User) -> bool:
        return is_global_moderator(current_user)

    def _add_audit_log(
        self,
        *,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        board_id: str | None,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                board_id=board_id,
                data=data,
                created_at=utcnow(),
            )
        )
