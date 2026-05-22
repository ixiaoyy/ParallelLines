from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.base import utcnow
from app.models.forum import Board, BoardMember, Tag, Topic, topic_tags
from app.models.search import SearchDocument, SearchLog
from app.models.user import User
from app.schemas.forum import TopicSort

LIKE_ESCAPE_PATTERN = re.compile(r"([%_\\])")
TAG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9一-鿿_.-]+")
SEARCH_TOKEN_PATTERN = re.compile(r"\S+")
SEARCHABLE_TOPIC_STATUSES = {"open", "closed", "archived"}


@dataclass(frozen=True)
class SearchFilters:
    board_slug: str | None = None
    tag: str | None = None
    author: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    status: str | None = None

    def to_log_dict(self) -> dict[str, object]:
        return {
            "board": self.board_slug,
            "tag": self.tag,
            "author": self.author,
            "created_after": self.created_after.isoformat() if self.created_after else None,
            "created_before": self.created_before.isoformat() if self.created_before else None,
            "status": self.status,
        }


def normalize_search_query(value: str) -> str:
    return " ".join(SEARCH_TOKEN_PATTERN.findall(value.strip().casefold()))


def normalize_search_tag(value: str) -> str:
    return TAG_SEPARATOR_PATTERN.sub("-", value.strip().lower()).strip("-#")


def escape_search_like(value: str) -> str:
    return LIKE_ESCAPE_PATTERN.sub(r"\\\1", value)


def search_match_conditions(query: str):
    normalized = normalize_search_query(query)
    conditions = []
    for token in SEARCH_TOKEN_PATTERN.findall(normalized):
        pattern = f"%{escape_search_like(token)}%"
        conditions.append(
            or_(
                SearchDocument.title.ilike(pattern, escape="\\"),
                SearchDocument.body.ilike(pattern, escape="\\"),
                SearchDocument.tags_text.ilike(pattern, escape="\\"),
                SearchDocument.author_username.ilike(pattern, escape="\\"),
            )
        )
    return conditions


def search_relevance_expression(query: str):
    relevance = 0
    for token in SEARCH_TOKEN_PATTERN.findall(normalize_search_query(query)):
        starts_with = f"{escape_search_like(token)}%"
        contains = f"%{escape_search_like(token)}%"
        relevance = (
            relevance
            + case((SearchDocument.title.ilike(starts_with, escape="\\"), 60), else_=0)
            + case((SearchDocument.title.ilike(contains, escape="\\"), 35), else_=0)
            + case((SearchDocument.tags_text.ilike(contains, escape="\\"), 20), else_=0)
            + case((SearchDocument.author_username.ilike(contains, escape="\\"), 10), else_=0)
            + case((SearchDocument.body.ilike(contains, escape="\\"), 8), else_=0)
        )
    return relevance


class SearchIndexService:
    """Database-backed search index adapter with a future external-engine seam."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sync_topic(self, topic_id: str) -> SearchDocument | None:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.author),
                selectinload(Topic.tags),
                selectinload(Topic.posts),
            )
            .where(Topic.id == topic_id)
        )
        if not topic or topic.deleted_at is not None or topic.status == "hidden":
            await self.remove_topic(topic_id)
            return None

        visible_posts = sorted(
            (post for post in topic.posts if post.deleted_at is None),
            key=lambda post: (post.post_number, post.created_at),
        )
        body = "\n".join(post.raw_md for post in visible_posts if post.raw_md)
        tags_text = " ".join(
            dict.fromkeys(
                [tag.name for tag in topic.tags]
                + [tag.slug for tag in topic.tags]
                + [topic.author.username]
            )
        )

        document = await self.session.scalar(
            select(SearchDocument).where(SearchDocument.topic_id == topic.id)
        )
        if document is None:
            document = SearchDocument(
                topic_id=topic.id,
                board_id=topic.board_id,
                author_id=topic.user_id,
                author_username=topic.author.username,
                topic_status=topic.status,
                title=topic.title,
                body=body,
                tags_text=tags_text,
            )
            self.session.add(document)
        else:
            document.board_id = topic.board_id
            document.author_id = topic.user_id
            document.author_username = topic.author.username
            document.topic_status = topic.status
            document.title = topic.title
            document.body = body
            document.tags_text = tags_text
            document.indexed_at = utcnow()
        await self.session.flush()
        return document

    async def remove_topic(self, topic_id: str) -> None:
        await self.session.execute(
            delete(SearchDocument).where(SearchDocument.topic_id == topic_id)
        )
        await self.session.flush()

    async def rebuild_all(self) -> dict[str, int]:
        topic_ids = list(
            await self.session.scalars(
                select(Topic.id).where(Topic.deleted_at.is_(None), Topic.status != "hidden")
            )
        )
        active_topic_ids = set(topic_ids)
        synced_count = 0
        for topic_id in topic_ids:
            if await self.sync_topic(topic_id) is not None:
                synced_count += 1

        stale_documents = list(await self.session.scalars(select(SearchDocument)))
        removed_count = 0
        for document in stale_documents:
            if document.topic_id not in active_topic_ids:
                await self.session.delete(document)
                removed_count += 1
        await self.session.flush()
        return {"synced_count": synced_count, "removed_count": removed_count}


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.index = SearchIndexService(session)

    async def search_topics(
        self,
        *,
        query: str,
        filters: SearchFilters,
        sort: TopicSort = "relevance",
        cursor: datetime | None = None,
        limit: int = 30,
        current_user: User | None = None,
    ) -> list[Topic]:
        normalized = normalize_search_query(query)
        if not normalized:
            await self.log_search(
                query=query,
                normalized_query=normalized,
                filters=filters,
                result_count=0,
                current_user=current_user,
            )
            return []

        relevance = search_relevance_expression(normalized)
        statement = (
            select(Topic, relevance.label("relevance"))
            .join(SearchDocument, SearchDocument.topic_id == Topic.id)
            .join(Topic.board)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
            )
            .where(
                Topic.deleted_at.is_(None),
                Topic.status != "hidden",
                self._board_visible_condition(current_user),
                *search_match_conditions(normalized),
            )
        )

        if filters.board_slug:
            board = await self._get_board_by_slug(filters.board_slug, current_user=current_user)
            statement = statement.where(Topic.board_id == board.id)

        if filters.tag:
            normalized_tag = normalize_search_tag(filters.tag)
            if normalized_tag:
                tag_exists = (
                    select(topic_tags.c.topic_id)
                    .join(Tag, topic_tags.c.tag_id == Tag.id)
                    .where(
                        topic_tags.c.topic_id == Topic.id,
                        or_(Tag.slug == normalized_tag, Tag.name == normalized_tag),
                    )
                    .exists()
                )
                statement = statement.where(tag_exists)

        if filters.author:
            statement = statement.where(SearchDocument.author_username == filters.author)

        if filters.created_after:
            statement = statement.where(Topic.created_at >= filters.created_after)

        if filters.created_before:
            statement = statement.where(Topic.created_at <= filters.created_before)

        if filters.status:
            statement = statement.where(Topic.status == filters.status)

        if cursor:
            statement = statement.where(Topic.last_posted_at < cursor)

        if sort == "hot":
            statement = statement.order_by(desc(Topic.hot_score), desc(Topic.last_posted_at))
        elif sort == "top":
            statement = statement.order_by(desc(Topic.like_count), desc(Topic.reply_count))
        elif sort == "latest":
            statement = statement.order_by(desc(Topic.last_posted_at), desc(Topic.id))
        else:
            statement = statement.order_by(
                relevance.desc(),
                desc(Topic.last_posted_at),
                desc(Topic.id),
            )

        result = await self.session.execute(statement.limit(limit))
        topics = [row[0] for row in result.unique().all()]
        await self.log_search(
            query=query,
            normalized_query=normalized,
            filters=filters,
            result_count=len(topics),
            current_user=current_user,
        )
        return topics

    async def log_search(
        self,
        *,
        query: str,
        normalized_query: str,
        filters: SearchFilters,
        result_count: int,
        current_user: User | None,
    ) -> None:
        self.session.add(
            SearchLog(
                user_id=current_user.id if current_user else None,
                query=query.strip()[:120],
                normalized_query=normalized_query[:120],
                filters=filters.to_log_dict(),
                result_count=result_count,
                has_results=result_count > 0,
            )
        )
        await self.session.commit()

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

    async def _get_board_by_slug(
        self,
        slug: str,
        *,
        current_user: User | None,
    ) -> Board:
        board = await self.session.scalar(select(Board).where(Board.slug == slug))
        if not board or not await self._can_access_board(board, current_user):
            raise NotFoundError("board_not_found", "Board not found")
        return board

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
