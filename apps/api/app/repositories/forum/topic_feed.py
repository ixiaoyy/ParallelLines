from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, desc, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload, noload, selectinload
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from app.models.forum import Board, BoardMember, Poll, Tag, Topic
from app.models.search import SearchDocument
from app.models.social import UserRelationship
from app.models.user import User
from app.repositories.forum.topic_search import (
    search_match_conditions,
    search_relevance_expression,
)
from app.services.topic_cursor import apply_latest_topic_cursor, parse_topic_cursor


class TopicFeedRepository:
    """Read repository for public topic feed and board-scoped topic queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Store the async database session used by repository read queries.

        Key parameter `session` is the current request/session scope. Return
        value is none. Side effect: keeps the session reference on this object.
        """

        self.session = session

    async def list_visible_topics(
        self,
        *,
        board_id: str | None = None,
        sort: str = "latest",
        limit: int = 30,
        query: str | None = None,
        normalized_tag: str | None = None,
        author: str | None = None,
        cursor: str | datetime | None = None,
        current_user: User | None = None,
    ) -> list[Topic]:
        """Return visible public topics for feed, board, tag, author, or query filters.

        Key parameters mirror the public topic-list API except `board_id` and
        `normalized_tag` are resolved by the service layer. Return value is an
        ordered topic list with board, author, tag, and poll relationships
        loaded. Side effect: performs read queries only.
        """

        statement = (
            select(Topic)
            .join(Topic.board)
            .options(
                contains_eager(Topic.board),
                joinedload(Topic.author),
                selectinload(Topic.tags),
                selectinload(Topic.poll).selectinload(Poll.options),
                noload(Topic.posts),
            )
            .where(Topic.deleted_at.is_(None), self.board_visible_condition(current_user))
            .where(Topic.visibility == "public")
        )
        if current_user is not None:
            statement = statement.where(self.visible_author_condition(current_user))
        if board_id is not None:
            statement = statement.where(Topic.board_id == board_id)

        relevance = None
        if query and query.strip():
            relevance = search_relevance_expression(query)
            statement = statement.join(
                SearchDocument,
                SearchDocument.topic_id == Topic.id,
            ).where(*search_match_conditions(query))

        if normalized_tag:
            statement = statement.join(Topic.tags).where(
                or_(Tag.slug == normalized_tag, Tag.name == normalized_tag)
            )

        if author:
            statement = statement.join(Topic.author).where(User.username == author)

        topic_cursor = parse_topic_cursor(cursor)
        statement = self._apply_sort(statement, sort=sort, relevance=relevance, cursor=topic_cursor)

        result = await self.session.scalars(statement.distinct().limit(limit))
        return list(result)

    def _apply_sort(
        self,
        statement: Select[Any],
        *,
        sort: str,
        relevance: ColumnElement[int] | int | None,
        cursor: Any,
    ) -> Select[Any]:
        """Apply feed cursor and ordering rules to a topic statement.

        Key parameters are the SQLAlchemy `statement`, requested `sort`,
        optional search `relevance`, and parsed `cursor`. Return value is the
        ordered statement; side effect is none.
        """

        if sort == "relevance" and relevance is not None:
            statement = apply_latest_topic_cursor(statement, cursor)
            return statement.order_by(
                relevance.desc(),
                desc(Topic.last_posted_at),
                desc(Topic.id),
            )
        if sort == "recommended":
            statement = apply_latest_topic_cursor(statement, cursor)
            featured_rank = case((Topic.featured.is_(True), 1), else_=0)
            pinned_rank = case((Topic.pinned.is_(True), 1), else_=0)
            return statement.order_by(
                desc(featured_rank),
                desc(pinned_rank),
                desc(Topic.hot_score),
                desc(Topic.last_posted_at),
                desc(Topic.id),
            )
        if sort == "hot":
            statement = apply_latest_topic_cursor(statement, cursor)
            return statement.order_by(desc(Topic.hot_score), desc(Topic.last_posted_at))
        if sort == "top":
            statement = apply_latest_topic_cursor(statement, cursor)
            return statement.order_by(desc(Topic.like_count), desc(Topic.reply_count))
        if sort == "votes":
            statement = apply_latest_topic_cursor(statement, cursor)
            return statement.order_by(
                desc(Topic.vote_score),
                desc(Topic.vote_count),
                desc(Topic.last_posted_at),
            )

        pinned_rank = case((Topic.pinned.is_(True), 1), else_=0)
        statement = apply_latest_topic_cursor(statement, cursor, include_pinned=True)
        return statement.order_by(
            desc(pinned_rank),
            desc(Topic.last_posted_at),
            desc(Topic.id),
        )

    @staticmethod
    def board_visible_condition(current_user: User | None) -> ColumnElement[bool]:
        """Return the board visibility expression for public feed reads.

        Key parameter `current_user` scopes private board membership access.
        Return value is a SQLAlchemy expression; side effect is none.
        """

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

    @staticmethod
    def visible_author_condition(
        current_user: User,
        author_id_column: Any = Topic.user_id,
    ) -> ColumnElement[bool]:
        """Return the author visibility expression for ignored or blocked users.

        Key parameters are `current_user` and optional `author_id_column`.
        Return value filters out ignored/blocked authors; side effect is none.
        """

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
