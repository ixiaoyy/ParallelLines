from __future__ import annotations

from asyncio import gather
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, desc, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.core.exceptions import NotFoundError
from app.db.base import utcnow
from app.models.forum import Board, Poll, Post, Tag, Topic, topic_tags
from app.models.interaction import Bookmark, Reaction, Vote
from app.models.search import SearchDocument, SearchLog
from app.models.social import UserRelationship
from app.models.user import User
from app.repositories.forum.topic_search import (
    normalize_search_query,
    normalize_search_tag,
    search_match_conditions,
    search_relevance_expression,
)
from app.schemas.forum import TopicSort
from app.services.board_access import (
    board_visible_condition as build_board_visible_condition,
)
from app.services.board_access import (
    can_access_board as user_can_access_board,
)
from app.services.topic_cursor import apply_latest_topic_cursor, parse_topic_cursor

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


def search_topic_excerpt(raw_md: str) -> str:
    """Return a compact first-post excerpt for search result topic cards.

    Key parameter `raw_md` is first-post Markdown. Return value mirrors the
    existing topic-card length limit without loading full `Topic.posts`
    relationships. The function has no side effects.
    """

    cleaned = " ".join(raw_md.split())
    if len(cleaned) > 140:
        return cleaned[:140].rstrip() + "..."
    return cleaned


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
        cursor: str | datetime | None = None,
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
                selectinload(Topic.poll).selectinload(Poll.options),
                noload(Topic.posts),
            )
            .where(
                Topic.deleted_at.is_(None),
                Topic.status != "hidden",
                self._board_visible_condition(current_user),
                *search_match_conditions(normalized),
            )
        )
        if current_user is not None:
            statement = statement.where(self._visible_author_condition(current_user))

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

        topic_cursor = parse_topic_cursor(cursor)
        statement = apply_latest_topic_cursor(statement, topic_cursor)

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
        await self._decorate_topic_excerpts(topics)
        await self._decorate_topics_for_user(topics, current_user)
        await self.log_search(
            query=query,
            normalized_query=normalized,
            filters=filters,
            result_count=len(topics),
            current_user=current_user,
        )
        return topics

    async def _decorate_topic_excerpts(self, topics: list[Topic]) -> None:
        """Attach first-post excerpts to search topic rows without loading posts.

        Key parameter `topics` is the ordered result set. Return value is none.
        Side effect: assigns transient `topic.excerpt` attributes used by
        `TopicResponse.from_model`.
        """

        if not topics:
            return
        topic_ids = [topic.id for topic in topics]
        rows = (
            await self.session.execute(
                select(Post.topic_id, func.substr(Post.raw_md, 1, 600)).where(
                    Post.topic_id.in_(topic_ids),
                    Post.post_number == 1,
                    Post.deleted_at.is_(None),
                )
            )
        ).all()
        excerpt_by_topic = {
            str(topic_id): search_topic_excerpt(str(raw_md or "")) for topic_id, raw_md in rows
        }
        for topic in topics:
            topic.excerpt = excerpt_by_topic.get(topic.id, "")

    async def _decorate_topics_for_user(
        self,
        topics: list[Topic],
        current_user: User | None,
    ) -> None:
        """Attach bookmark/reaction/vote state to search topic rows.

        Key parameters are the ordered `topics` and optional `current_user`.
        Return value is none. Side effect: assigns transient response-only
        fields such as `bookmark_count`, `liked_by_me`, and `my_vote`.
        """

        if not topics:
            return
        for topic in topics:
            topic.liked_by_me = False
            topic.bookmarked_by_me = False
            topic.my_vote = 0

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

        # Parallelize Reaction, Bookmark, and Vote queries for better performance
        liked_result, bookmarked_result, votes_result = await gather(
            self.session.scalars(
                select(Reaction.target_id).where(
                    Reaction.target_type == "topic",
                    Reaction.target_id.in_(topic_ids),
                    Reaction.user_id == current_user.id,
                    Reaction.type == "like",
                )
            ),
            self.session.scalars(
                select(Bookmark.target_id).where(
                    Bookmark.target_type == "topic",
                    Bookmark.target_id.in_(topic_ids),
                    Bookmark.user_id == current_user.id,
                )
            ),
            self.session.scalars(
                select(Vote).where(
                    Vote.target_type == "topic",
                    Vote.target_id.in_(topic_ids),
                    Vote.user_id == current_user.id,
                )
            ),
        )
        liked_topic_ids = set(liked_result)
        bookmarked_topic_ids = set(bookmarked_result)
        votes = list(votes_result)
        vote_by_topic = {vote.target_id: vote.value for vote in votes}
        for topic in topics:
            topic.liked_by_me = topic.id in liked_topic_ids
            topic.bookmarked_by_me = topic.id in bookmarked_topic_ids
            topic.my_vote = vote_by_topic.get(topic.id, 0)

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
        return build_board_visible_condition(current_user)

    def _visible_author_condition(self, current_user: User):
        hidden_author_exists = (
            select(UserRelationship.id)
            .where(
                UserRelationship.actor_user_id == current_user.id,
                UserRelationship.target_user_id == Topic.user_id,
                UserRelationship.relationship_type.in_(("ignore", "block")),
            )
            .exists()
        )
        return not_(hidden_author_exists)

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
        return await user_can_access_board(self.session, board, current_user)
