from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import case, desc, func, not_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import BOARD_MODERATOR_ROLES, is_admin, is_global_moderator
from app.db.base import new_random_suffix, utcnow
from app.models.forum import (
    Board,
    BoardInvitation,
    BoardMember,
    NotificationLevel,
    Poll,
    PollOption,
    PollVote,
    Post,
    PostRevision,
    Tag,
    Topic,
    TopicRead,
)
from app.models.interaction import Notification
from app.models.moderation import AuditLog, Reviewable
from app.models.search import SearchDocument
from app.models.social import PrivateMessageParticipant, UserRelationship
from app.models.upload import Upload
from app.models.user import User
from app.schemas.forum import (
    BoardCreateRequest,
    BoardInviteCreateRequest,
    BoardMemberUpdateRequest,
    BoardSettingsResponse,
    BoardSettingsUpdateRequest,
    PollVoteRequest,
    PostCreateRequest,
    PostRevisionRestoreRequest,
    PostSort,
    PostUpdateRequest,
    TopicCreateRequest,
    TopicLifecycleRequest,
    TopicMergeRequest,
    TopicMoveRequest,
    TopicSolutionRequest,
    TopicSort,
    TopicSplitRequest,
)
from app.schemas.interactions import TopicNotificationLevelResponse
from app.services.background_jobs import BackgroundJobService
from app.services.badges import BadgeTrustService
from app.services.content_safety import moderate_text_fields
from app.services.growth import GrowthService
from app.services.integrations import IntegrationService
from app.services.search import (
    SearchIndexService,
    search_match_conditions,
    search_relevance_expression,
)
from app.services.spam import SpamPreventionService
from app.services.uploads import UploadService

SLUG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
TAG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9一-鿿_.-]+")
MENTION_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])@([A-Za-z0-9_.-]{3,32})")
LIKE_ESCAPE_PATTERN = re.compile(r"([%_\\])")
INLINE_MARKDOWN_LINK_PATTERN = re.compile(
    r"(!?)\[([^\]\n]{0,160})\]\((https?://[^)\s]+|/[^\s)]+)\)"
)
SAFE_UPLOAD_PATH_PATTERN = re.compile(
    r"^/(?:api/v1/)?uploads/(?:"
    r"[1-9][0-9]*|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r")/content(?:\?[^<>\"]*)?$"
)

BOARD_DISPLAY_ORDER = (
    "announcements",
    "resources",
    "benefits",
    "reading",
    "health",
    "news",
    "experience",
    "qna",
    "lounge",
    "feedback",
)

ADMIN_ONLY_TOPIC_BOARD_SLUGS = frozenset({"announcements"})

TAG_DISPLAY_ORDER = (
    "公告",
    "集中帖",
    "精华神帖",
    "快问快答",
    "人工智能",
    "原创",
    "资源分享",
    "福利羊毛",
    "教程",
    "作品集",
    "读书",
    "健康",
    "闲聊",
    "站务反馈",
    "活动",
    "发帖模板",
)


def slugify(value: str, *, fallback_prefix: str = "item") -> str:
    normalized = SLUG_SEPARATOR_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or f"{fallback_prefix}-{new_random_suffix(4)}"


def normalize_tag_name(value: str) -> str:
    return TAG_SEPARATOR_PATTERN.sub("-", value.strip().lower()).strip("-#")


def board_display_order_expression():
    return case(
        *((Board.slug == slug, index) for index, slug in enumerate(BOARD_DISPLAY_ORDER)),
        else_=len(BOARD_DISPLAY_ORDER),
    )


def tag_display_order_expression():
    return case(
        *((Tag.name == name, index) for index, name in enumerate(TAG_DISPLAY_ORDER)),
        else_=len(TAG_DISPLAY_ORDER),
    )


def notification_idempotency_key(
    *,
    kind: str,
    user_id: str,
    topic_id: str | None,
    post_id: str | None,
    actor_id: str | None,
    data: dict[str, object],
) -> str:
    payload = json.dumps(
        {
            "kind": kind,
            "user_id": user_id,
            "topic_id": topic_id,
            "post_id": post_id,
            "actor_id": actor_id,
            "data": data,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return f"notification:{kind}:{user_id}:{sha256(payload.encode()).hexdigest()}"


def render_markdown(raw_md: str) -> str:
    """Render a safe, small Markdown subset until the sanitizer pipeline lands."""

    lines = raw_md.strip().splitlines()
    html_parts: list[str] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        escaped = "<br />".join(
            render_inline_markdown(line.strip()) for line in paragraph_lines if line.strip()
        )
        if escaped:
            html_parts.append(f"<p>{escaped}</p>")
        paragraph_lines.clear()

    def flush_code() -> None:
        if not code_lines:
            return
        escaped = html.escape("\n".join(code_lines))
        html_parts.append(f"<pre><code>{escaped}</code></pre>")
        code_lines.clear()

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_paragraph()
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if line.strip():
            paragraph_lines.append(line)
        else:
            flush_paragraph()

    if in_code:
        flush_code()
    flush_paragraph()

    return "".join(html_parts) or "<p></p>"


def render_inline_markdown(line: str) -> str:
    rendered: list[str] = []
    cursor = 0
    for match in INLINE_MARKDOWN_LINK_PATTERN.finditer(line):
        rendered.append(html.escape(line[cursor : match.start()]))
        marker, label, url = match.groups()
        if is_safe_markdown_url(url):
            safe_url = html.escape(url, quote=True)
            safe_label = html.escape(label or "upload", quote=True)
            if marker:
                rendered.append(f'<img src="{safe_url}" alt="{safe_label}" loading="lazy" />')
            else:
                rendered.append(
                    f'<a href="{safe_url}" target="_blank" rel="nofollow noopener noreferrer">'
                    f"{safe_label}</a>"
                )
        else:
            rendered.append(html.escape(match.group(0)))
        cursor = match.end()
    rendered.append(html.escape(line[cursor:]))
    return "".join(rendered)


def is_safe_markdown_url(url: str) -> bool:
    if url.startswith(("http://", "https://")):
        return True
    return SAFE_UPLOAD_PATH_PATTERN.match(url) is not None


def calculate_hot_score(*, reply_count: int, like_count: int, view_count: int) -> float:
    return round(reply_count * 2 + like_count + view_count / 100, 2)


def escape_like(value: str) -> str:
    return LIKE_ESCAPE_PATTERN.sub(r"\\\1", value)


class ForumService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_board(self, payload: BoardCreateRequest, current_user: User) -> Board:
        existing = await self.session.scalar(select(Board).where(Board.slug == payload.slug))
        if existing:
            raise ConflictError(
                "board_slug_exists",
                "Board slug is already in use",
                {"slug": payload.slug},
            )
        parent_board = await self._resolve_parent_board(
            parent_board_id=payload.parent_board_id,
            parent_board_slug=payload.parent_board_slug,
            current_user=current_user,
        )
        required_tags = self._normalized_unique_tags(payload.required_tags)
        allowed_tags = self._normalized_unique_tags(payload.allowed_tags)
        self._validate_board_tag_policy(required_tags, allowed_tags)

        board = Board(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            color=payload.color,
            owner_id=current_user.id,
            parent_board_id=parent_board.id if parent_board else None,
            visibility=payload.visibility,
            required_tags=required_tags,
            allowed_tags=allowed_tags,
            post_template=self._clean_optional_text(payload.post_template),
            default_notification_level=payload.default_notification_level,
            default_sort=payload.default_sort,
            follower_count=1,
        )
        self.session.add(board)
        await self.session.flush()
        self.session.add(
            BoardMember(
                board_id=board.id,
                user_id=current_user.id,
                role="owner",
                notification_level="watching",
            )
        )
        await self.session.commit()
        return await self.get_board_by_slug(board.slug, current_user=current_user)

    async def list_boards(self, current_user: User | None = None) -> list[Board]:
        statement = (
            select(Board)
            .options(selectinload(Board.parent_board))
            .where(self._board_visible_condition(current_user))
        )
        result = await self.session.scalars(
            statement.order_by(
                board_display_order_expression(),
                desc(Board.topic_count),
                Board.name,
            )
        )
        return list(result)

    async def board_memberships_for_user(
        self,
        board_ids: Iterable[str],
        current_user: User | None,
    ) -> dict[str, BoardMember]:
        if current_user is None:
            return {}
        ids = list(dict.fromkeys(board_ids))
        if not ids:
            return {}
        result = await self.session.scalars(
            select(BoardMember).where(
                BoardMember.board_id.in_(ids),
                BoardMember.user_id == current_user.id,
            )
        )
        return {member.board_id: member for member in result}

    async def get_board_by_slug(
        self,
        slug: str,
        *,
        current_user: User | None = None,
        include_private_for_owner: bool = False,
    ) -> Board:
        board = await self.session.scalar(
            select(Board).options(selectinload(Board.parent_board)).where(Board.slug == slug)
        )
        if not board or (
            not include_private_for_owner and not await self._can_access_board(board, current_user)
        ):
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def get_board_detail(
        self,
        slug: str,
        *,
        current_user: User | None = None,
    ) -> tuple[Board, list[Topic], list[Board]]:
        board = await self.get_board_by_slug(slug, current_user=current_user)
        topics = await self.list_topics(
            board_slug=board.slug,
            sort="latest",
            limit=5,
            current_user=current_user,
        )
        child_boards = await self.list_child_boards(board.id, current_user=current_user)
        return board, topics, child_boards

    async def list_child_boards(
        self,
        parent_board_id: str,
        *,
        current_user: User | None = None,
    ) -> list[Board]:
        result = await self.session.scalars(
            select(Board)
            .options(selectinload(Board.parent_board))
            .where(
                Board.parent_board_id == parent_board_id,
                self._board_visible_condition(current_user),
            )
            .order_by(board_display_order_expression(), desc(Board.topic_count), Board.name)
        )
        return list(result)

    async def get_board_settings(
        self,
        slug: str,
        current_user: User,
    ) -> BoardSettingsResponse:
        board = await self.get_board_by_slug(slug, current_user=current_user)
        await self._require_can_manage_board_settings(current_user, board)
        memberships = await self.board_memberships_for_user([board.id], current_user)
        members = await self.list_board_members(board.id)
        from app.schemas.forum import BoardMemberResponse, BoardResponse

        return BoardSettingsResponse(
            board=BoardResponse.from_board(board, memberships.get(board.id)),
            members=[BoardMemberResponse.from_member(member) for member in members],
        )

    async def update_board_settings(
        self,
        slug: str,
        payload: BoardSettingsUpdateRequest,
        current_user: User,
    ) -> Board:
        board = await self.get_board_by_slug(slug, current_user=current_user)
        await self._require_can_manage_board_settings(current_user, board)
        parent_board = await self._resolve_parent_board(
            parent_board_id=payload.parent_board_id,
            parent_board_slug=payload.parent_board_slug,
            current_user=current_user,
        )
        if parent_board and parent_board.id == board.id:
            raise ValidationError("board_parent_invalid", "Board cannot be its own parent")
        if parent_board and await self._would_create_board_parent_cycle(board.id, parent_board.id):
            raise ValidationError("board_parent_cycle", "Board parent would create a cycle")

        required_tags = self._normalized_unique_tags(payload.required_tags)
        allowed_tags = self._normalized_unique_tags(payload.allowed_tags)
        self._validate_board_tag_policy(required_tags, allowed_tags)

        board.parent_board_id = parent_board.id if parent_board else None
        board.required_tags = required_tags
        board.allowed_tags = allowed_tags
        board.post_template = self._clean_optional_text(payload.post_template)
        board.default_notification_level = payload.default_notification_level
        board.default_sort = payload.default_sort
        board.updated_at = utcnow()
        await self.session.commit()
        return await self.get_board_by_slug(board.slug, current_user=current_user)

    async def list_board_members(self, board_id: str) -> list[BoardMember]:
        result = await self.session.scalars(
            select(BoardMember)
            .options(selectinload(BoardMember.user))
            .where(BoardMember.board_id == board_id)
            .order_by(BoardMember.role.desc(), BoardMember.joined_at)
        )
        return list(result)

    async def update_board_member(
        self,
        slug: str,
        username: str,
        payload: BoardMemberUpdateRequest,
        current_user: User,
    ) -> BoardMember:
        board = await self.get_board_by_slug(slug, current_user=current_user)
        await self._require_can_manage_board_settings(current_user, board)
        target_user = await self.get_user_by_username(username)
        if target_user.id == board.owner_id:
            raise ValidationError(
                "board_owner_role_protected",
                "Board owner membership cannot be demoted through member management.",
            )

        member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id == target_user.id,
            )
        )
        if member is None:
            member = BoardMember(
                board_id=board.id,
                user_id=target_user.id,
                role=payload.role,
                notification_level=payload.notification_level or board.default_notification_level,
            )
            self.session.add(member)
            board.follower_count += 1
        else:
            if member.role == "owner":
                raise ValidationError(
                    "board_owner_role_protected",
                    "Board owner membership cannot be demoted through member management.",
                )
            member.role = payload.role
            if payload.notification_level is not None:
                member.notification_level = payload.notification_level
        await self.session.commit()
        return await self.session.scalar(
            select(BoardMember)
            .options(selectinload(BoardMember.user))
            .where(BoardMember.id == member.id)
        )

    async def remove_board_member(
        self,
        slug: str,
        username: str,
        current_user: User,
    ) -> None:
        board = await self.get_board_by_slug(slug, current_user=current_user)
        await self._require_can_manage_board_settings(current_user, board)
        target_user = await self.get_user_by_username(username)
        member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id == target_user.id,
            )
        )
        if member is None:
            raise NotFoundError("board_member_not_found", "Board member not found")
        if member.role == "owner" or target_user.id == board.owner_id:
            raise ValidationError(
                "board_owner_role_protected",
                "Board owner membership cannot be removed.",
            )
        await self.session.delete(member)
        board.follower_count = max(0, board.follower_count - 1)
        await self.session.commit()

    async def list_topics(
        self,
        *,
        board_slug: str | None = None,
        sort: TopicSort = "latest",
        limit: int = 30,
        query: str | None = None,
        tag: str | None = None,
        author: str | None = None,
        cursor: datetime | None = None,
        current_user: User | None = None,
    ) -> list[Topic]:
        statement = (
            select(Topic)
            .join(Topic.board)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
                selectinload(Topic.poll).selectinload(Poll.options),
            )
            .where(Topic.deleted_at.is_(None), self._board_visible_condition(current_user))
            .where(Topic.visibility == "public")
        )
        if current_user is not None:
            statement = statement.where(self._visible_author_condition(current_user))
        if board_slug:
            board = await self.get_board_by_slug(board_slug, current_user=current_user)
            statement = statement.where(Topic.board_id == board.id)

        relevance = None
        if query and query.strip():
            relevance = search_relevance_expression(query)
            statement = statement.join(
                SearchDocument,
                SearchDocument.topic_id == Topic.id,
            ).where(*search_match_conditions(query))

        if tag:
            normalized_tag = normalize_tag_name(tag)
            if normalized_tag:
                statement = statement.join(Topic.tags).where(
                    or_(Tag.slug == normalized_tag, Tag.name == normalized_tag)
                )

        if author:
            statement = statement.join(Topic.author).where(User.username == author)

        if cursor:
            statement = statement.where(Topic.last_posted_at < cursor)

        if sort == "relevance" and relevance is not None:
            statement = statement.order_by(
                relevance.desc(),
                desc(Topic.last_posted_at),
                desc(Topic.id),
            )
        elif sort == "hot":
            statement = statement.order_by(desc(Topic.hot_score), desc(Topic.last_posted_at))
        elif sort == "top":
            statement = statement.order_by(desc(Topic.like_count), desc(Topic.reply_count))
        elif sort == "votes":
            statement = statement.order_by(
                desc(Topic.vote_score),
                desc(Topic.vote_count),
                desc(Topic.last_posted_at),
            )
        else:
            statement = statement.order_by(desc(Topic.last_posted_at))

        result = await self.session.scalars(statement.distinct().limit(limit))
        topics = list(result)
        await self._decorate_topics_for_user(topics, current_user)
        return topics

    async def get_user_by_username(self, username: str) -> User:
        user = await self.session.scalar(select(User).where(User.username == username))
        if not user:
            raise NotFoundError("user_not_found", "User not found")
        return user

    async def list_tags(
        self,
        *,
        limit: int = 30,
        current_user: User | None = None,
    ) -> list[Tag]:
        visible_tag_ids = (
            select(Tag.id)
            .join(Tag.topics)
            .join(Topic.board)
            .where(
                Tag.topic_count > 0,
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                self._board_visible_condition(current_user),
            )
            .distinct()
        )
        result = await self.session.scalars(
            select(Tag)
            .where(or_(Tag.id.in_(visible_tag_ids), Tag.name.in_(TAG_DISPLAY_ORDER)))
            .order_by(tag_display_order_expression(), desc(Tag.topic_count), Tag.name)
            .limit(limit)
        )
        return list(result)

    async def get_user_content_counts(
        self,
        username: str,
        *,
        current_user: User | None = None,
    ) -> tuple[User, int, int]:
        user = await self.get_user_by_username(username)
        topic_count = (
            await self.session.scalar(
                select(func.count(Topic.id))
                .join(Topic.board)
                .where(
                    Topic.user_id == user.id,
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                    self._board_visible_condition(current_user),
                )
            )
            or 0
        )
        post_count = (
            await self.session.scalar(
                select(func.count(Post.id))
                .join(Post.topic)
                .join(Topic.board)
                .where(
                    Post.user_id == user.id,
                    Post.deleted_at.is_(None),
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                    self._board_visible_condition(current_user),
                )
            )
            or 0
        )
        return user, topic_count, post_count

    async def list_user_topics(
        self,
        username: str,
        *,
        limit: int = 30,
        current_user: User | None = None,
    ) -> list[Topic]:
        user = await self.get_user_by_username(username)
        statement = (
            select(Topic)
            .join(Topic.board)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
            )
            .where(
                Topic.user_id == user.id,
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                self._board_visible_condition(current_user),
            )
            .order_by(desc(Topic.last_posted_at))
            .limit(limit)
        )
        if current_user is not None:
            statement = statement.where(self._visible_author_condition(current_user))
        result = await self.session.scalars(statement)
        return list(result)

    async def create_topic(
        self,
        board_slug: str,
        payload: TopicCreateRequest,
        current_user: User,
        request: Request | None = None,
        *,
        skip_spam_checks: bool = False,
    ) -> Topic:
        board = await self.get_board_by_slug(board_slug, current_user=current_user)
        if not self.can_create_topic_in_board(board, current_user):
            raise PermissionDeniedError(
                "board_topic_create_restricted",
                "Only administrators can create topics in this board.",
            )
        if not skip_spam_checks:
            await SpamPreventionService(self.session).enforce_topic(
                request,
                current_user=current_user,
                title=payload.title,
                raw_md=payload.raw_md,
            )
        normalized_tags = self._normalized_unique_tags(payload.tags)
        self._validate_board_topic_tags(board, normalized_tags)
        try:
            filtered = await self._moderate_or_queue_content(
                {"title": payload.title, "raw_md": payload.raw_md},
                current_user=current_user,
                reviewable_type="queued_topic",
                board=board,
                data={
                    "title": payload.title,
                    "raw_md": payload.raw_md,
                    "tags": normalized_tags,
                    "pinned": payload.pinned,
                    "featured": payload.featured,
                    "board_slug": board.slug,
                },
            )
        except ValidationError as e:
            if e.code == "content_pending_review":
                from app.services.draft import DraftService

                await DraftService(self.session).delete_draft(
                    user_id=current_user.id,
                    target_type="new_topic",
                    target_id="",
                )
            raise e
        title = filtered["title"].strip()
        raw_md = filtered["raw_md"].strip()
        cooked_html = self._render_required_markdown(raw_md)
        topic_slug = await self._unique_topic_slug(board.id, title)
        tags = await self._resolve_tags(normalized_tags)
        now = utcnow()
        topic = Topic(
            board_id=board.id,
            user_id=current_user.id,
            title=title,
            slug=topic_slug,
            pinned=payload.pinned,
            featured=payload.featured,
            hot_score=calculate_hot_score(reply_count=0, like_count=0, view_count=0),
            last_posted_at=now,
            tags=tags,
        )
        self.session.add(topic)
        await self.session.flush()
        first_post = Post(
            topic_id=topic.id,
            user_id=current_user.id,
            post_number=1,
            raw_md=raw_md,
            cooked_html=cooked_html,
        )
        self.session.add(first_post)
        if payload.poll:
            await self._create_poll(topic, payload.poll)
        board.topic_count += 1
        board.post_count += 1
        await self._upsert_read_state(topic.id, current_user.id, post_number=1)
        await self.session.flush()
        await UploadService(self.session).attach_uploads_to_post(
            raw_md,
            post=first_post,
            topic=topic,
            board=board,
            current_user=current_user,
        )
        await self._queue_board_new_topic_notifications(board, topic, first_post, current_user)
        await self._queue_followed_user_new_topic_notifications(topic, first_post, current_user)
        await GrowthService(self.session).award(
            current_user.id,
            "topic_created",
            source_id=topic.id,
            actor_id=current_user.id,
            note="发布主题奖励",
        )
        badge_service = BadgeTrustService(self.session)
        await badge_service.grant_badge(
            user_id=current_user.id,
            badge_slug="first-topic",
            source_type="topic_created",
            source_id=topic.id,
            actor_id=current_user.id,
            note="发布第一条公开主题",
            idempotency_key=f"badge:first-topic:{current_user.id}",
        )
        await badge_service.recompute_trust(
            current_user,
            source_type="topic_created",
            source_id=topic.id,
            actor_id=current_user.id,
            note="发布主题后重算信任等级",
        )
        await IntegrationService(self.session).enqueue_event(
            "topic.created",
            {
                "topic_id": topic.id,
                "title": topic.title,
                "slug": topic.slug,
                "board_id": topic.board_id,
                "board_slug": board.slug,
                "author_id": current_user.id,
                "author_name": current_user.username,
                "created_at": topic.created_at.isoformat(),
            },
        )
        from app.services.plugins import PluginService

        await PluginService(self.session).emit_event(
            "topic.created",
            {
                "topic_id": topic.id,
                "title": topic.title,
                "slug": topic.slug,
                "board_id": topic.board_id,
                "board_slug": board.slug,
                "author_id": current_user.id,
                "author_name": current_user.username,
                "created_at": topic.created_at.isoformat(),
            },
        )
        await SearchIndexService(self.session).sync_topic(topic.id)
        from app.services.draft import DraftService

        await DraftService(self.session).delete_draft(
            user_id=current_user.id,
            target_type="new_topic",
            target_id="",
        )
        await self.session.commit()
        return await self.get_topic(topic.id, current_user=current_user)

    def can_create_topic_in_board(self, board: Board, current_user: User | None) -> bool:
        if board.slug in ADMIN_ONLY_TOPIC_BOARD_SLUGS:
            return current_user is not None and is_admin(current_user)
        return current_user is None or current_user.status == "active"

    async def get_topic(self, topic_id: str, *, current_user: User | None = None) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
                selectinload(Topic.posts),
                selectinload(Topic.poll).selectinload(Poll.options),
            )
            .where(Topic.id == topic_id)
        )
        if topic and topic.merged_into_topic_id:
            target_topic = await self.session.scalar(
                select(Topic)
                .options(selectinload(Topic.board))
                .where(Topic.id == topic.merged_into_topic_id)
            )
            if target_topic and await self._can_access_board(target_topic.board, current_user):
                raise ConflictError(
                    "topic_merged",
                    "Topic has been merged into another topic",
                    {"target_topic_id": topic.merged_into_topic_id},
                )
        if (
            not topic
            or topic.deleted_at is not None
            or not await self._can_access_topic(topic, current_user)
        ):
            raise NotFoundError("topic_not_found", "Topic not found")
        await self._decorate_topics_for_user([topic], current_user)
        return topic

    async def list_posts(
        self,
        topic_id: str,
        *,
        current_user: User | None = None,
        sort: PostSort = "chronological",
    ) -> list[Post]:
        topic = await self.get_topic(topic_id, current_user=current_user)
        if topic.visibility == "private_message" and current_user is not None:
            await self._mark_private_message_read(topic, current_user)
        statement = (
            select(Post)
            .options(selectinload(Post.author), selectinload(Post.topic))
            .where(Post.topic_id == topic_id)
            .order_by(Post.post_number)
        )
        if current_user is not None:
            statement = statement.where(self._visible_author_condition(current_user, Post.user_id))
        result = await self.session.scalars(statement)
        posts = list(result)
        await self._decorate_posts_for_user(posts, current_user)
        if sort == "qa":
            posts = self._sort_posts_for_qa(posts, topic.accepted_answer_post_id)
        return posts

    async def set_topic_solution(
        self,
        topic_id: str,
        payload: TopicSolutionRequest,
        current_user: User,
    ) -> Topic:
        topic = await self.get_topic(topic_id, current_user=current_user)
        if not await self._can_manage_solution(topic, current_user):
            raise PermissionDeniedError(
                "solution_forbidden",
                "Topic author or moderator permission required",
            )

        if payload.post_id is None:
            previous_post_id = topic.accepted_answer_post_id
            topic.accepted_answer_post_id = None
            topic.solved_at = None
            topic.solved_by_id = None
            topic.answer_mode = False
            topic.updated_at = utcnow()
            self._add_audit_log(
                actor_id=current_user.id,
                action="topic_solution_cleared",
                target_type="topic",
                target_id=topic.id,
                board_id=topic.board_id,
                data={"previous_post_id": previous_post_id or ""},
            )
            await SearchIndexService(self.session).sync_topic(topic.id)
            await self.session.commit()
            return await self.get_topic(topic.id, current_user=current_user)

        post = await self.session.scalar(
            select(Post)
            .options(selectinload(Post.topic))
            .where(Post.id == payload.post_id, Post.topic_id == topic.id)
        )
        if not post or post.deleted_at is not None:
            raise NotFoundError("post_not_found", "Post not found")
        if post.post_number == 1:
            raise ValidationError("solution_must_be_reply", "Solution must be a reply post")

        previous_post_id = topic.accepted_answer_post_id
        topic.accepted_answer_post_id = post.id
        topic.solved_at = utcnow()
        topic.solved_by_id = current_user.id
        topic.answer_mode = True
        topic.updated_at = utcnow()
        self._add_audit_log(
            actor_id=current_user.id,
            action="topic_solution_marked",
            target_type="topic",
            target_id=topic.id,
            board_id=topic.board_id,
            data={
                "previous_post_id": previous_post_id or "",
                "accepted_answer_post_id": post.id,
                "post_number": post.post_number,
            },
        )
        await SearchIndexService(self.session).sync_topic(topic.id)
        await self.session.commit()
        return await self.get_topic(topic.id, current_user=current_user)

    async def get_topic_poll(
        self,
        topic_id: str,
        *,
        current_user: User | None = None,
    ) -> Poll:
        await self.get_topic(topic_id, current_user=current_user)
        poll = await self._get_poll_for_topic(topic_id)
        await self._decorate_poll_for_user(poll, current_user)
        return poll

    async def vote_topic_poll(
        self,
        topic_id: str,
        payload: PollVoteRequest,
        current_user: User,
    ) -> Poll:
        await self.get_topic(topic_id, current_user=current_user)
        poll = await self._get_poll_for_topic(topic_id)
        if poll.closes_at is not None:
            closes_at = (
                poll.closes_at if poll.closes_at.tzinfo else poll.closes_at.replace(tzinfo=UTC)
            )
            if closes_at <= utcnow():
                raise ValidationError("poll_closed", "Poll is closed")
        option_ids = list(dict.fromkeys(payload.option_ids))
        if not option_ids:
            raise ValidationError("poll_option_required", "At least one option is required")
        if not poll.multiple_choice and len(option_ids) != 1:
            raise ValidationError("poll_single_choice_required", "Poll requires exactly one option")
        valid_option_ids = {option.id for option in poll.options}
        if any(option_id not in valid_option_ids for option_id in option_ids):
            raise NotFoundError("poll_option_not_found", "Poll option not found")

        existing_votes = list(
            await self.session.scalars(
                select(PollVote).where(
                    PollVote.poll_id == poll.id,
                    PollVote.user_id == current_user.id,
                )
            )
        )
        existing_option_ids = {vote.option_id for vote in existing_votes}
        next_option_ids = set(option_ids)
        for vote in existing_votes:
            if vote.option_id not in next_option_ids:
                await self.session.delete(vote)
        for option_id in next_option_ids - existing_option_ids:
            self.session.add(
                PollVote(poll_id=poll.id, option_id=option_id, user_id=current_user.id)
            )
        await self.session.flush()
        await self._recompute_poll_counts(poll)
        await self.session.commit()
        return await self.get_topic_poll(topic_id, current_user=current_user)

    async def update_topic_lifecycle(
        self,
        topic_id: str,
        payload: TopicLifecycleRequest,
        current_user: User,
    ) -> Topic:
        topic = await self._get_topic_for_lifecycle(topic_id)
        await self._require_can_moderate_board(current_user, topic.board_id)
        if payload.status is None and payload.pinned is None:
            raise ValidationError(
                "topic_lifecycle_noop",
                "At least one lifecycle field is required",
            )

        if payload.status is not None and topic.status != payload.status:
            previous_status = topic.status
            topic.status = payload.status
            topic.updated_at = utcnow()
            self._add_audit_log(
                actor_id=current_user.id,
                action="topic_status_changed",
                target_type="topic",
                target_id=topic.id,
                board_id=topic.board_id,
                data={
                    "from_status": previous_status,
                    "to_status": payload.status,
                    "note": payload.note or "",
                },
            )

        if payload.pinned is not None and topic.pinned != payload.pinned:
            previous_pinned = topic.pinned
            topic.pinned = payload.pinned
            topic.updated_at = utcnow()
            self._add_audit_log(
                actor_id=current_user.id,
                action="topic_pinned_changed",
                target_type="topic",
                target_id=topic.id,
                board_id=topic.board_id,
                data={
                    "from_pinned": previous_pinned,
                    "to_pinned": payload.pinned,
                    "note": payload.note or "",
                },
            )

        await SearchIndexService(self.session).sync_topic(topic.id)
        await self.session.commit()
        return await self.get_topic(topic.id, current_user=current_user)

    async def move_topic(
        self,
        topic_id: str,
        payload: TopicMoveRequest,
        current_user: User,
    ) -> Topic:
        topic = await self._get_topic_for_lifecycle(topic_id)
        target_board = await self._resolve_lifecycle_board(payload.board_id, payload.board_slug)
        await self._require_can_moderate_board(current_user, topic.board_id)
        await self._require_can_moderate_board(current_user, target_board.id)
        if topic.board_id == target_board.id:
            raise ValidationError("topic_already_in_board", "Topic is already in the target board")

        source_board = topic.board
        moved_post_count = await self._count_topic_posts(topic.id)
        previous_board_id = topic.board_id
        previous_board_slug = source_board.slug
        topic.board_id = target_board.id
        topic.board = target_board
        if await self.session.scalar(
            select(Topic.id).where(
                Topic.board_id == target_board.id,
                Topic.slug == topic.slug,
                Topic.id != topic.id,
            )
        ):
            topic.slug = await self._unique_topic_slug(target_board.id, topic.title)
        topic.updated_at = utcnow()
        source_board.topic_count = max(source_board.topic_count - 1, 0)
        source_board.post_count = max(source_board.post_count - moved_post_count, 0)
        target_board.topic_count += 1
        target_board.post_count += moved_post_count
        await self._update_topic_related_board(topic.id, target_board.id)
        await SearchIndexService(self.session).sync_topic(topic.id)
        self._add_audit_log(
            actor_id=current_user.id,
            action="topic_moved",
            target_type="topic",
            target_id=topic.id,
            board_id=target_board.id,
            data={
                "from_board_id": previous_board_id,
                "from_board_slug": previous_board_slug,
                "to_board_id": target_board.id,
                "to_board_slug": target_board.slug,
                "moved_post_count": moved_post_count,
                "note": payload.note or "",
            },
        )
        await self.session.commit()
        return await self.get_topic(topic.id, current_user=current_user)

    async def split_topic(
        self,
        topic_id: str,
        payload: TopicSplitRequest,
        current_user: User,
    ) -> tuple[Topic, Topic, int]:
        source = await self._get_topic_for_lifecycle(topic_id)
        target_board = (
            await self._resolve_lifecycle_board(payload.board_id, payload.board_slug)
            if payload.board_id or payload.board_slug
            else source.board
        )
        await self._require_can_moderate_board(current_user, source.board_id)
        await self._require_can_moderate_board(current_user, target_board.id)
        post_ids = list(dict.fromkeys(payload.post_ids))
        posts = await self._topic_posts(source.id)
        selected_posts = [post for post in posts if post.id in post_ids]
        selected_ids = {post.id for post in selected_posts}
        if len(selected_posts) != len(post_ids):
            raise NotFoundError("post_not_found", "Post not found")
        if any(post.post_number == 1 for post in selected_posts):
            raise ValidationError("cannot_split_first_post", "First post cannot be split")
        if any(post.deleted_at is not None for post in selected_posts):
            raise NotFoundError("post_not_found", "Post not found")

        selected_posts.sort(key=lambda post: post.post_number)
        new_topic = Topic(
            board_id=target_board.id,
            user_id=selected_posts[0].user_id,
            title=payload.title.strip(),
            slug=await self._unique_topic_slug(target_board.id, payload.title),
            status="open",
            pinned=False,
            featured=False,
            view_count=0,
            like_count=sum(post.like_count for post in selected_posts),
            hot_score=0.0,
            last_posted_at=selected_posts[-1].created_at,
            tags=await self._copy_topic_tags(source),
        )
        self.session.add(new_topic)
        await self.session.flush()

        for index, post in enumerate(selected_posts, start=1):
            post.topic_id = new_topic.id
            post.post_number = index
            if post.parent_id not in selected_ids:
                post.parent_id = None
            post.updated_at = utcnow()

        remaining_posts = [post for post in posts if post.id not in selected_ids]
        self._renumber_posts(remaining_posts)
        await self.session.flush()
        await self._recompute_topic_counters(source)
        await self._recompute_topic_counters(new_topic)
        if target_board.id != source.board_id:
            source.board.post_count = max(source.board.post_count - len(selected_posts), 0)
            target_board.post_count += len(selected_posts)
        target_board.topic_count += 1
        await self._move_post_related_rows(
            [post.id for post in selected_posts],
            topic_id=new_topic.id,
            board_id=target_board.id,
        )
        search_index = SearchIndexService(self.session)
        await search_index.sync_topic(source.id)
        await search_index.sync_topic(new_topic.id)
        self._add_audit_log(
            actor_id=current_user.id,
            action="topic_split",
            target_type="topic",
            target_id=source.id,
            board_id=source.board_id,
            data={
                "new_topic_id": new_topic.id,
                "new_topic_title": new_topic.title,
                "post_ids": [post.id for post in selected_posts],
                "moved_post_count": len(selected_posts),
                "target_board_id": target_board.id,
                "note": payload.note or "",
            },
        )
        await self.session.commit()
        return (
            await self.get_topic(source.id, current_user=current_user),
            await self.get_topic(new_topic.id, current_user=current_user),
            len(selected_posts),
        )

    async def merge_topic(
        self,
        source_topic_id: str,
        payload: TopicMergeRequest,
        current_user: User,
    ) -> tuple[Topic, int]:
        source = await self._get_topic_for_lifecycle(source_topic_id)
        target = await self._get_topic_for_lifecycle(payload.target_topic_id)
        if source.id == target.id:
            raise ValidationError("cannot_merge_same_topic", "Cannot merge a topic into itself")
        await self._require_can_moderate_board(current_user, source.board_id)
        await self._require_can_moderate_board(current_user, target.board_id)

        source_posts = await self._topic_posts(source.id)
        if not source_posts:
            raise ValidationError("source_topic_empty", "Source topic has no posts")

        target_posts = await self._topic_posts(target.id)
        next_number = max((post.post_number for post in target_posts), default=0) + 1
        source_post_ids = [post.id for post in source_posts]
        for offset, post in enumerate(source_posts):
            post.topic_id = target.id
            post.post_number = next_number + offset
            post.updated_at = utcnow()

        source.status = "hidden"
        source.deleted_at = utcnow()
        source.merged_into_topic_id = target.id
        source.updated_at = utcnow()
        self._merge_topic_tags(source, target)
        if source.board_id == target.board_id:
            source.board.topic_count = max(source.board.topic_count - 1, 0)
        else:
            source.board.topic_count = max(source.board.topic_count - 1, 0)
            source.board.post_count = max(source.board.post_count - len(source_posts), 0)
            target.board.post_count += len(source_posts)
        await self._move_post_related_rows(
            source_post_ids,
            topic_id=target.id,
            board_id=target.board_id,
            previous_topic_id=source.id,
        )
        await self._merge_topic_reads(source.id, target.id)
        await self._recompute_topic_counters(target)
        source.reply_count = 0
        source.hot_score = 0.0
        search_index = SearchIndexService(self.session)
        await search_index.remove_topic(source.id)
        await search_index.sync_topic(target.id)
        self._add_audit_log(
            actor_id=current_user.id,
            action="topic_merged",
            target_type="topic",
            target_id=source.id,
            board_id=source.board_id,
            data={
                "target_topic_id": target.id,
                "moved_post_count": len(source_posts),
                "note": payload.note or "",
            },
        )
        await self.session.commit()
        return await self.get_topic(target.id, current_user=current_user), len(source_posts)

    async def reply_to_topic(
        self,
        topic_id: str,
        payload: PostCreateRequest,
        current_user: User,
        request: Request | None = None,
        *,
        skip_spam_checks: bool = False,
    ) -> Post:
        topic = await self.get_topic(topic_id, current_user=current_user)
        if topic.status != "open":
            raise ValidationError("topic_closed", "This topic is closed")

        parent_post: Post | None = None
        if payload.parent_post_id:
            parent_post = await self.session.get(Post, payload.parent_post_id)
            if not parent_post or parent_post.topic_id != topic.id:
                raise NotFoundError("post_not_found", "Parent post not found")

        if not skip_spam_checks:
            await SpamPreventionService(self.session).enforce_reply(
                request,
                current_user=current_user,
                raw_md=payload.raw_md,
            )
        try:
            filtered = await self._moderate_or_queue_content(
                {"raw_md": payload.raw_md},
                current_user=current_user,
                reviewable_type="queued_post",
                board=topic.board,
                topic=topic,
                data={
                    "raw_md": payload.raw_md,
                    "parent_post_id": payload.parent_post_id,
                    "topic_title": topic.title,
                    "topic_slug": topic.slug,
                },
            )
        except ValidationError as e:
            if e.code == "content_pending_review":
                from app.services.draft import DraftService

                await DraftService(self.session).delete_draft(
                    user_id=current_user.id,
                    target_type="topic",
                    target_id=topic_id,
                )
            raise e
        raw_md = filtered["raw_md"].strip()
        next_number = (
            await self.session.scalar(
                select(func.max(Post.post_number)).where(Post.topic_id == topic.id)
            )
            or 0
        ) + 1
        post = Post(
            topic_id=topic.id,
            user_id=current_user.id,
            parent_id=parent_post.id if parent_post else None,
            post_number=next_number,
            raw_md=raw_md,
            cooked_html=self._render_required_markdown(raw_md),
        )
        self.session.add(post)

        if parent_post:
            parent_post.reply_count += 1
        topic.reply_count += 1
        topic.last_posted_at = utcnow()
        topic.hot_score = calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
        topic.board.post_count += 1
        await self._upsert_read_state(topic.id, current_user.id, post_number=next_number)
        await self.session.flush()
        await UploadService(self.session).attach_uploads_to_post(
            raw_md,
            post=post,
            topic=topic,
            board=topic.board,
            current_user=current_user,
        )
        if topic.visibility == "private_message":
            await self._queue_private_message_reply_notifications(topic, post, current_user)
        else:
            await self._queue_reply_notifications(topic, post, current_user, parent_post)
            await SearchIndexService(self.session).sync_topic(topic.id)
            await GrowthService(self.session).award(
                current_user.id,
                "post_created",
                source_id=post.id,
                actor_id=current_user.id,
                note="回复主题奖励",
            )
            badge_service = BadgeTrustService(self.session)
            await badge_service.grant_badge(
                user_id=current_user.id,
                badge_slug="first-reply",
                source_type="post_created",
                source_id=post.id,
                actor_id=current_user.id,
                note="完成第一次公开回复",
                idempotency_key=f"badge:first-reply:{current_user.id}",
            )
            await badge_service.recompute_trust(
                current_user,
                source_type="post_created",
                source_id=post.id,
                actor_id=current_user.id,
                note="回复后重算信任等级",
            )
            await IntegrationService(self.session).enqueue_event(
                "post.created",
                {
                    "post_id": post.id,
                    "topic_id": topic.id,
                    "topic_slug": topic.slug,
                    "post_number": post.post_number,
                    "author_id": current_user.id,
                    "author_name": current_user.username,
                    "created_at": post.created_at.isoformat(),
                },
            )
        from app.services.draft import DraftService

        await DraftService(self.session).delete_draft(
            user_id=current_user.id,
            target_type="topic",
            target_id=topic_id,
        )
        await self.session.commit()
        return await self._get_post(post.id)

    async def update_post(
        self,
        post_id: str,
        payload: PostUpdateRequest,
        current_user: User,
        request: Request | None = None,
    ) -> Post:
        post = await self.session.scalar(
            select(Post)
            .options(
                selectinload(Post.author),
                selectinload(Post.topic).selectinload(Topic.board),
            )
            .where(Post.id == post_id)
        )
        if not post or post.deleted_at is not None or post.topic.deleted_at is not None:
            raise NotFoundError("post_not_found", "Post not found")

        if post.post_number != 1:
            raise ValidationError("reply_edit_not_allowed", "Replies cannot be edited")

        if not await self._can_edit_post(post, current_user):
            raise PermissionDeniedError("permission_denied", "Permission denied")

        await SpamPreventionService(self.session).enforce_reply(
            request,
            current_user=current_user,
            raw_md=payload.raw_md,
        )
        filtered = await self._moderate_or_queue_content(
            {"raw_md": payload.raw_md},
            current_user=current_user,
            reviewable_type="queued_edit",
            board=post.topic.board,
            topic=post.topic,
            post=post,
            data={
                "raw_md": payload.raw_md,
                "edit_reason": payload.edit_reason,
                "topic_title": post.topic.title,
                "topic_slug": post.topic.slug,
                "post_number": post.post_number,
            },
        )
        stripped = filtered["raw_md"].strip()
        revision = await self._create_post_revision(
            post,
            editor=current_user,
            reason=payload.edit_reason,
            next_raw_md=stripped,
        )
        post.raw_md = stripped
        post.cooked_html = self._render_required_markdown(stripped)
        post.updated_at = utcnow()
        self._add_audit_log(
            actor_id=current_user.id,
            action="post_edited",
            target_type="post",
            target_id=post.id,
            board_id=post.topic.board_id,
            data={
                "revision_id": revision.id,
                "version_number": revision.version_number,
                "post_number": post.post_number,
                "reason": revision.edit_reason or "",
            },
        )
        await UploadService(self.session).attach_uploads_to_post(
            stripped,
            post=post,
            topic=post.topic,
            board=post.topic.board,
            current_user=current_user,
        )
        await SearchIndexService(self.session).sync_topic(post.topic_id)
        await self.session.commit()
        return await self._get_post(post.id)

    async def list_post_revisions(
        self,
        post_id: str,
        current_user: User,
        *,
        limit: int = 50,
    ) -> list[PostRevision]:
        post = await self._get_post_for_revision_access(post_id, current_user)
        revisions = await self.session.scalars(
            select(PostRevision)
            .options(selectinload(PostRevision.editor))
            .where(PostRevision.post_id == post.id)
            .order_by(desc(PostRevision.version_number))
            .limit(limit)
        )
        return list(revisions)

    async def get_post_revision(
        self,
        post_id: str,
        revision_id: str,
        current_user: User,
    ) -> PostRevision:
        post = await self._get_post_for_revision_access(post_id, current_user)
        revision = await self.session.scalar(
            select(PostRevision)
            .options(selectinload(PostRevision.editor))
            .where(PostRevision.id == revision_id, PostRevision.post_id == post.id)
        )
        if not revision:
            raise NotFoundError("post_revision_not_found", "Post revision not found")
        return revision

    async def restore_post_revision(
        self,
        post_id: str,
        revision_id: str,
        payload: PostRevisionRestoreRequest,
        current_user: User,
    ) -> Post:
        post = await self._get_post_for_revision_access(
            post_id,
            current_user,
            require_moderator=True,
        )
        revision = await self.session.scalar(
            select(PostRevision)
            .options(selectinload(PostRevision.editor))
            .where(PostRevision.id == revision_id, PostRevision.post_id == post.id)
        )
        if not revision:
            raise NotFoundError("post_revision_not_found", "Post revision not found")

        restore_reason = payload.reason or f"Restore post to revision {revision.version_number}"
        new_revision = await self._create_post_revision(
            post,
            editor=current_user,
            reason=restore_reason,
            next_raw_md=revision.raw_md,
            restored_from_revision_id=revision.id,
        )
        post.raw_md = revision.raw_md
        post.cooked_html = revision.cooked_html
        post.updated_at = utcnow()
        self._add_audit_log(
            actor_id=current_user.id,
            action="post_revision_restored",
            target_type="post",
            target_id=post.id,
            board_id=post.topic.board_id,
            data={
                "revision_id": revision.id,
                "created_revision_id": new_revision.id,
                "from_version_number": new_revision.version_number,
                "to_version_number": revision.version_number,
                "reason": restore_reason,
            },
        )
        await UploadService(self.session).attach_uploads_to_post(
            revision.raw_md,
            post=post,
            topic=post.topic,
            board=post.topic.board,
            current_user=current_user,
        )
        await SearchIndexService(self.session).sync_topic(post.topic_id)
        await self.session.commit()
        return await self._get_post(post.id)

    async def delete_post(self, post_id: str, current_user: User) -> Post:
        post = await self.session.scalar(
            select(Post)
            .options(
                selectinload(Post.author),
                selectinload(Post.topic).selectinload(Topic.board),
            )
            .where(Post.id == post_id)
        )
        if not post or post.deleted_at is not None or post.topic.deleted_at is not None:
            raise NotFoundError("post_not_found", "Post not found")

        if post.post_number == 1:
            raise ValidationError(
                "topic_post_delete_not_allowed",
                "Topic posts cannot be deleted here",
            )

        if not await self._can_delete_post(post, current_user):
            raise PermissionDeniedError("permission_denied", "Permission denied")

        post.deleted_at = utcnow()
        post.raw_md = ""
        post.cooked_html = ""
        post.updated_at = utcnow()
        await SearchIndexService(self.session).sync_topic(post.topic_id)
        await self.session.commit()
        return await self._get_post(post.id)

    async def list_my_board_invites(
        self,
        current_user: User,
    ) -> tuple[list[BoardInvitation], list[BoardInvitation], list[Board]]:
        received = list(
            await self.session.scalars(
                select(BoardInvitation)
                .options(
                    selectinload(BoardInvitation.board),
                    selectinload(BoardInvitation.inviter),
                    selectinload(BoardInvitation.invitee),
                )
                .where(
                    BoardInvitation.invitee_id == current_user.id,
                    BoardInvitation.status == "pending",
                )
                .order_by(desc(BoardInvitation.created_at))
            )
        )
        owned_boards = list(
            await self.session.scalars(
                select(Board)
                .where(Board.owner_id == current_user.id, Board.visibility != "public")
                .order_by(Board.name)
            )
        )
        board_ids = [board.id for board in owned_boards]
        managed: list[BoardInvitation] = []
        if board_ids:
            managed = list(
                await self.session.scalars(
                    select(BoardInvitation)
                    .options(
                        selectinload(BoardInvitation.board),
                        selectinload(BoardInvitation.inviter),
                        selectinload(BoardInvitation.invitee),
                    )
                    .where(BoardInvitation.board_id.in_(board_ids))
                    .order_by(desc(BoardInvitation.created_at))
                    .limit(100)
                )
            )
        return received, managed, owned_boards

    async def create_board_invite(
        self,
        payload: BoardInviteCreateRequest,
        current_user: User,
    ) -> BoardInvitation:
        board = await self.session.scalar(select(Board).where(Board.id == payload.board_id))
        if not board or board.visibility == "public":
            raise NotFoundError("board_not_found", "Board not found")
        if board.owner_id != current_user.id:
            raise PermissionDeniedError("board_invite_forbidden", "Board owner permission required")

        invitee = await self.session.scalar(select(User).where(User.username == payload.username))
        if not invitee:
            raise NotFoundError("user_not_found", "User not found")
        if invitee.id == current_user.id:
            raise ValidationError("cannot_invite_self", "Cannot invite yourself")

        existing_member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id == invitee.id,
            )
        )
        if existing_member:
            raise ValidationError("board_member_exists", "User is already a board member")

        existing_invite = await self.session.scalar(
            select(BoardInvitation)
            .options(
                selectinload(BoardInvitation.board),
                selectinload(BoardInvitation.inviter),
                selectinload(BoardInvitation.invitee),
            )
            .where(
                BoardInvitation.board_id == board.id,
                BoardInvitation.invitee_id == invitee.id,
                BoardInvitation.status == "pending",
            )
        )
        if existing_invite:
            return existing_invite

        invitation = BoardInvitation(
            board_id=board.id,
            inviter_id=current_user.id,
            invitee_id=invitee.id,
            status="pending",
        )
        self.session.add(invitation)
        await self.session.flush()
        await self._add_notification(
            user_id=invitee.id,
            kind="board_invite",
            topic_id=None,
            post_id=None,
            actor_id=current_user.id,
            data={
                "board_id": board.id,
                "board_slug": board.slug,
                "board_name": board.name,
                "invite_id": invitation.id,
            },
        )
        await self.session.commit()
        return await self._get_board_invitation(invitation.id)

    async def accept_board_invite(self, invite_id: str, current_user: User) -> BoardInvitation:
        invitation = await self._get_board_invitation(invite_id)
        self._require_invitee(invitation, current_user)
        self._require_pending_invite(invitation)

        existing_member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == invitation.board_id,
                BoardMember.user_id == current_user.id,
            )
        )
        if not existing_member:
            self.session.add(
                BoardMember(
                    board_id=invitation.board_id,
                    user_id=current_user.id,
                    role="follower",
                    notification_level=invitation.board.default_notification_level,
                )
            )
            invitation.board.follower_count += 1
        invitation.status = "accepted"
        invitation.responded_at = utcnow()
        growth = GrowthService(self.session)
        await growth.award(
            current_user.id,
            "invite_accepted_invitee",
            source_id=invitation.id,
            actor_id=current_user.id,
            note="接受版块邀请奖励",
        )
        badge_service = BadgeTrustService(self.session)
        await badge_service.recompute_trust(
            current_user,
            source_type="invite_accepted",
            source_id=invitation.id,
            actor_id=current_user.id,
            note="接受邀请后重算信任等级",
        )
        if invitation.inviter_id != current_user.id:
            await growth.award(
                invitation.inviter_id,
                "invite_accepted_inviter",
                source_id=invitation.id,
                actor_id=current_user.id,
                note="邀请被接受奖励",
            )
            inviter = await self.session.get(User, invitation.inviter_id)
            if inviter is not None:
                await badge_service.recompute_trust(
                    inviter,
                    source_type="invite_accepted",
                    source_id=invitation.id,
                    actor_id=current_user.id,
                    note="邀请被接受后重算信任等级",
                )
        await self.session.commit()
        return await self._get_board_invitation(invitation.id)

    async def decline_board_invite(self, invite_id: str, current_user: User) -> BoardInvitation:
        invitation = await self._get_board_invitation(invite_id)
        self._require_invitee(invitation, current_user)
        self._require_pending_invite(invitation)
        invitation.status = "declined"
        invitation.responded_at = utcnow()
        await self.session.commit()
        return await self._get_board_invitation(invitation.id)

    async def revoke_board_invite(self, invite_id: str, current_user: User) -> BoardInvitation:
        invitation = await self._get_board_invitation(invite_id)
        if invitation.board.owner_id != current_user.id:
            raise PermissionDeniedError("board_invite_forbidden", "Board owner permission required")
        self._require_pending_invite(invitation)
        invitation.status = "revoked"
        invitation.revoked_by_id = current_user.id
        invitation.responded_at = utcnow()
        await self.session.commit()
        return await self._get_board_invitation(invitation.id)

    def _board_visible_condition(self, current_user: User | None):
        if current_user is None:
            return Board.visibility == "public"
        member_exists = (
            select(BoardMember.id)
            .where(
                BoardMember.board_id == Board.id,
                BoardMember.user_id == current_user.id,
            )
            .exists()
        )
        return or_(Board.visibility == "public", member_exists)

    def _visible_author_condition(self, current_user: User, author_id_column=Topic.user_id):
        hidden_author_exists = (
            select(UserRelationship.id)
            .where(
                UserRelationship.actor_user_id == current_user.id,
                UserRelationship.target_user_id == author_id_column,
                UserRelationship.relationship_type.in_(("ignore", "block")),
            )
            .exists()
        )
        return not_(hidden_author_exists)

    async def _author_visible_to_user(self, author_id: str, current_user: User | None) -> bool:
        if current_user is None or author_id == current_user.id:
            return True
        hidden_relationship_id = await self.session.scalar(
            select(UserRelationship.id).where(
                UserRelationship.actor_user_id == current_user.id,
                UserRelationship.target_user_id == author_id,
                UserRelationship.relationship_type.in_(("ignore", "block")),
            )
        )
        return hidden_relationship_id is None

    async def _can_access_topic(self, topic: Topic, current_user: User | None) -> bool:
        if topic.visibility == "private_message":
            if current_user is None:
                return False
            return await self._is_private_message_participant(topic.id, current_user.id)
        if not await self._author_visible_to_user(topic.user_id, current_user):
            return False
        return await self._can_access_board(topic.board, current_user)

    async def _is_private_message_participant(self, topic_id: str, user_id: str) -> bool:
        participant_id = await self.session.scalar(
            select(PrivateMessageParticipant.id).where(
                PrivateMessageParticipant.topic_id == topic_id,
                PrivateMessageParticipant.user_id == user_id,
            )
        )
        return participant_id is not None

    async def _mark_private_message_read(self, topic: Topic, current_user: User) -> None:
        participant = await self.session.scalar(
            select(PrivateMessageParticipant).where(
                PrivateMessageParticipant.topic_id == topic.id,
                PrivateMessageParticipant.user_id == current_user.id,
            )
        )
        if participant is None:
            return
        participant.last_read_post_number = topic.reply_count + 1
        participant.last_read_at = utcnow()
        await self.session.commit()

    async def _can_access_board(self, board: Board, current_user: User | None) -> bool:
        if board.visibility == "public":
            return True
        if current_user is None:
            return False
        if board.owner_id == current_user.id:
            return True
        member = await self.session.scalar(
            select(BoardMember.id).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id == current_user.id,
            )
        )
        return member is not None

    async def _require_can_manage_board_settings(self, current_user: User, board: Board) -> None:
        if is_admin(current_user) or board.owner_id == current_user.id:
            return
        raise PermissionDeniedError(
            "board_settings_forbidden",
            "Board owner or admin permission required",
        )

    async def _resolve_parent_board(
        self,
        *,
        parent_board_id: str | None,
        parent_board_slug: str | None,
        current_user: User,
    ) -> Board | None:
        if not parent_board_id and not parent_board_slug:
            return None
        statement = select(Board).options(selectinload(Board.parent_board))
        if parent_board_id:
            statement = statement.where(Board.id == parent_board_id)
        else:
            statement = statement.where(Board.slug == parent_board_slug)
        parent = await self.session.scalar(statement)
        if not parent or not await self._can_access_board(parent, current_user):
            raise NotFoundError("board_not_found", "Board not found")
        return parent

    async def _would_create_board_parent_cycle(
        self,
        board_id: str,
        proposed_parent_id: str,
    ) -> bool:
        cursor_id: str | None = proposed_parent_id
        visited: set[str] = set()
        while cursor_id:
            if cursor_id == board_id:
                return True
            if cursor_id in visited:
                return True
            visited.add(cursor_id)
            cursor_id = await self.session.scalar(
                select(Board.parent_board_id).where(Board.id == cursor_id)
            )
        return False

    def _normalized_unique_tags(self, tag_names: Iterable[str]) -> list[str]:
        normalized_names: list[str] = []
        for tag_name in tag_names:
            normalized = normalize_tag_name(tag_name)
            if normalized and normalized not in normalized_names:
                normalized_names.append(normalized)
        return normalized_names

    def _validate_board_tag_policy(
        self,
        required_tags: list[str],
        allowed_tags: list[str],
    ) -> None:
        if not allowed_tags:
            return
        missing_from_allowed = [tag for tag in required_tags if tag not in allowed_tags]
        if missing_from_allowed:
            raise ValidationError(
                "required_tags_not_allowed",
                "Required tags must be included in allowed tags.",
                {"tags": missing_from_allowed},
            )

    def _validate_board_topic_tags(self, board: Board, normalized_tags: list[str]) -> None:
        required_tags = list(board.required_tags or [])
        allowed_tags = list(board.allowed_tags or [])
        missing_tags = [tag for tag in required_tags if tag not in normalized_tags]
        if missing_tags:
            raise ValidationError(
                "required_tags_missing",
                "Topic is missing required board tags.",
                {"required_tags": required_tags, "missing_tags": missing_tags},
            )
        if allowed_tags:
            disallowed_tags = [tag for tag in normalized_tags if tag not in allowed_tags]
            if disallowed_tags:
                raise ValidationError(
                    "tag_not_allowed",
                    "Topic includes tags that are not allowed in this board.",
                    {"allowed_tags": allowed_tags, "disallowed_tags": disallowed_tags},
                )

    def _clean_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    async def _get_board_invitation(self, invite_id: str) -> BoardInvitation:
        invitation = await self.session.scalar(
            select(BoardInvitation)
            .options(
                selectinload(BoardInvitation.board),
                selectinload(BoardInvitation.inviter),
                selectinload(BoardInvitation.invitee),
            )
            .where(BoardInvitation.id == invite_id)
        )
        if not invitation:
            raise NotFoundError("board_invite_not_found", "Board invite not found")
        return invitation

    async def _moderate_or_queue_content(
        self,
        fields: Mapping[str, str],
        *,
        current_user: User,
        reviewable_type: str,
        board: Board,
        topic: Topic | None = None,
        post: Post | None = None,
        data: dict[str, object] | None = None,
    ) -> dict[str, str]:
        result = moderate_text_fields(fields)
        if result.blocked_fields:
            raise ValidationError(
                "content_policy_violation",
                "Content violates community safety rules; please edit and retry",
                {
                    "action": "blocked",
                    "fields": list(result.blocked_fields),
                },
            )
        if result.review_fields:
            from app.services.moderation import ModerationService

            reviewable = await ModerationService(self.session).create_content_reviewable(
                current_user=current_user,
                reviewable_type=reviewable_type,
                board=board,
                topic=topic,
                post=post,
                sanitized_fields=result.sanitized_fields,
                matched_fields=result.review_fields,
                data=data or {},
            )
            await self.session.commit()
            raise ValidationError(
                "content_pending_review",
                "Content was queued for moderator review",
                {
                    "action": "review",
                    "reviewable_id": reviewable.id,
                    "fields": list(result.review_fields),
                    "appeal_available": True,
                },
            )
        return result.sanitized_fields

    def _require_invitee(self, invitation: BoardInvitation, current_user: User) -> None:
        if invitation.invitee_id != current_user.id:
            raise PermissionDeniedError(
                "board_invite_forbidden",
                "Board invite permission required",
            )

    def _require_pending_invite(self, invitation: BoardInvitation) -> None:
        if invitation.status != "pending":
            raise ValidationError("board_invite_not_pending", "Board invite is not pending")

    async def _can_manage_solution(self, topic: Topic, current_user: User) -> bool:
        if topic.user_id == current_user.id:
            return True
        return await self._can_moderate_board(current_user, topic.board_id)

    async def _create_poll(self, topic: Topic, payload) -> Poll:
        closes_at = self._normalize_poll_closes_at(payload.closes_at)
        option_labels = self._normalized_poll_options(payload.options)
        poll = Poll(
            topic=topic,
            question=payload.question.strip(),
            multiple_choice=payload.multiple_choice,
            closes_at=closes_at,
        )
        self.session.add(poll)
        await self.session.flush()
        for index, label in enumerate(option_labels, start=1):
            self.session.add(PollOption(poll_id=poll.id, label=label, position=index))
        return poll

    def _normalize_poll_closes_at(self, closes_at: datetime | None) -> datetime | None:
        if closes_at is None:
            return None
        normalized = closes_at if closes_at.tzinfo else closes_at.replace(tzinfo=UTC)
        if normalized <= utcnow():
            raise ValidationError("poll_closes_at_past", "Poll close time must be in the future")
        return normalized

    def _normalized_poll_options(self, options: Iterable[str]) -> list[str]:
        labels: list[str] = []
        for option in options:
            label = option.strip()
            if label and label not in labels:
                labels.append(label)
        if len(labels) < 2:
            raise ValidationError("poll_options_required", "Poll requires at least two options")
        return labels

    async def _get_poll_for_topic(self, topic_id: str) -> Poll:
        poll = await self.session.scalar(
            select(Poll).options(selectinload(Poll.options)).where(Poll.topic_id == topic_id)
        )
        if poll is None:
            raise NotFoundError("poll_not_found", "Poll not found")
        return poll

    async def _decorate_topics_for_user(
        self,
        topics: list[Topic],
        current_user: User | None,
    ) -> None:
        if not topics:
            return
        for topic in topics:
            if topic.poll:
                await self._decorate_poll_for_user(topic.poll, current_user)
            topic.liked_by_me = False
            topic.bookmarked_by_me = False
            topic.my_vote = 0

        from app.models.interaction import Bookmark, Reaction, Vote

        topic_ids = [topic.id for topic in topics]
        bookmark_counts = {
            target_id: int(count)
            for target_id, count in (
                await self.session.execute(
                    select(Bookmark.target_id, func.count(Bookmark.id))
                    .where(
                        Bookmark.target_type == "topic",
                        Bookmark.target_id.in_(topic_ids),
                    )
                    .group_by(Bookmark.target_id)
                )
            ).all()
        }
        for topic in topics:
            topic.bookmark_count = bookmark_counts.get(topic.id, 0)

        if current_user is None:
            return

        liked_topic_ids = set(
            await self.session.scalars(
                select(Reaction.target_id).where(
                    Reaction.target_type == "topic",
                    Reaction.target_id.in_(topic_ids),
                    Reaction.user_id == current_user.id,
                    Reaction.type == "like",
                )
            )
        )
        bookmarked_topic_ids = set(
            await self.session.scalars(
                select(Bookmark.target_id).where(
                    Bookmark.target_type == "topic",
                    Bookmark.target_id.in_(topic_ids),
                    Bookmark.user_id == current_user.id,
                )
            )
        )
        votes = list(
            await self.session.scalars(
                select(Vote).where(
                    Vote.target_type == "topic",
                    Vote.target_id.in_(topic_ids),
                    Vote.user_id == current_user.id,
                )
            )
        )
        vote_by_topic = {vote.target_id: vote.value for vote in votes}
        for topic in topics:
            topic.liked_by_me = topic.id in liked_topic_ids
            topic.bookmarked_by_me = topic.id in bookmarked_topic_ids
            topic.my_vote = vote_by_topic.get(topic.id, 0)

    async def _decorate_posts_for_user(
        self,
        posts: list[Post],
        current_user: User | None,
    ) -> None:
        if not posts:
            return
        accepted_ids = {
            post.topic.accepted_answer_post_id
            for post in posts
            if getattr(post, "topic", None) is not None and post.topic.accepted_answer_post_id
        }
        for post in posts:
            post.accepted_answer = post.id in accepted_ids
            post.liked_by_me = False
            post.my_vote = 0
        if current_user is None:
            return
        from app.models.interaction import Reaction, Vote

        post_ids = [post.id for post in posts]
        liked_post_ids = set(
            await self.session.scalars(
                select(Reaction.target_id).where(
                    Reaction.target_type == "post",
                    Reaction.target_id.in_(post_ids),
                    Reaction.user_id == current_user.id,
                    Reaction.type == "like",
                )
            )
        )
        votes = list(
            await self.session.scalars(
                select(Vote).where(
                    Vote.target_type == "post",
                    Vote.target_id.in_(post_ids),
                    Vote.user_id == current_user.id,
                )
            )
        )
        vote_by_post = {vote.target_id: vote.value for vote in votes}
        for post in posts:
            post.liked_by_me = post.id in liked_post_ids
            post.my_vote = vote_by_post.get(post.id, 0)

    async def _decorate_poll_for_user(self, poll: Poll, current_user: User | None) -> None:
        if current_user is None:
            poll.selected_option_ids = []
            return
        selected_option_ids = list(
            await self.session.scalars(
                select(PollVote.option_id).where(
                    PollVote.poll_id == poll.id,
                    PollVote.user_id == current_user.id,
                )
            )
        )
        poll.selected_option_ids = selected_option_ids

    def _sort_posts_for_qa(
        self, posts: list[Post], accepted_answer_post_id: str | None
    ) -> list[Post]:
        first_posts = [post for post in posts if post.post_number == 1]
        replies = [post for post in posts if post.post_number != 1]
        replies.sort(
            key=lambda post: (
                post.id != accepted_answer_post_id,
                -post.vote_score,
                post.post_number,
            )
        )
        return first_posts + replies

    async def _recompute_poll_counts(self, poll: Poll) -> None:
        option_counts = {
            option_id: count
            for option_id, count in (
                await self.session.execute(
                    select(PollVote.option_id, func.count(PollVote.id))
                    .where(PollVote.poll_id == poll.id)
                    .group_by(PollVote.option_id)
                )
            ).all()
        }
        for option in poll.options:
            option.vote_count = int(option_counts.get(option.id, 0))
        poll.total_votes = int(
            await self.session.scalar(
                select(func.count(func.distinct(PollVote.user_id))).where(
                    PollVote.poll_id == poll.id
                )
            )
            or 0
        )
        poll.updated_at = utcnow()

    async def _get_topic_for_lifecycle(self, topic_id: str) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
                selectinload(Topic.posts),
            )
            .where(Topic.id == topic_id)
        )
        if not topic or topic.deleted_at is not None or topic.merged_into_topic_id:
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    async def _resolve_lifecycle_board(
        self,
        board_id: str | None,
        board_slug: str | None,
    ) -> Board:
        if board_id:
            board = await self.session.scalar(select(Board).where(Board.id == board_id))
        elif board_slug:
            board = await self.session.scalar(select(Board).where(Board.slug == board_slug))
        else:
            raise ValidationError("target_board_required", "Target board is required")
        if not board:
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def _require_can_moderate_board(self, current_user: User, board_id: str) -> None:
        if not await self._can_moderate_board(current_user, board_id):
            raise PermissionDeniedError(
                "moderation_forbidden",
                "Moderation permission required",
            )

    async def _can_moderate_board(self, current_user: User, board_id: str) -> bool:
        if is_global_moderator(current_user):
            return True
        member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == board_id,
                BoardMember.user_id == current_user.id,
                BoardMember.role.in_(BOARD_MODERATOR_ROLES),
            )
        )
        return member is not None

    async def _count_topic_posts(self, topic_id: str) -> int:
        return int(
            await self.session.scalar(select(func.count(Post.id)).where(Post.topic_id == topic_id))
            or 0
        )

    async def _topic_posts(self, topic_id: str) -> list[Post]:
        return list(
            await self.session.scalars(
                select(Post)
                .options(selectinload(Post.author))
                .where(Post.topic_id == topic_id)
                .order_by(Post.post_number, Post.created_at)
            )
        )

    def _renumber_posts(self, posts: list[Post]) -> None:
        for index, post in enumerate(sorted(posts, key=lambda item: item.post_number), start=1):
            post.post_number = index
            post.updated_at = utcnow()

    async def _recompute_topic_counters(self, topic: Topic) -> None:
        posts = await self._topic_posts(topic.id)
        visible_posts = [post for post in posts if post.deleted_at is None]
        topic.reply_count = max(len(visible_posts) - 1, 0)
        topic.like_count = sum(post.like_count for post in visible_posts)
        if visible_posts:
            topic.last_posted_at = max(post.created_at for post in visible_posts)
        topic.hot_score = calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
        topic.updated_at = utcnow()

    async def _copy_topic_tags(self, source: Topic) -> list[Tag]:
        tags: list[Tag] = []
        for tag in source.tags:
            tag.topic_count += 1
            tags.append(tag)
        return tags

    def _merge_topic_tags(self, source: Topic, target: Topic) -> None:
        target_tag_ids = {tag.id for tag in target.tags}
        for tag in source.tags:
            if tag.id in target_tag_ids:
                tag.topic_count = max(tag.topic_count - 1, 0)
                continue
            target.tags.append(tag)
            target_tag_ids.add(tag.id)

    async def _update_topic_related_board(self, topic_id: str, board_id: str) -> None:
        await self.session.execute(
            update(Upload).where(Upload.topic_id == topic_id).values(board_id=board_id)
        )

    async def _move_post_related_rows(
        self,
        post_ids: list[str],
        *,
        topic_id: str,
        board_id: str,
        previous_topic_id: str | None = None,
    ) -> None:
        if not post_ids:
            return
        await self.session.execute(
            update(Notification).where(Notification.post_id.in_(post_ids)).values(topic_id=topic_id)
        )
        if previous_topic_id:
            await self.session.execute(
                update(Notification)
                .where(Notification.topic_id == previous_topic_id)
                .values(topic_id=topic_id)
            )
        await self.session.execute(
            update(Upload)
            .where(Upload.post_id.in_(post_ids))
            .values(topic_id=topic_id, board_id=board_id)
        )
        await self.session.execute(
            update(PostRevision).where(PostRevision.post_id.in_(post_ids)).values(topic_id=topic_id)
        )

    async def _merge_topic_reads(self, source_topic_id: str, target_topic_id: str) -> None:
        source_reads = list(
            await self.session.scalars(
                select(TopicRead).where(TopicRead.topic_id == source_topic_id)
            )
        )
        for source_read in source_reads:
            target_read = await self.session.scalar(
                select(TopicRead).where(
                    TopicRead.topic_id == target_topic_id,
                    TopicRead.user_id == source_read.user_id,
                )
            )
            if target_read:
                target_read.last_read_post_number = max(
                    target_read.last_read_post_number,
                    source_read.last_read_post_number,
                )
                if target_read.notification_level == "normal":
                    target_read.notification_level = source_read.notification_level
                await self.session.delete(source_read)
                continue
            source_read.topic_id = target_topic_id

    async def _get_post_for_revision_access(
        self,
        post_id: str,
        current_user: User,
        *,
        require_moderator: bool = False,
    ) -> Post:
        post = await self.session.scalar(
            select(Post)
            .options(
                selectinload(Post.author),
                selectinload(Post.topic).selectinload(Topic.board),
            )
            .where(Post.id == post_id)
        )
        if not post:
            raise NotFoundError("post_not_found", "Post not found")

        can_moderate = await self._can_moderate_post(post, current_user)
        if require_moderator:
            if not can_moderate:
                raise PermissionDeniedError(
                    "moderation_forbidden",
                    "Moderation permission required",
                )
        elif not can_moderate and post.user_id != current_user.id:
            raise PermissionDeniedError("permission_denied", "Permission denied")

        if post.topic.deleted_at is not None or post.deleted_at is not None:
            if not can_moderate:
                raise NotFoundError("post_not_found", "Post not found")

        if not can_moderate and post.user_id != current_user.id:
            if not await self._can_access_board(post.topic.board, current_user):
                raise NotFoundError("post_not_found", "Post not found")

        return post

    async def _can_moderate_post(self, post: Post, current_user: User) -> bool:
        if is_global_moderator(current_user):
            return True
        member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == post.topic.board_id,
                BoardMember.user_id == current_user.id,
                BoardMember.role.in_(BOARD_MODERATOR_ROLES),
            )
        )
        if member:
            return True
        return post.topic.board.owner_id == current_user.id

    async def _can_edit_post(self, post: Post, current_user: User) -> bool:
        if post.user_id == current_user.id:
            return True
        return await self._can_moderate_post(post, current_user)

    async def _can_delete_post(self, post: Post, current_user: User) -> bool:
        if post.user_id == current_user.id:
            return True
        return await self._can_edit_post(post, current_user)

    async def _get_post(self, post_id: str) -> Post:
        post = await self.session.scalar(
            select(Post).options(selectinload(Post.author)).where(Post.id == post_id)
        )
        if not post:
            raise NotFoundError("post_not_found", "Post not found")
        return post

    async def _create_post_revision(
        self,
        post: Post,
        *,
        editor: User,
        reason: str | None,
        next_raw_md: str,
        restored_from_revision_id: str | None = None,
    ) -> PostRevision:
        edit_reason = reason.strip() if reason and reason.strip() else None
        version_number = await self._next_post_revision_number(post.id)
        revision = PostRevision(
            post_id=post.id,
            topic_id=post.topic_id,
            editor_id=editor.id,
            version_number=version_number,
            raw_md=post.raw_md,
            cooked_html=post.cooked_html,
            edit_reason=edit_reason,
            summary=self._build_revision_summary(
                previous_raw_md=post.raw_md,
                next_raw_md=next_raw_md,
                reason=edit_reason,
                restored_from_revision_id=restored_from_revision_id,
            ),
            restored_from_revision_id=restored_from_revision_id,
        )
        self.session.add(revision)
        await self.session.flush()
        return revision

    async def _next_post_revision_number(self, post_id: str) -> int:
        latest = await self.session.scalar(
            select(func.max(PostRevision.version_number)).where(PostRevision.post_id == post_id)
        )
        return int(latest or 0) + 1

    def _build_revision_summary(
        self,
        *,
        previous_raw_md: str,
        next_raw_md: str,
        reason: str | None,
        restored_from_revision_id: str | None,
    ) -> str:
        if reason:
            return reason[:500]
        if restored_from_revision_id:
            return "恢复历史版本"
        return f"内容长度 {len(previous_raw_md)} → {len(next_raw_md)}"

    async def _unique_topic_slug(self, board_id: str, title: str) -> str:
        base_slug = slugify(title, fallback_prefix="topic")[:180]
        slug = base_slug
        attempt = 1
        while await self.session.scalar(
            select(Topic.id).where(Topic.board_id == board_id, Topic.slug == slug)
        ):
            attempt += 1
            slug = f"{base_slug}-{attempt}"
        return slug

    async def _resolve_tags(self, tag_names: Iterable[str]) -> list[Tag]:
        normalized_names = []
        for tag_name in tag_names:
            normalized = normalize_tag_name(tag_name)
            if normalized and normalized not in normalized_names:
                normalized_names.append(normalized)

        tags: list[Tag] = []
        for name in normalized_names:
            slug = slugify(name, fallback_prefix="tag")[:64]
            tag = await self.session.scalar(
                select(Tag).where(or_(Tag.slug == slug, Tag.name == name))
            )
            if not tag:
                tag = Tag(name=name, slug=slug, topic_count=0)
                self.session.add(tag)
                await self.session.flush()
            tag.topic_count += 1
            tags.append(tag)
        return tags

    async def _upsert_read_state(self, topic_id: str, user_id: str, *, post_number: int) -> None:
        read_state = await self.session.scalar(
            select(TopicRead).where(TopicRead.topic_id == topic_id, TopicRead.user_id == user_id)
        )
        if read_state:
            read_state.last_read_post_number = post_number
            # Only auto-upgrade to tracking if the user hasn't explicitly set a level
            if read_state.notification_level == "normal":
                read_state.notification_level = "tracking"
            return

        self.session.add(
            TopicRead(
                topic_id=topic_id,
                user_id=user_id,
                last_read_post_number=post_number,
                notification_level="tracking",
            )
        )

    async def get_topic_notification_level(
        self,
        topic_id: str,
        current_user: User,
    ) -> TopicNotificationLevelResponse:
        await self.get_topic(topic_id, current_user=current_user)
        read_state = await self.session.scalar(
            select(TopicRead).where(
                TopicRead.topic_id == topic_id,
                TopicRead.user_id == current_user.id,
            )
        )
        if read_state:
            return TopicNotificationLevelResponse(
                topic_id=topic_id,
                notification_level=read_state.notification_level,
                last_read_post_number=read_state.last_read_post_number,
            )
        return TopicNotificationLevelResponse(
            topic_id=topic_id,
            notification_level="normal",
            last_read_post_number=0,
        )

    async def set_topic_notification_level(
        self,
        topic_id: str,
        level: NotificationLevel,
        current_user: User,
    ) -> TopicNotificationLevelResponse:
        await self.get_topic(topic_id, current_user=current_user)
        read_state = await self.session.scalar(
            select(TopicRead).where(
                TopicRead.topic_id == topic_id,
                TopicRead.user_id == current_user.id,
            )
        )
        if read_state:
            read_state.notification_level = level
        else:
            read_state = TopicRead(
                topic_id=topic_id,
                user_id=current_user.id,
                last_read_post_number=0,
                notification_level=level,
            )
            self.session.add(read_state)
        await self.session.commit()
        return TopicNotificationLevelResponse(
            topic_id=topic_id,
            notification_level=read_state.notification_level,
            last_read_post_number=read_state.last_read_post_number,
        )

    def _render_required_markdown(self, raw_md: str) -> str:
        stripped = raw_md.strip()
        if not stripped:
            raise ValidationError("empty_post", "Post content cannot be empty")
        return render_markdown(stripped)

    async def _queue_board_new_topic_notifications(
        self,
        board: Board,
        topic: Topic,
        first_post: Post,
        current_user: User,
    ) -> None:
        watchers = await self.session.scalars(
            select(BoardMember).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id != current_user.id,
                BoardMember.notification_level.in_(("watching", "tracking")),
            )
        )
        for watcher in watchers:
            await self._add_notification(
                user_id=watcher.user_id,
                kind="board_new_topic",
                topic_id=topic.id,
                post_id=first_post.id,
                actor_id=current_user.id,
                data={
                    "board_slug": board.slug,
                    "board_name": board.name,
                    "topic_title": topic.title,
                    "topic_slug": topic.slug,
                    "post_number": first_post.post_number,
                },
            )

    async def _queue_followed_user_new_topic_notifications(
        self,
        topic: Topic,
        first_post: Post,
        current_user: User,
    ) -> None:
        followers = await self.session.scalars(
            select(UserRelationship).where(
                UserRelationship.target_user_id == current_user.id,
                UserRelationship.actor_user_id != current_user.id,
                UserRelationship.relationship_type == "follow",
            )
        )
        for follower in followers:
            await self._add_notification(
                user_id=follower.actor_user_id,
                kind="user_new_topic",
                topic_id=topic.id,
                post_id=first_post.id,
                actor_id=current_user.id,
                data={
                    "topic_title": topic.title,
                    "topic_slug": topic.slug,
                    "board_slug": topic.board.slug,
                    "post_number": first_post.post_number,
                    "actor_name": current_user.username,
                },
            )

    async def _queue_reply_notifications(
        self,
        topic: Topic,
        post: Post,
        current_user: User,
        parent_post: Post | None,
    ) -> None:
        notified_user_ids: set[str] = set()

        if topic.user_id != current_user.id:
            if await self._add_reply_notification(topic.user_id, topic, post, current_user):
                notified_user_ids.add(topic.user_id)

        if parent_post and parent_post.user_id != current_user.id:
            if await self._add_reply_notification(parent_post.user_id, topic, post, current_user):
                notified_user_ids.add(parent_post.user_id)

        mentioned_users = await self._find_mentioned_users(post.raw_md)
        for mentioned_user in mentioned_users:
            if mentioned_user.id == current_user.id:
                continue
            if await self._is_topic_muted_for_user(topic.id, mentioned_user.id):
                continue
            await self._add_notification(
                user_id=mentioned_user.id,
                kind="mentioned",
                topic_id=topic.id,
                post_id=post.id,
                actor_id=current_user.id,
                data={
                    "topic_title": topic.title,
                    "topic_slug": topic.slug,
                    "post_number": post.post_number,
                    "actor_name": current_user.username,
                },
            )
            notified_user_ids.add(mentioned_user.id)

        read_states = await self.session.scalars(
            select(TopicRead).where(
                TopicRead.topic_id == topic.id,
                TopicRead.user_id != current_user.id,
                TopicRead.notification_level.in_(("watching", "tracking")),
            )
        )
        for read_state in read_states:
            if read_state.user_id in notified_user_ids:
                continue
            await self._add_notification(
                user_id=read_state.user_id,
                kind="topic_new_post",
                topic_id=topic.id,
                post_id=post.id,
                actor_id=current_user.id,
                data={
                    "topic_title": topic.title,
                    "topic_slug": topic.slug,
                    "post_number": post.post_number,
                    "actor_name": current_user.username,
                },
            )

    async def _queue_private_message_reply_notifications(
        self,
        topic: Topic,
        post: Post,
        current_user: User,
    ) -> None:
        participants = await self.session.scalars(
            select(PrivateMessageParticipant).where(
                PrivateMessageParticipant.topic_id == topic.id,
                PrivateMessageParticipant.user_id != current_user.id,
                PrivateMessageParticipant.muted.is_(False),
            )
        )
        for participant in participants:
            await self._add_notification(
                user_id=participant.user_id,
                kind="private_message",
                topic_id=topic.id,
                post_id=post.id,
                actor_id=current_user.id,
                data={
                    "topic_title": topic.title,
                    "topic_slug": topic.slug,
                    "post_number": post.post_number,
                    "actor_name": current_user.username,
                },
            )

    async def _add_reply_notification(
        self,
        user_id: str,
        topic: Topic,
        post: Post,
        current_user: User,
    ) -> bool:
        if await self._is_topic_muted_for_user(topic.id, user_id):
            return False
        await self._add_notification(
            user_id=user_id,
            kind="replied",
            topic_id=topic.id,
            post_id=post.id,
            actor_id=current_user.id,
            data={
                "topic_title": topic.title,
                "topic_slug": topic.slug,
                "post_number": post.post_number,
                "actor_name": current_user.username,
            },
        )
        return True

    async def _is_topic_muted_for_user(self, topic_id: str, user_id: str) -> bool:
        read_state = await self.session.scalar(
            select(TopicRead.notification_level).where(
                TopicRead.topic_id == topic_id,
                TopicRead.user_id == user_id,
            )
        )
        return read_state == "muted"

    async def _find_mentioned_users(self, raw_md: str) -> list[User]:
        mentioned_names = {match.group(1) for match in MENTION_PATTERN.finditer(raw_md)}
        if not mentioned_names:
            return []
        result = await self.session.scalars(select(User).where(User.username.in_(mentioned_names)))
        return list(result)

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

    async def _add_notification(
        self,
        *,
        user_id: str,
        kind: str,
        topic_id: str | None,
        post_id: str | None,
        actor_id: str | None,
        data: dict[str, object],
    ) -> None:
        if actor_id and await self._relationship_blocks_notification(user_id, actor_id):
            return
        await BackgroundJobService(self.session).enqueue_notification(
            user_id=user_id,
            kind=kind,
            topic_id=topic_id,
            post_id=post_id,
            actor_id=actor_id,
            data=data,
            idempotency_key=notification_idempotency_key(
                kind=kind,
                user_id=user_id,
                topic_id=topic_id,
                post_id=post_id,
                actor_id=actor_id,
                data=data,
            ),
            commit=False,
        )

    async def _relationship_blocks_notification(self, recipient_id: str, actor_id: str) -> bool:
        relationship_id = await self.session.scalar(
            select(UserRelationship.id).where(
                or_(
                    (
                        (UserRelationship.actor_user_id == recipient_id)
                        & (UserRelationship.target_user_id == actor_id)
                        & (UserRelationship.relationship_type.in_(("ignore", "block")))
                    ),
                    (
                        (UserRelationship.actor_user_id == actor_id)
                        & (UserRelationship.target_user_id == recipient_id)
                        & (UserRelationship.relationship_type == "block")
                    ),
                )
            )
        )
        return relationship_id is not None

    async def publish_queued_topic(self, reviewable: Reviewable) -> Topic:
        board = await self.get_board_by_slug(reviewable.data["board_slug"])
        creator = await self.session.get(User, reviewable.created_by_id)
        if not creator:
            raise NotFoundError("user_not_found", "Creator not found")

        title = str(reviewable.data["title"]).strip()
        raw_md = str(reviewable.data["raw_md"]).strip()
        cooked_html = self._render_required_markdown(raw_md)
        topic_slug = await self._unique_topic_slug(board.id, title)
        normalized_tags = self._normalized_unique_tags(reviewable.data["tags"])
        self._validate_board_topic_tags(board, normalized_tags)
        tags = await self._resolve_tags(normalized_tags)
        now = utcnow()
        topic = Topic(
            board_id=board.id,
            user_id=creator.id,
            title=title,
            slug=topic_slug,
            pinned=reviewable.data["pinned"],
            featured=reviewable.data["featured"],
            hot_score=calculate_hot_score(reply_count=0, like_count=0, view_count=0),
            last_posted_at=now,
            tags=tags,
        )
        self.session.add(topic)
        await self.session.flush()
        first_post = Post(
            topic_id=topic.id,
            user_id=creator.id,
            post_number=1,
            raw_md=raw_md,
            cooked_html=cooked_html,
        )
        self.session.add(first_post)
        board.topic_count += 1
        board.post_count += 1
        await self._upsert_read_state(topic.id, creator.id, post_number=1)
        await self.session.flush()
        await UploadService(self.session).attach_uploads_to_post(
            raw_md,
            post=first_post,
            topic=topic,
            board=board,
            current_user=creator,
        )
        await self._queue_board_new_topic_notifications(board, topic, first_post, creator)
        await SearchIndexService(self.session).sync_topic(topic.id)

        reviewable.target_type = "topic"
        reviewable.target_id = topic.id
        reviewable.topic_id = topic.id
        reviewable.post_id = first_post.id
        return topic

    async def publish_queued_post(self, reviewable: Reviewable) -> Post:
        topic = await self.session.get(Topic, reviewable.topic_id)
        if not topic:
            raise NotFoundError("topic_not_found", "Topic not found")
        creator = await self.session.get(User, reviewable.created_by_id)
        if not creator:
            raise NotFoundError("user_not_found", "Creator not found")

        parent_post = None
        if reviewable.data.get("parent_post_id"):
            parent_post = await self.session.get(Post, reviewable.data["parent_post_id"])

        raw_md = str(reviewable.data["raw_md"]).strip()
        next_number = (
            await self.session.scalar(
                select(func.max(Post.post_number)).where(Post.topic_id == topic.id)
            )
            or 0
        ) + 1
        post = Post(
            topic_id=topic.id,
            user_id=creator.id,
            parent_id=parent_post.id if parent_post else None,
            post_number=next_number,
            raw_md=raw_md,
            cooked_html=self._render_required_markdown(raw_md),
        )
        self.session.add(post)

        if parent_post:
            parent_post.reply_count += 1
        topic.reply_count += 1
        topic.last_posted_at = utcnow()
        topic.hot_score = calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
        topic.board.post_count += 1
        await self._upsert_read_state(topic.id, creator.id, post_number=next_number)
        await self.session.flush()
        await UploadService(self.session).attach_uploads_to_post(
            raw_md,
            post=post,
            topic=topic,
            board=topic.board,
            current_user=creator,
        )
        await self._queue_reply_notifications(topic, post, creator, parent_post)
        await SearchIndexService(self.session).sync_topic(topic.id)

        reviewable.target_type = "post"
        reviewable.target_id = post.id
        reviewable.post_id = post.id
        return post

    async def publish_queued_edit(self, reviewable: Reviewable) -> Post:
        post = await self.session.get(Post, reviewable.post_id)
        if not post:
            raise NotFoundError("post_not_found", "Post not found")
        editor = await self.session.get(User, reviewable.created_by_id)
        if not editor:
            raise NotFoundError("user_not_found", "Editor not found")

        raw_md = str(reviewable.data["raw_md"]).strip()
        revision = await self._create_post_revision(
            post,
            editor=editor,
            reason=reviewable.data.get("edit_reason"),
            next_raw_md=raw_md,
        )
        post.raw_md = raw_md
        post.cooked_html = self._render_required_markdown(raw_md)
        post.updated_at = utcnow()
        self._add_audit_log(
            actor_id=editor.id,
            action="post_edited",
            target_type="post",
            target_id=post.id,
            board_id=post.topic.board_id,
            data={
                "revision_id": revision.id,
                "version_number": revision.version_number,
                "post_number": post.post_number,
                "reason": revision.edit_reason or "",
            },
        )
        await UploadService(self.session).attach_uploads_to_post(
            raw_md,
            post=post,
            topic=post.topic,
            board=post.topic.board,
            current_user=editor,
        )
        await SearchIndexService(self.session).sync_topic(post.topic_id)

        reviewable.target_type = "post"
        reviewable.target_id = post.id
        return post
