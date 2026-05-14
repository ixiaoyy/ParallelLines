from __future__ import annotations

import html
import re
from collections.abc import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.base import new_uuid, utcnow
from app.models.forum import Board, BoardMember, Post, Tag, Topic, TopicRead
from app.models.user import User
from app.schemas.forum import BoardCreateRequest, PostCreateRequest, TopicCreateRequest, TopicSort

SLUG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
TAG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9一-鿿_.-]+")


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
    ) -> list[Topic]:
        statement = select(Topic).options(
            selectinload(Topic.board),
            selectinload(Topic.author),
            selectinload(Topic.tags),
        )
        if board_slug:
            board = await self.get_board_by_slug(board_slug)
            statement = statement.where(Topic.board_id == board.id)

        if sort == "hot":
            statement = statement.order_by(desc(Topic.hot_score), desc(Topic.last_posted_at))
        elif sort == "top":
            statement = statement.order_by(desc(Topic.like_count), desc(Topic.reply_count))
        else:
            statement = statement.order_by(desc(Topic.last_posted_at))

        result = await self.session.scalars(statement.limit(limit))
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
            hot_score=self._calculate_hot_score(reply_count=0, like_count=0, view_count=0),
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
        if not topic:
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
        topic.hot_score = self._calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
        topic.board.post_count += 1
        await self._upsert_read_state(topic.id, current_user.id, post_number=next_number)
        await self.session.commit()
        return await self._get_post(post.id)

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
            tag = await self.session.scalar(select(Tag).where(Tag.slug == slug))
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

    def _calculate_hot_score(self, *, reply_count: int, like_count: int, view_count: int) -> float:
        return round(reply_count * 2 + like_count + view_count / 100, 2)
