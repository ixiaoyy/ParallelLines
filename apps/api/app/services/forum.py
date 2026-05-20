from __future__ import annotations

import html
import re
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import BOARD_MODERATOR_ROLES, is_global_moderator
from app.db.base import new_uuid, utcnow
from app.models.forum import (
    Board,
    BoardInvitation,
    BoardMember,
    Post,
    PostRevision,
    Tag,
    Topic,
    TopicRead,
)
from app.models.interaction import Notification
from app.models.moderation import AuditLog
from app.models.upload import Upload
from app.models.user import User
from app.schemas.forum import (
    BoardCreateRequest,
    BoardInviteCreateRequest,
    PostCreateRequest,
    PostRevisionRestoreRequest,
    PostUpdateRequest,
    TopicCreateRequest,
    TopicLifecycleRequest,
    TopicMergeRequest,
    TopicMoveRequest,
    TopicSort,
    TopicSplitRequest,
)
from app.services.content_safety import enforce_content_policy
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
    r"^/(?:api/v1/)?uploads/[0-9a-fA-F-]{36}/content(?:\?[^<>\"]*)?$"
)


def slugify(value: str, *, fallback_prefix: str = "item") -> str:
    normalized = SLUG_SEPARATOR_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or f"{fallback_prefix}-{new_uuid()[:8]}"


def normalize_tag_name(value: str) -> str:
    return TAG_SEPARATOR_PATTERN.sub("-", value.strip().lower()).strip("-#")


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
                rendered.append(
                    f'<img src="{safe_url}" alt="{safe_label}" loading="lazy" />'
                )
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

        board = Board(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            color=payload.color,
            owner_id=current_user.id,
            visibility=payload.visibility,
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
        statement = select(Board).where(self._board_visible_condition(current_user))
        result = await self.session.scalars(
            statement.order_by(desc(Board.topic_count), Board.name)
        )
        return list(result)

    async def get_board_by_slug(
        self,
        slug: str,
        *,
        current_user: User | None = None,
        include_private_for_owner: bool = False,
    ) -> Board:
        board = await self.session.scalar(select(Board).where(Board.slug == slug))
        if not board or (
            not include_private_for_owner
            and not await self._can_access_board(board, current_user)
        ):
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def get_board_detail(
        self,
        slug: str,
        *,
        current_user: User | None = None,
    ) -> tuple[Board, list[Topic]]:
        board = await self.get_board_by_slug(slug, current_user=current_user)
        topics = await self.list_topics(
            board_slug=board.slug,
            sort="latest",
            limit=5,
            current_user=current_user,
        )
        return board, topics

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
            )
            .where(Topic.deleted_at.is_(None), self._board_visible_condition(current_user))
        )
        if board_slug:
            board = await self.get_board_by_slug(board_slug, current_user=current_user)
            statement = statement.where(Topic.board_id == board.id)

        if query:
            pattern = f"%{escape_like(query.strip())}%"
            post_match = (
                select(Post.id)
                .where(
                    Post.topic_id == Topic.id,
                    Post.deleted_at.is_(None),
                    Post.raw_md.ilike(pattern, escape="\\"),
                )
                .exists()
            )
            statement = statement.where(or_(Topic.title.ilike(pattern, escape="\\"), post_match))

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

        if sort == "hot":
            statement = statement.order_by(desc(Topic.hot_score), desc(Topic.last_posted_at))
        elif sort == "top":
            statement = statement.order_by(desc(Topic.like_count), desc(Topic.reply_count))
        else:
            statement = statement.order_by(desc(Topic.last_posted_at))

        result = await self.session.scalars(statement.distinct().limit(limit))
        return list(result)

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
        result = await self.session.scalars(
            select(Tag)
            .join(Tag.topics)
            .join(Topic.board)
            .where(Tag.topic_count > 0, self._board_visible_condition(current_user))
            .group_by(Tag.id)
            .order_by(desc(Tag.topic_count), Tag.name)
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
        result = await self.session.scalars(
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
                self._board_visible_condition(current_user),
            )
            .order_by(desc(Topic.last_posted_at))
            .limit(limit)
        )
        return list(result)

    async def create_topic(
        self,
        board_slug: str,
        payload: TopicCreateRequest,
        current_user: User,
        request: Request | None = None,
    ) -> Topic:
        board = await self.get_board_by_slug(board_slug, current_user=current_user)
        await SpamPreventionService(self.session).enforce_topic(
            request,
            current_user=current_user,
            title=payload.title,
            raw_md=payload.raw_md,
        )
        filtered = enforce_content_policy({"title": payload.title, "raw_md": payload.raw_md})
        title = filtered["title"].strip()
        raw_md = filtered["raw_md"].strip()
        cooked_html = self._render_required_markdown(raw_md)
        topic_slug = await self._unique_topic_slug(board.id, title)
        tags = await self._resolve_tags(payload.tags)
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
        await self.session.commit()
        return await self.get_topic(topic.id, current_user=current_user)

    async def get_topic(self, topic_id: str, *, current_user: User | None = None) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.board), selectinload(Topic.author), selectinload(Topic.tags)
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
            or not await self._can_access_board(topic.board, current_user)
        ):
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    async def list_posts(self, topic_id: str, *, current_user: User | None = None) -> list[Post]:
        await self.get_topic(topic_id, current_user=current_user)
        result = await self.session.scalars(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.topic_id == topic_id)
            .order_by(Post.post_number)
        )
        return list(result)

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
    ) -> Post:
        topic = await self.get_topic(topic_id, current_user=current_user)
        if topic.status != "open":
            raise ValidationError("topic_closed", "This topic is closed")

        parent_post: Post | None = None
        if payload.parent_post_id:
            parent_post = await self.session.get(Post, payload.parent_post_id)
            if not parent_post or parent_post.topic_id != topic.id:
                raise NotFoundError("post_not_found", "Parent post not found")

        await SpamPreventionService(self.session).enforce_reply(
            request,
            current_user=current_user,
            raw_md=payload.raw_md,
        )
        filtered = enforce_content_policy({"raw_md": payload.raw_md})
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
        await self._queue_reply_notifications(topic, post, current_user, parent_post)
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
        filtered = enforce_content_policy({"raw_md": payload.raw_md})
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
        self._add_notification(
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
                    notification_level="normal",
                )
            )
            invitation.board.follower_count += 1
        invitation.status = "accepted"
        invitation.responded_at = utcnow()
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

    def _require_invitee(self, invitation: BoardInvitation, current_user: User) -> None:
        if invitation.invitee_id != current_user.id:
            raise PermissionDeniedError(
                "board_invite_forbidden",
                "Board invite permission required",
            )

    def _require_pending_invite(self, invitation: BoardInvitation) -> None:
        if invitation.status != "pending":
            raise ValidationError("board_invite_not_pending", "Board invite is not pending")

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
            update(PostRevision)
            .where(PostRevision.post_id.in_(post_ids))
            .values(topic_id=topic_id)
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
            self._add_notification(
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

    async def _queue_reply_notifications(
        self,
        topic: Topic,
        post: Post,
        current_user: User,
        parent_post: Post | None,
    ) -> None:
        notified_user_ids: set[str] = set()

        if topic.user_id != current_user.id:
            self._add_reply_notification(topic.user_id, topic, post, current_user)
            notified_user_ids.add(topic.user_id)

        if parent_post and parent_post.user_id != current_user.id:
            self._add_reply_notification(parent_post.user_id, topic, post, current_user)
            notified_user_ids.add(parent_post.user_id)

        mentioned_users = await self._find_mentioned_users(post.raw_md)
        for mentioned_user in mentioned_users:
            if mentioned_user.id == current_user.id:
                continue
            self._add_notification(
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
            self._add_notification(
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

    def _add_reply_notification(
        self,
        user_id: str,
        topic: Topic,
        post: Post,
        current_user: User,
    ) -> None:
        self._add_notification(
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

    def _add_notification(
        self,
        *,
        user_id: str,
        kind: str,
        topic_id: str | None,
        post_id: str | None,
        actor_id: str | None,
        data: dict[str, object],
    ) -> None:
        if actor_id and user_id == actor_id:
            return
        self.session.add(
            Notification(
                user_id=user_id,
                type=kind,
                topic_id=topic_id,
                post_id=post_id,
                actor_id=actor_id,
                data=data,
            )
        )
