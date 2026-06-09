from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import BOARD_MODERATOR_ROLES, is_admin, is_global_moderator
from app.core.trust import review_priority_for_trust
from app.db.base import utcnow
from app.models.forum import Board, BoardMember, Post, Topic
from app.models.moderation import AuditLog, Flag, Reviewable, ReviewableEvent
from app.models.user import User
from app.schemas.moderation import (
    AuditLogResponse,
    FlagCreateRequest,
    FlagResponse,
    FlagStatusUpdateRequest,
    HideContentRequest,
    ModerationActionResponse,
    ModerationTargetResponse,
    ReviewableAppealRequest,
    ReviewableBulkDecisionRequest,
    ReviewableBulkDecisionResponse,
    ReviewableDecisionRequest,
    ReviewableResponse,
    UserStatusResponse,
    UserStatusUpdateRequest,
)
from app.services.background_jobs import BackgroundJobService
from app.services.integrations import IntegrationService
from app.services.search import SearchIndexService
from app.services.spam import SpamPreventionService

VALID_FLAG_STATUSES = {"pending", "resolved", "rejected"}
VALID_REVIEWABLE_STATUSES = {
    "pending",
    "claimed",
    "approved",
    "rejected",
    "hidden",
    "deleted",
    "silenced",
    "escalated",
    "appealed",
}
DECISION_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "hide": "hidden",
    "delete": "deleted",
    "silence": "silenced",
    "escalate": "escalated",
}
OPEN_REVIEWABLE_STATUSES = {"pending", "claimed", "appealed"}


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
        await self._create_flag_reviewable(flag, target, current_user)
        self._add_audit_log(
            actor_id=current_user.id,
            action="flag_created",
            target_type=payload.target_type,
            target_id=payload.target_id,
            board_id=target.board_id,
            data={"flag_id": flag.id, "reason": payload.reason},
        )
        await IntegrationService(self.session).enqueue_event(
            "moderation.flag_created",
            {
                "flag_id": flag.id,
                "target_type": payload.target_type,
                "target_id": payload.target_id,
                "board_id": target.board_id,
                "reporter_id": current_user.id,
                "reason": payload.reason,
                "created_at": flag.created_at.isoformat(),
            },
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
        await SearchIndexService(self.session).remove_topic(target.topic.id)
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
        await SearchIndexService(self.session).sync_topic(target.topic.id)
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
        await SearchIndexService(self.session).sync_topic(target.topic_id or target.post.topic_id)
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
        await SearchIndexService(self.session).sync_topic(target.topic_id or target.post.topic_id)
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

    async def create_content_reviewable(
        self,
        *,
        current_user: User,
        reviewable_type: str,
        board: Board,
        sanitized_fields: dict[str, str],
        matched_fields: tuple[str, ...],
        data: dict[str, object],
        topic: Topic | None = None,
        post: Post | None = None,
        source: str = "content_safety",
        source_summary: str = "Content matched a pending-review safety rule",
    ) -> Reviewable:
        title = str(data.get("title") or data.get("topic_title") or "Content pending review")
        excerpt = str(sanitized_fields.get("raw_md") or sanitized_fields.get("title") or title)[
            :180
        ]
        reviewable = Reviewable(
            type=reviewable_type,
            status="pending",
            priority=review_priority_for_trust(80, current_user.trust_level),
            source=source,
            source_summary=source_summary,
            target_type="post" if post else ("topic" if topic else None),
            target_id=post.id if post else (topic.id if topic else None),
            board_id=board.id,
            topic_id=topic.id if topic else None,
            post_id=post.id if post else None,
            created_by_id=current_user.id,
            target_user_id=current_user.id,
            data={
                **data,
                "title": title,
                "excerpt": excerpt,
                "fields": sanitized_fields,
                "matched_fields": list(matched_fields),
            },
        )
        self.session.add(reviewable)
        await self.session.flush()
        self._add_reviewable_event(
            reviewable,
            actor_id=current_user.id,
            event="created",
            from_status=None,
            to_status=reviewable.status,
            note=None,
            data={"source": reviewable.source, "matched_fields": list(matched_fields)},
        )
        self._add_audit_log(
            actor_id=current_user.id,
            action="reviewable_created",
            target_type="reviewable",
            target_id=reviewable.id,
            board_id=board.id,
            data={
                "type": reviewable.type,
                "source": reviewable.source,
                "matched_fields": list(matched_fields),
            },
        )
        return reviewable

    async def list_reviewables(
        self,
        current_user: User,
        *,
        status: str | None = "pending",
        reviewable_type: str | None = None,
        limit: int = 50,
    ) -> list[ReviewableResponse]:
        statement = (
            select(Reviewable)
            .options(*self._reviewable_options())
            .order_by(Reviewable.priority.asc(), desc(Reviewable.created_at))
            .limit(limit)
        )
        if status and status != "all":
            if status not in VALID_REVIEWABLE_STATUSES:
                raise ValidationError("invalid_reviewable_status", "Reviewable status is invalid")
            statement = statement.where(Reviewable.status == status)
        if reviewable_type:
            statement = statement.where(Reviewable.type == reviewable_type)
        if not self._is_global_moderator(current_user):
            board_ids = await self._moderatable_board_ids(current_user)
            if not board_ids:
                raise PermissionDeniedError(
                    "moderation_forbidden", "Moderation permission required"
                )
            statement = statement.where(Reviewable.board_id.in_(board_ids))
        reviewables = list(await self.session.scalars(statement))
        return [ReviewableResponse.from_model(reviewable) for reviewable in reviewables]

    async def list_my_reviewables(
        self,
        current_user: User,
        *,
        limit: int = 50,
    ) -> list[ReviewableResponse]:
        reviewables = list(
            await self.session.scalars(
                select(Reviewable)
                .options(*self._reviewable_options())
                .where(
                    (Reviewable.created_by_id == current_user.id)
                    | (Reviewable.target_user_id == current_user.id)
                )
                .order_by(desc(Reviewable.created_at))
                .limit(limit)
            )
        )
        return [
            ReviewableResponse.from_model(
                reviewable,
                include_private_data=False,
                current_user_id=current_user.id,
            )
            for reviewable in reviewables
        ]

    async def claim_reviewable(self, reviewable_id: str, current_user: User) -> ReviewableResponse:
        reviewable = await self._get_reviewable(reviewable_id)
        await self._require_can_access_reviewable(current_user, reviewable)
        if reviewable.status not in {"pending", "claimed", "appealed"}:
            raise ValidationError("reviewable_not_open", "Reviewable is not open")
        if reviewable.assigned_to_id and reviewable.assigned_to_id != current_user.id:
            raise ConflictError(
                "reviewable_already_claimed",
                "Reviewable has already been claimed",
                {"assigned_to_id": reviewable.assigned_to_id},
            )
        previous_status = reviewable.status
        reviewable.status = "claimed"
        reviewable.assigned_to_id = current_user.id
        reviewable.assigned_at = utcnow()
        self._record_reviewable_transition(
            reviewable,
            actor=current_user,
            event="claimed",
            from_status=previous_status,
            to_status=reviewable.status,
            note=None,
            data={},
        )
        await self.session.commit()
        return ReviewableResponse.from_model(await self._get_reviewable(reviewable.id))

    async def release_reviewable(
        self,
        reviewable_id: str,
        current_user: User,
    ) -> ReviewableResponse:
        reviewable = await self._get_reviewable(reviewable_id)
        await self._require_can_access_reviewable(current_user, reviewable)
        if reviewable.assigned_to_id and (
            reviewable.assigned_to_id != current_user.id
            and not self._is_global_moderator(current_user)
        ):
            raise PermissionDeniedError("reviewable_claim_required", "Reviewable is claimed")
        previous_status = reviewable.status
        reviewable.status = "pending" if reviewable.status == "claimed" else reviewable.status
        reviewable.assigned_to_id = None
        reviewable.assigned_at = None
        self._record_reviewable_transition(
            reviewable,
            actor=current_user,
            event="released",
            from_status=previous_status,
            to_status=reviewable.status,
            note=None,
            data={},
        )
        await self.session.commit()
        return ReviewableResponse.from_model(await self._get_reviewable(reviewable.id))

    async def decide_reviewable(
        self,
        reviewable_id: str,
        payload: ReviewableDecisionRequest,
        current_user: User,
    ) -> ReviewableResponse:
        """Apply one moderator decision and commit the result.

        Key parameters are the reviewable id, decision payload, and actor.
        Return value is the refreshed reviewable response. Side effect: mutates
        the target content, reviewable status, notifications, and audit log.
        """

        reviewable = await self._decide_reviewable_in_session(
            reviewable_id,
            payload,
            current_user,
        )
        await self.session.commit()
        return ReviewableResponse.from_model(await self._get_reviewable(reviewable.id))

    async def decide_reviewables_bulk(
        self,
        payload: ReviewableBulkDecisionRequest,
        current_user: User,
    ) -> ReviewableBulkDecisionResponse:
        """Apply one decision action to multiple reviewables in a single transaction.

        Key parameters are a bulk decision payload and actor. Return value
        reports the unique processed reviewables. Side effect: commits all
        reviewable decisions together, or rolls the batch back when any item
        fails validation or target mutation.
        """

        unique_ids = list(dict.fromkeys(payload.reviewable_ids))
        decision_payload = ReviewableDecisionRequest(action=payload.action, note=payload.note)
        decided_ids: list[str] = []
        try:
            for reviewable_id in unique_ids:
                reviewable = await self._decide_reviewable_in_session(
                    reviewable_id,
                    decision_payload,
                    current_user,
                )
                decided_ids.append(reviewable.id)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        decided_reviewables = await self._get_reviewables_by_ids(decided_ids)
        return ReviewableBulkDecisionResponse(
            action=payload.action,
            requested_count=len(payload.reviewable_ids),
            processed_count=len(decided_reviewables),
            reviewables=[ReviewableResponse.from_model(reviewable) for reviewable in decided_reviewables],
        )

    async def _decide_reviewable_in_session(
        self,
        reviewable_id: str,
        payload: ReviewableDecisionRequest,
        current_user: User,
    ) -> Reviewable:
        """Mutate one reviewable decision without committing the transaction.

        Key parameters are the reviewable id, decision payload, and actor.
        Return value is the mutated ORM reviewable. Side effect: applies content
        publishing/hiding/silencing work, notifications, and audit rows in the
        current session only.
        """

        reviewable = await self._get_reviewable(reviewable_id)
        await self._require_can_access_reviewable(current_user, reviewable)
        if reviewable.status not in OPEN_REVIEWABLE_STATUSES:
            raise ValidationError("reviewable_not_open", "Reviewable is not open")
        previous_status = reviewable.status
        target_status = DECISION_STATUS[payload.action]
        await self._apply_reviewable_decision(
            reviewable,
            payload.action,
            actor=current_user,
            note=payload.note,
        )
        reviewable.status = target_status
        reviewable.resolved_by_id = current_user.id
        reviewable.resolved_at = utcnow()
        reviewable.assigned_to_id = current_user.id
        reviewable.assigned_at = reviewable.assigned_at or utcnow()
        self._record_reviewable_transition(
            reviewable,
            actor=current_user,
            event="decided",
            from_status=previous_status,
            to_status=reviewable.status,
            note=payload.note,
            data={"action": payload.action},
        )
        if reviewable.source != "frontier_news":
            await self._notify_reviewable_user(
                reviewable,
                actor=current_user,
                event="decided",
                idempotency_suffix=payload.action,
            )
        return reviewable

    async def appeal_reviewable(
        self,
        reviewable_id: str,
        payload: ReviewableAppealRequest,
        current_user: User,
    ) -> ReviewableResponse:
        reviewable = await self._get_reviewable(reviewable_id)
        if current_user.id not in {reviewable.created_by_id, reviewable.target_user_id}:
            raise PermissionDeniedError("reviewable_forbidden", "Reviewable access denied")
        if reviewable.status not in {"rejected", "hidden", "deleted", "silenced", "escalated"}:
            raise ValidationError("reviewable_appeal_unavailable", "Reviewable cannot be appealed")
        previous_status = reviewable.status
        reviewable.status = "appealed"
        reviewable.data = {
            **reviewable.data,
            "appeal_count": int(reviewable.data.get("appeal_count") or 0) + 1,
        }
        self._record_reviewable_transition(
            reviewable,
            actor=current_user,
            event="appealed",
            from_status=previous_status,
            to_status=reviewable.status,
            note=payload.reason,
            data={},
        )
        await self._notify_reviewable_staff(
            reviewable,
            actor=current_user,
            idempotency_suffix=str(reviewable.data["appeal_count"]),
        )
        await self.session.commit()
        return ReviewableResponse.from_model(
            await self._get_reviewable(reviewable.id),
            include_private_data=False,
            current_user_id=current_user.id,
        )

    async def _create_flag_reviewable(
        self,
        flag: Flag,
        target: ModerationTarget,
        current_user: User,
    ) -> Reviewable:
        existing = await self.session.scalar(
            select(Reviewable).where(Reviewable.flag_id == flag.id)
        )
        if existing:
            return existing
        reviewable = Reviewable(
            type="flag",
            status="pending",
            priority=50,
            source="flag",
            source_summary=f"User report: {flag.reason}",
            target_type=flag.target_type,
            target_id=flag.target_id,
            board_id=target.board_id,
            topic_id=target.topic_id,
            post_id=target.target_id if target.target_type == "post" else None,
            flag_id=flag.id,
            created_by_id=current_user.id,
            target_user_id=target.author_id,
            data={
                "reason": flag.reason,
                "detail": flag.detail,
                "title": target.title,
                "excerpt": target.excerpt,
                "topic_slug": target.topic_slug,
                "post_number": target.post_number,
            },
        )
        self.session.add(reviewable)
        await self.session.flush()
        self._add_reviewable_event(
            reviewable,
            actor_id=current_user.id,
            event="created",
            from_status=None,
            to_status=reviewable.status,
            note=flag.detail,
            data={"source": "flag", "flag_id": flag.id, "reason": flag.reason},
        )
        self._add_audit_log(
            actor_id=current_user.id,
            action="reviewable_created",
            target_type="reviewable",
            target_id=reviewable.id,
            board_id=target.board_id,
            data={"type": "flag", "flag_id": flag.id, "reason": flag.reason},
        )
        return reviewable

    def _reviewable_options(self):
        return (
            selectinload(Reviewable.board),
            selectinload(Reviewable.created_by),
            selectinload(Reviewable.target_user),
            selectinload(Reviewable.assigned_to),
            selectinload(Reviewable.resolved_by),
            selectinload(Reviewable.events).selectinload(ReviewableEvent.actor),
        )

    async def _get_reviewable(self, reviewable_id: str) -> Reviewable:
        reviewable = await self.session.scalar(
            select(Reviewable)
            .options(*self._reviewable_options())
            .where(Reviewable.id == reviewable_id)
        )
        if not reviewable:
            raise NotFoundError("reviewable_not_found", "Reviewable not found")
        return reviewable

    async def _get_reviewables_by_ids(self, reviewable_ids: list[str]) -> list[Reviewable]:
        """Return refreshed reviewables in caller-provided order.

        Key parameter `reviewable_ids` should be unique ids already processed
        by the current service call. Return value omits missing ids only after
        commit-time refresh; the method has no side effects.
        """

        if not reviewable_ids:
            return []

        reviewables = list(
            await self.session.scalars(
                select(Reviewable)
                .options(*self._reviewable_options())
                .where(Reviewable.id.in_(reviewable_ids))
            )
        )
        reviewable_by_id = {reviewable.id: reviewable for reviewable in reviewables}
        return [
            reviewable_by_id[reviewable_id]
            for reviewable_id in reviewable_ids
            if reviewable_id in reviewable_by_id
        ]

    async def _require_can_access_reviewable(
        self,
        current_user: User,
        reviewable: Reviewable,
    ) -> None:
        if reviewable.board_id is None:
            if not self._is_global_moderator(current_user):
                raise PermissionDeniedError(
                    "moderation_forbidden", "Moderation permission required"
                )
            return
        await self._require_can_moderate_board(current_user, reviewable.board_id)

    async def _apply_reviewable_decision(
        self,
        reviewable: Reviewable,
        action: str,
        *,
        actor: User,
        note: str | None = None,
    ) -> None:
        """Apply a moderator decision and trigger target side effects.

        `queued_topic` approval publishes content immediately; frontier news rows are
        synchronized here so the material pool reflects the same unified moderation decision.
        """

        if action == "reject" and reviewable.flag_id:
            await self._set_flag_status(reviewable.flag_id, "rejected", None)
            return
        if action == "reject" and reviewable.source == "frontier_news":
            from app.services.frontier_news import FrontierNewsService

            await FrontierNewsService(self.session).record_reviewable_decision(
                reviewable,
                action=action,
                actor=actor,
                note=note,
            )
            return
        if action in {"approve", "escalate"}:
            if action == "approve":
                if reviewable.type == "queued_topic":
                    from app.services.forum import ForumService

                    if reviewable.source == "frontier_news":
                        from app.services.frontier_news import FrontierNewsService

                        await FrontierNewsService(self.session).refresh_reviewable_public_copy(
                            reviewable
                        )
                    await ForumService(self.session).publish_queued_topic(reviewable)
                    if reviewable.source == "frontier_news":
                        from app.services.frontier_news import FrontierNewsService

                        await FrontierNewsService(self.session).record_reviewable_decision(
                            reviewable,
                            action=action,
                            actor=actor,
                            note=note,
                        )
                elif reviewable.type == "queued_post":
                    from app.services.forum import ForumService

                    await ForumService(self.session).publish_queued_post(reviewable)
                elif reviewable.type == "queued_edit":
                    from app.services.forum import ForumService

                    await ForumService(self.session).publish_queued_edit(reviewable)
            if reviewable.flag_id:
                await self._set_flag_status(reviewable.flag_id, "resolved", None)
            return
        if action in {"hide", "delete"}:
            await self._hide_reviewable_target(reviewable, delete=(action == "delete"))
            if reviewable.flag_id:
                await self._set_flag_status(reviewable.flag_id, "resolved", None)
            return
        if action == "silence":
            if not reviewable.target_user_id:
                raise ValidationError("reviewable_target_user_required", "Target user is required")
            user = await self.session.get(User, reviewable.target_user_id)
            if not user:
                raise NotFoundError("user_not_found", "User not found")
            user.status = "silenced"
            if reviewable.flag_id:
                await self._set_flag_status(reviewable.flag_id, "resolved", None)
            return

    async def _hide_reviewable_target(self, reviewable: Reviewable, *, delete: bool) -> None:
        if reviewable.target_type == "topic" and reviewable.target_id:
            topic = await self.session.get(Topic, reviewable.target_id)
            if not topic:
                raise NotFoundError("topic_not_found", "Topic not found")
            topic.deleted_at = utcnow()
            topic.status = "hidden"
            await SearchIndexService(self.session).remove_topic(topic.id)
            return
        if reviewable.target_type == "post" and reviewable.target_id:
            post = await self.session.get(Post, reviewable.target_id)
            if not post:
                raise NotFoundError("post_not_found", "Post not found")
            post.deleted_at = utcnow()
            if delete:
                post.raw_md = ""
                post.cooked_html = ""
            await SearchIndexService(self.session).sync_topic(post.topic_id)
            return
        raise ValidationError("reviewable_target_required", "Reviewable target is required")

    async def _set_flag_status(
        self,
        flag_id: str,
        status: str,
        resolution_note: str | None,
    ) -> None:
        flag = await self.session.get(Flag, flag_id)
        if not flag:
            return
        flag.status = status
        flag.resolution_note = resolution_note
        flag.resolved_at = utcnow()

    def _record_reviewable_transition(
        self,
        reviewable: Reviewable,
        *,
        actor: User,
        event: str,
        from_status: str | None,
        to_status: str | None,
        note: str | None,
        data: dict[str, object],
    ) -> None:
        self._add_reviewable_event(
            reviewable,
            actor_id=actor.id,
            event=event,
            from_status=from_status,
            to_status=to_status,
            note=note,
            data=data,
        )
        self._add_audit_log(
            actor_id=actor.id,
            action=f"reviewable_{event}",
            target_type="reviewable",
            target_id=reviewable.id,
            board_id=reviewable.board_id,
            data={
                "from_status": from_status,
                "to_status": to_status,
                "note": note or "",
                **data,
            },
        )

    def _add_reviewable_event(
        self,
        reviewable: Reviewable,
        *,
        actor_id: str | None,
        event: str,
        from_status: str | None,
        to_status: str | None,
        note: str | None,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            ReviewableEvent(
                reviewable_id=reviewable.id,
                actor_id=actor_id,
                event=event,
                from_status=from_status,
                to_status=to_status,
                note=note.strip() if note else None,
                data=data,
                created_at=utcnow(),
            )
        )

    async def _notify_reviewable_user(
        self,
        reviewable: Reviewable,
        *,
        actor: User,
        event: str,
        idempotency_suffix: str,
    ) -> None:
        user_id = reviewable.target_user_id or reviewable.created_by_id
        if not user_id or user_id == actor.id:
            return
        await BackgroundJobService(self.session).enqueue_notification(
            user_id=user_id,
            kind="moderation",
            topic_id=reviewable.topic_id,
            post_id=reviewable.post_id,
            actor_id=actor.id,
            data=self._notification_data(reviewable, event=event, actor=actor),
            idempotency_key=f"reviewable:{reviewable.id}:{event}:{idempotency_suffix}",
            commit=False,
        )

    async def _notify_reviewable_staff(
        self,
        reviewable: Reviewable,
        *,
        actor: User,
        idempotency_suffix: str,
    ) -> None:
        user_id = reviewable.assigned_to_id or reviewable.resolved_by_id
        if not user_id or user_id == actor.id:
            return
        await BackgroundJobService(self.session).enqueue_notification(
            user_id=user_id,
            kind="moderation",
            topic_id=reviewable.topic_id,
            post_id=reviewable.post_id,
            actor_id=actor.id,
            data=self._notification_data(reviewable, event="appealed", actor=actor),
            idempotency_key=f"reviewable:{reviewable.id}:appeal:{idempotency_suffix}",
            commit=False,
        )

    def _notification_data(
        self,
        reviewable: Reviewable,
        *,
        event: str,
        actor: User,
    ) -> dict[str, object]:
        return {
            "reviewable_id": reviewable.id,
            "reviewable_status": reviewable.status,
            "reviewable_type": reviewable.type,
            "event": event,
            "topic_title": reviewable.data.get("title") or reviewable.source_summary,
            "topic_slug": reviewable.data.get("topic_slug"),
            "post_number": reviewable.data.get("post_number"),
            "board_slug": reviewable.board.slug if reviewable.board else None,
            "board_name": reviewable.board.name if reviewable.board else None,
            "actor_name": actor.username,
        }

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
