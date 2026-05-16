from __future__ import annotations

import html
import re
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.db.base import new_uuid, utcnow
from app.models.forum import Board, BoardMember, Post, Tag, Topic, TopicRead
from app.models.interaction import Notification
from app.models.user import User
from app.schemas.forum import (
    BoardCreateRequest,
    PostCreateRequest,
    PostUpdateRequest,
    TopicCreateRequest,
    TopicSort,
)

SLUG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
TAG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9一-鿿_.-]+")
MENTION_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])@([A-Za-z0-9_.-]{3,32})")
LIKE_ESCAPE_PATTERN = re.compile(r"([%_\\])")


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
            html.escape(line.strip()) for line in paragraph_lines if line.strip()
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
        return await self.get_board_by_slug(board.slug)

    async def list_boards(self) -> list[Board]:
        result = await self.session.scalars(
            select(Board).order_by(desc(Board.topic_count), Board.name)
        )
        return list(result)

    async def get_board_by_slug(self, slug: str) -> Board:
        board = await self.session.scalar(select(Board).where(Board.slug == slug))
        if not board:
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def get_board_detail(self, slug: str) -> tuple[Board, list[Topic]]:
        board = await self.get_board_by_slug(slug)
        topics = await self.list_topics(board_slug=board.slug, sort="latest", limit=5)
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
    ) -> list[Topic]:
        statement = select(Topic).options(
            selectinload(Topic.board),
            selectinload(Topic.author),
            selectinload(Topic.tags),
        ).where(Topic.deleted_at.is_(None))
        if board_slug:
            board = await self.get_board_by_slug(board_slug)
            statement = statement.where(Topic.board_id == board.id)

        if query:
            pattern = f"%{escape_like(query.strip())}%"
            post_match = (
                select(Post.id)
                .where(Post.topic_id == Topic.id, Post.raw_md.ilike(pattern, escape="\\"))
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

    async def list_tags(self, *, limit: int = 30) -> list[Tag]:
        result = await self.session.scalars(
            select(Tag)
            .where(Tag.topic_count > 0)
            .order_by(desc(Tag.topic_count), Tag.name)
            .limit(limit)
        )
        return list(result)

    async def get_user_content_counts(self, username: str) -> tuple[User, int, int]:
        user = await self.get_user_by_username(username)
        topic_count = (
            await self.session.scalar(
                select(func.count(Topic.id)).where(
                    Topic.user_id == user.id,
                    Topic.deleted_at.is_(None),
                )
            )
            or 0
        )
        post_count = (
            await self.session.scalar(
                select(func.count(Post.id))
                .join(Post.topic)
                .where(
                    Post.user_id == user.id,
                    Post.deleted_at.is_(None),
                    Topic.deleted_at.is_(None),
                )
            )
            or 0
        )
        return user, topic_count, post_count

    async def list_user_topics(self, username: str, *, limit: int = 30) -> list[Topic]:
        user = await self.get_user_by_username(username)
        result = await self.session.scalars(
            select(Topic)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
            )
            .where(Topic.user_id == user.id, Topic.deleted_at.is_(None))
            .order_by(desc(Topic.last_posted_at))
            .limit(limit)
        )
        return list(result)

    async def create_topic(
        self,
        board_slug: str,
        payload: TopicCreateRequest,
        current_user: User,
    ) -> Topic:
        board = await self.get_board_by_slug(board_slug)
        cooked_html = self._render_required_markdown(payload.raw_md)
        topic_slug = await self._unique_topic_slug(board.id, payload.title)
        tags = await self._resolve_tags(payload.tags)
        now = utcnow()
        topic = Topic(
            board_id=board.id,
            user_id=current_user.id,
            title=payload.title.strip(),
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
            raw_md=payload.raw_md.strip(),
            cooked_html=cooked_html,
        )
        self.session.add(first_post)
        board.topic_count += 1
        board.post_count += 1
        await self._upsert_read_state(topic.id, current_user.id, post_number=1)
        await self.session.flush()
        await self._queue_board_new_topic_notifications(board, topic, first_post, current_user)
        await self.session.commit()
        return await self.get_topic(topic.id)

    async def get_topic(self, topic_id: str) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.board), selectinload(Topic.author), selectinload(Topic.tags)
            )
            .where(Topic.id == topic_id)
        )
        if not topic or topic.deleted_at is not None:
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    async def list_posts(self, topic_id: str) -> list[Post]:
        await self.get_topic(topic_id)
        result = await self.session.scalars(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.topic_id == topic_id)
            .order_by(Post.post_number)
        )
        return list(result)

    async def reply_to_topic(
        self,
        topic_id: str,
        payload: PostCreateRequest,
        current_user: User,
    ) -> Post:
        topic = await self.get_topic(topic_id)
        if topic.status != "open":
            raise ValidationError("topic_closed", "This topic is closed")

        parent_post: Post | None = None
        if payload.parent_post_id:
            parent_post = await self.session.get(Post, payload.parent_post_id)
            if not parent_post or parent_post.topic_id != topic.id:
                raise NotFoundError("post_not_found", "Parent post not found")

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
            raw_md=payload.raw_md.strip(),
            cooked_html=self._render_required_markdown(payload.raw_md),
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
        await self._queue_reply_notifications(topic, post, current_user, parent_post)
        await self.session.commit()
        return await self._get_post(post.id)

    async def update_post(
        self,
        post_id: str,
        payload: PostUpdateRequest,
        current_user: User,
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

        if not await self._can_edit_post(post, current_user):
            raise PermissionDeniedError("permission_denied", "Permission denied")

        stripped = payload.raw_md.strip()
        post.raw_md = stripped
        post.cooked_html = self._render_required_markdown(stripped)
        post.updated_at = utcnow()
        await self.session.commit()
        return await self._get_post(post.id)

    async def _can_edit_post(self, post: Post, current_user: User) -> bool:
        if post.user_id == current_user.id:
            return True
        if current_user.role in {"admin", "moderator"}:
            return True
        member = await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == post.topic.board_id,
                BoardMember.user_id == current_user.id,
                BoardMember.role.in_(("owner", "moderator")),
            )
        )
        if member:
            return True
        return post.topic.board.owner_id == current_user.id

    async def _get_post(self, post_id: str) -> Post:
        post = await self.session.scalar(
            select(Post).options(selectinload(Post.author)).where(Post.id == post_id)
        )
        if not post:
            raise NotFoundError("post_not_found", "Post not found")
        return post

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
