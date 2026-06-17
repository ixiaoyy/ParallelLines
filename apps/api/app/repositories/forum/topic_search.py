from __future__ import annotations

import re

from sqlalchemy import case, or_
from sqlalchemy.sql.elements import ColumnElement

from app.models.search import SearchDocument

LIKE_ESCAPE_PATTERN = re.compile(r"([%_\\])")
TAG_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9一-鿿_.-]+")
SEARCH_TOKEN_PATTERN = re.compile(r"\S+")


def normalize_search_query(value: str) -> str:
    """Return a whitespace-normalized search query for matching and logging.

    Key parameter `value` is raw user query text. Return value is casefolded
    token text; side effect is none.
    """

    return " ".join(SEARCH_TOKEN_PATTERN.findall(value.strip().casefold()))


def normalize_search_tag(value: str) -> str:
    """Return the normalized tag slug used by search and topic feed filters.

    Key parameter `value` is user-supplied tag text. Return value strips unsafe
    separators and leading hash markers; side effect is none.
    """

    return TAG_SEPARATOR_PATTERN.sub("-", value.strip().lower()).strip("-#")


def escape_search_like(value: str) -> str:
    """Escape LIKE wildcard characters before building ilike patterns.

    Key parameter `value` is one normalized search token. Return value is safe
    for SQLAlchemy `ilike(..., escape="\\")`; side effect is none.
    """

    return LIKE_ESCAPE_PATTERN.sub(r"\\\1", value)


def search_match_conditions(query: str) -> list[ColumnElement[bool]]:
    """Build SQLAlchemy conditions matching a normalized query across search fields.

    Key parameter `query` is raw or normalized query text. Return value is a
    list of AND-able SQLAlchemy expressions; side effect is none.
    """

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


def search_relevance_expression(query: str) -> ColumnElement[int] | int:
    """Return the weighted SQL relevance expression used by topic search feeds.

    Key parameter `query` is raw or normalized query text. Return value is a
    SQLAlchemy expression ranking title, tag, author, and body matches; side
    effect is none.
    """

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
