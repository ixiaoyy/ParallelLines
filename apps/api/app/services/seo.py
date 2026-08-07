from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlsplit
from xml.sax.saxutils import escape

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.core.exceptions import NotFoundError
from app.db.base import as_utc_datetime
from app.models.admin import SiteSetting
from app.models.forum import Board, Post, PostRevision, Topic
from app.models.user import User
from app.schemas.seo import SeoMetaResponse, SitemapUrl

MAX_SITEMAP_ITEMS_PER_TYPE = 1000
MAX_HOME_LINKS_PER_TYPE = 20
MAX_BOARD_PAGE_TOPICS = 30
MAX_TOPIC_PAGE_POSTS = 51
MAX_PROFILE_PAGE_TOPICS = 20
SITE_TITLE_FALLBACK = "平行线"
SITE_BRAND_NAME = "ParallelLines"
SITE_TAGLINE_FALLBACK = "让答案可追溯"
SITE_DESCRIPTION_FALLBACK = "让答案可追溯的中文技术论坛。"
SITE_LOGO_FALLBACK = "/logo-lines-mark.png"
LEGACY_SITE_LOGO_URLS = {
    "/logo-lines.png",
    "/logo.png",
    "/brand-mark.svg",
    "/favicon.svg",
}
PUBLIC_SITE_SETTING_KEYS = {"site_title", "site_tagline", "brand_logo_url"}

JsonObject = dict[str, object]
SeoPageKind = Literal["home", "boards", "board", "topic", "profile", "restricted", "missing"]


@dataclass(frozen=True)
class LegacyTopicRedirect:
    status_code: int
    location: str


@dataclass(frozen=True)
class SeoSiteIdentity:
    title: str
    tagline: str
    logo_url: str


@dataclass(frozen=True)
class SeoPageLink:
    path: str
    label: str
    description: str | None = None


@dataclass(frozen=True)
class SeoPagePost:
    author_name: str
    author_path: str | None
    published_at: datetime
    modified_at: datetime
    plain_text: str
    content_html: str
    post_number: int


@dataclass(frozen=True)
class SeoPageDocument:
    kind: SeoPageKind
    status_code: int
    site: SeoSiteIdentity
    meta: SeoMetaResponse
    heading: str
    intro: str
    links: tuple[SeoPageLink, ...] = ()
    posts: tuple[SeoPagePost, ...] = ()
    site_structured_data: JsonObject | None = None
    page_structured_data: JsonObject | None = None


SeoTopicPageResolution = SeoPageDocument | LegacyTopicRedirect


class SeoService:
    def __init__(self, session: AsyncSession) -> None:
        """Create a read-only SEO service around the provided async DB session.

        The ``session`` parameter supplies persisted public content. Construction
        performs no query or write and the service never records page views.
        """

        self.session = session

    async def sitemap_urls(self, base_url: str) -> list[SitemapUrl]:
        """Return bounded canonical sitemap entries for anonymous public content.

        ``base_url`` is the already resolved canonical origin. The returned list
        excludes private, hidden, deleted, merged, and non-public-profile data;
        this read-only method has no database side effects.
        """

        public_boards = await self._public_boards(MAX_SITEMAP_ITEMS_PER_TYPE)
        public_topics = await self._public_topics(MAX_SITEMAP_ITEMS_PER_TYPE)
        public_users = await self._public_users(MAX_SITEMAP_ITEMS_PER_TYPE)
        board_activity = await self._public_board_activity()
        topic_content_activity = await self._public_topic_content_activity()
        user_activity = await self._public_user_activity()
        latest_public_activity = latest_datetime(
            *(board.updated_at for board in public_boards),
            *board_activity.values(),
            *topic_content_activity.values(),
        )

        urls = [
            SitemapUrl(loc=absolute_url(base_url, "/"), lastmod=latest_public_activity),
            SitemapUrl(loc=absolute_url(base_url, "/boards"), lastmod=latest_public_activity),
        ]
        urls.extend(
            SitemapUrl(
                loc=absolute_url(base_url, f"/b/{encode_path_segment(board.slug)}"),
                lastmod=latest_datetime(board.updated_at, board_activity.get(board.id)),
            )
            for board in public_boards
        )
        urls.extend(
            SitemapUrl(
                loc=absolute_url(base_url, topic_canonical_path(topic)),
                lastmod=latest_datetime(
                    topic.last_posted_at,
                    topic_content_activity.get(topic.id),
                ),
            )
            for topic in public_topics
        )
        urls.extend(
            SitemapUrl(
                loc=absolute_url(base_url, f"/members/{encode_path_segment(user.id)}"),
                lastmod=user_activity.get(user.id),
            )
            for user in public_users
        )
        return urls

    async def robots_txt(self, base_url: str) -> str:
        """Return the public robots policy referencing the canonical sitemap URL.

        ``base_url`` is the canonical origin. The returned text keeps low-value
        private application areas out of crawling and has no side effects.
        """

        sitemap_url = absolute_url(base_url, "/sitemap.xml")
        return "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "Disallow: /admin",
                "Disallow: /messages",
                f"Sitemap: {sitemap_url}",
                "",
            ]
        )

    async def meta_for_path(self, path: str, base_url: str) -> SeoMetaResponse:
        """Resolve canonical metadata for one supported anonymous public path.

        ``path`` may include a query or fragment and ``base_url`` is the canonical
        origin. A metadata object is returned for public targets; unsupported or
        non-public targets raise ``NotFoundError`` without writing data.
        """

        identity = await self._site_identity()
        normalized = normalize_path(path)
        if normalized in {"", "/"}:
            return self._site_meta(
                identity,
                base_url,
                "/",
                title=site_brand_name(identity.title),
                description=site_description(identity),
            )
        if normalized == "/boards":
            return self._site_meta(
                identity,
                base_url,
                "/boards",
                title=f"全部版块 · {identity.title}",
                description=f"浏览{identity.title}的公开版块、最新主题和可追溯讨论。",
            )
        if normalized.startswith("/b/"):
            slug = normalized.removeprefix("/b/").split("/", 1)[0]
            return await self.board_meta(slug, base_url, identity=identity)
        if normalized.startswith("/members/"):
            user_id = normalized.removeprefix("/members/").split("/", 1)[0]
            return await self.user_meta(user_id, base_url, identity=identity)
        topic_id = topic_id_from_path(normalized)
        if topic_id:
            return await self.topic_meta(topic_id, base_url, identity=identity)
        raise NotFoundError("seo_meta_not_found", "SEO metadata target not found")

    async def topic_meta(
        self,
        topic_id: str,
        base_url: str,
        *,
        identity: SeoSiteIdentity | None = None,
    ) -> SeoMetaResponse:
        """Return metadata for one public, unmerged topic ID.

        ``topic_id`` identifies the topic and ``base_url`` builds absolute URLs;
        the optional ``identity`` avoids a repeated settings query. The method is
        read-only and raises ``NotFoundError`` for every non-indexable state.
        """

        site = identity or await self._site_identity()
        topic = await self._public_topic(topic_id)
        posts = await self._visible_topic_posts(topic.id, limit=1)
        description = topic_excerpt(topic, posts[0] if posts else None)
        return self._site_meta(
            site,
            base_url,
            topic_canonical_path(topic),
            title=f"{topic.title} · {topic.board.name} · {site.title}",
            description=description,
            og_type="article",
        )

    async def board_meta(
        self,
        slug: str,
        base_url: str,
        *,
        identity: SeoSiteIdentity | None = None,
    ) -> SeoMetaResponse:
        """Return metadata for one anonymous-public board slug.

        ``slug`` identifies the board and ``base_url`` builds absolute URLs; an
        optional preloaded ``identity`` avoids duplicate reads. The method has no
        writes and raises ``NotFoundError`` for non-public or unknown boards.
        """

        site = identity or await self._site_identity()
        board = await self._public_board(slug)
        description = board.description or f"浏览{board.name}版块的公开主题。"
        return self._site_meta(
            site,
            base_url,
            f"/b/{encode_path_segment(board.slug)}",
            title=f"{board.name} · {site.title}",
            description=truncate_text(description, 180),
        )

    async def user_meta(
        self,
        user_id: str,
        base_url: str,
        *,
        identity: SeoSiteIdentity | None = None,
    ) -> SeoMetaResponse:
        """Return metadata for one active profile explicitly visible to everyone.

        ``user_id`` is the stable member ID and ``base_url`` builds its canonical
        URL; optional ``identity`` reuses loaded settings. The method is read-only
        and does not expose members-only or private profile fields.
        """

        site = identity or await self._site_identity()
        user = await self._public_user(user_id)
        topic_count = await self._public_topic_count_for_user(user.id)
        display_name = user.display_name or user.username
        description = user.bio or f"{display_name} 在{site.title}发布了 {topic_count} 个公开主题。"
        return self._site_meta(
            site,
            base_url,
            f"/members/{encode_path_segment(user.id)}",
            title=f"{display_name} 的公开档案 · {site.title}",
            description=description,
        )

    async def legacy_topic_redirect(self, topic_id: str, base_url: str) -> LegacyTopicRedirect:
        """Return a permanent redirect from a legacy topic ID to its public canonical URL.

        ``topic_id`` may reference one merged source and ``base_url`` is the
        canonical origin. The method returns a 301 target, raises for non-public
        content, and never increments views or mutates content.
        """

        topic = await self._public_topic(topic_id, follow_merge=True)
        canonical_path = topic_canonical_path(topic)
        return LegacyTopicRedirect(status_code=301, location=absolute_url(base_url, canonical_path))

    async def home_page(self, base_url: str) -> SeoPageDocument:
        """Build the anonymous semantic home-page document and public links.

        ``base_url`` is the canonical origin. The returned document contains
        bounded board/topic links plus stable site schema and performs no writes.
        """

        identity = await self._site_identity()
        boards = await self._public_boards(MAX_HOME_LINKS_PER_TYPE)
        topics = await self._public_topics(MAX_HOME_LINKS_PER_TYPE)
        links = tuple(self._board_link(board) for board in boards) + tuple(
            self._topic_link(topic) for topic in topics
        )
        return SeoPageDocument(
            kind="home",
            status_code=200,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                "/",
                title=site_brand_name(identity.title),
                description=site_description(identity),
            ),
            heading=identity.title,
            intro=site_description(identity),
            links=links,
            site_structured_data=self._site_structured_data(identity, base_url),
        )

    async def boards_page(self, base_url: str) -> SeoPageDocument:
        """Build the anonymous board-directory document with bounded public links.

        ``base_url`` supplies canonical absolute URLs. The returned document is
        indexable, contains public boards only, and causes no persistence writes.
        """

        identity = await self._site_identity()
        boards = await self._public_boards(MAX_SITEMAP_ITEMS_PER_TYPE)
        description = f"浏览{identity.title}的公开版块、最新主题和可追溯讨论。"
        return SeoPageDocument(
            kind="boards",
            status_code=200,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                "/boards",
                title=f"全部版块 · {identity.title}",
                description=description,
            ),
            heading="全部版块",
            intro=description,
            links=tuple(self._board_link(board) for board in boards),
            site_structured_data=self._site_structured_data(identity, base_url),
        )

    async def board_page(self, slug: str, base_url: str) -> SeoPageDocument:
        """Resolve one board into a public, restricted, or missing HTML document.

        ``slug`` is the decoded route segment and ``base_url`` the canonical
        origin. Public output contains bounded topic links; private data is never
        copied into restricted/missing documents and no database writes occur.
        """

        board = await self._board_by_slug(slug)
        identity = await self._site_identity()
        path = f"/b/{encode_path_segment(slug)}"
        if board is None:
            return self._missing_document(identity, base_url, path)
        if board.visibility != "public":
            return self._restricted_document(identity, base_url, path)

        topics = await self._public_topics(MAX_BOARD_PAGE_TOPICS, board_id=board.id)
        description = board.description or f"浏览{board.name}版块的公开主题。"
        return SeoPageDocument(
            kind="board",
            status_code=200,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                f"/b/{encode_path_segment(board.slug)}",
                title=f"{board.name} · {identity.title}",
                description=description,
            ),
            heading=board.name,
            intro=description,
            links=tuple(self._topic_link(topic) for topic in topics),
            site_structured_data=self._site_structured_data(identity, base_url),
        )

    async def topic_page(
        self,
        topic_id: str,
        requested_slug: str | None,
        base_url: str,
    ) -> SeoTopicPageResolution:
        """Resolve a topic route into a canonical redirect or safe HTML document.

        ``topic_id`` and optional decoded ``requested_slug`` identify the route;
        ``base_url`` supplies canonical absolute URLs. Public posts are bounded,
        restricted content is omitted, and the method does not record views.
        """

        topic = await self._topic_by_id(topic_id)
        identity = await self._site_identity()
        request_path = f"/topics/{encode_path_segment(topic_id)}"
        if requested_slug is not None:
            request_path += f"/{encode_path_segment(requested_slug)}"
        if topic is None or topic.deleted_at is not None:
            return self._missing_document(identity, base_url, request_path)

        if topic.merged_into_topic_id is not None:
            try:
                target = await self._public_topic(topic.id, follow_merge=True)
            except NotFoundError:
                return self._missing_document(identity, base_url, request_path)
            return LegacyTopicRedirect(
                status_code=301,
                location=absolute_url(base_url, topic_canonical_path(target)),
            )

        canonical_path = topic_canonical_path(topic)
        if not self._topic_is_public(topic):
            return self._restricted_document(identity, base_url, request_path)
        if requested_slug != topic.slug:
            return LegacyTopicRedirect(
                status_code=301,
                location=absolute_url(base_url, canonical_path),
            )

        posts = await self._visible_topic_posts(topic.id, limit=MAX_TOPIC_PAGE_POSTS)
        post_revision_activity = await self._post_revision_activity(
            tuple(post.id for post in posts)
        )
        first_post = next((post for post in posts if post.post_number == 1), None)
        page_posts = tuple(
            self._page_post(
                post,
                modified_at=(
                    latest_datetime(post.created_at, post_revision_activity.get(post.id))
                    or post.created_at
                ),
            )
            for post in posts
        )
        description = topic_excerpt(topic, first_post)
        return SeoPageDocument(
            kind="topic",
            status_code=200,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                canonical_path,
                title=f"{topic.title} · {topic.board.name} · {identity.title}",
                description=description,
                og_type="article",
            ),
            heading=topic.title,
            intro=f"{topic.board.name}版块中的公开讨论，共 {topic.reply_count} 条回复。",
            links=(
                SeoPageLink(
                    path=f"/b/{encode_path_segment(topic.board.slug)}",
                    label=topic.board.name,
                    description=topic.board.description,
                ),
            ),
            posts=page_posts,
            site_structured_data=self._site_structured_data(identity, base_url),
            page_structured_data=(
                self._topic_structured_data(topic, page_posts, base_url)
                if first_post is not None
                else None
            ),
        )

    async def profile_page(self, user_id: str, base_url: str) -> SeoPageDocument:
        """Resolve a member route into a public, restricted, or missing document.

        ``user_id`` is the stable route ID and ``base_url`` the canonical origin.
        Only active profiles marked public contribute fields/schema; other
        existing profiles produce an empty noindex shell without writes.
        """

        user = await self._user_by_id(user_id)
        identity = await self._site_identity()
        path = f"/members/{encode_path_segment(user_id)}"
        if user is None or user.status == "deleted":
            return self._missing_document(identity, base_url, path)
        if user.status != "active" or user.profile_visibility != "public":
            return self._restricted_document(identity, base_url, path)

        topic_count = await self._public_topic_count_for_user(user.id)
        post_count = await self._public_post_count_for_user(user.id)
        topics = await self._public_topics(MAX_PROFILE_PAGE_TOPICS, author_id=user.id)
        display_name = user.display_name or user.username
        description = user.bio or (
            f"{display_name} 在{identity.title}发布了 {topic_count} 个公开主题"
            f"和 {post_count} 篇公开帖子。"
        )
        return SeoPageDocument(
            kind="profile",
            status_code=200,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                path,
                title=f"{display_name} 的公开档案 · {identity.title}",
                description=description,
            ),
            heading=display_name,
            intro=description,
            links=tuple(self._topic_link(topic) for topic in topics),
            site_structured_data=self._site_structured_data(identity, base_url),
            page_structured_data=self._profile_structured_data(
                user,
                topic_count=topic_count,
                post_count=post_count,
                base_url=base_url,
            ),
        )

    def build_sitemap_xml(self, urls: list[SitemapUrl]) -> str:
        """Serialize canonical sitemap entries with only loc and accurate lastmod.

        ``urls`` contains already filtered sitemap models. The returned UTF-8 XML
        string escapes dynamic values and has no side effects.
        """

        rows = ['<?xml version="1.0" encoding="UTF-8"?>']
        rows.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        for item in urls:
            rows.append("  <url>")
            rows.append(f"    <loc>{escape(item.loc)}</loc>")
            if item.lastmod is not None:
                rows.append(f"    <lastmod>{escape(format_datetime(item.lastmod))}</lastmod>")
            rows.append("  </url>")
        rows.append("</urlset>")
        return "\n".join(rows) + "\n"

    async def _public_boards(self, limit: int) -> list[Board]:
        """Return at most ``limit`` anonymous-public boards without relationships.

        The result is ordered for stable navigation and the query has no writes.
        """

        return list(
            await self.session.scalars(
                select(Board)
                .options(noload("*"))
                .where(Board.visibility == "public")
                .order_by(desc(Board.topic_count), Board.name)
                .limit(limit)
            )
        )

    async def _public_topics(
        self,
        limit: int,
        *,
        board_id: str | None = None,
        author_id: str | None = None,
    ) -> list[Topic]:
        """Return a bounded latest-topic list under optional board/author filters.

        ``limit`` caps output while ``board_id`` and ``author_id`` narrow it. The
        returned models contain no eagerly loaded posts and the query is read-only.
        """

        statement = (
            select(Topic)
            .options(noload("*"))
            .join(Topic.board)
            .where(
                Board.visibility == "public",
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.deleted_at.is_(None),
                Topic.merged_into_topic_id.is_(None),
            )
        )
        if board_id is not None:
            statement = statement.where(Topic.board_id == board_id)
        if author_id is not None:
            statement = statement.where(Topic.user_id == author_id)
        return list(
            await self.session.scalars(
                statement.order_by(desc(Topic.last_posted_at), desc(Topic.created_at)).limit(limit)
            )
        )

    async def _public_users(self, limit: int) -> list[User]:
        """Return at most ``limit`` active profiles explicitly visible to everyone.

        The stable, recently created result has no relationships and no write
        side effects. It deliberately avoids ``updated_at``, which also changes
        when private account activity such as last-seen time is written.
        """

        return list(
            await self.session.scalars(
                select(User)
                .options(noload("*"))
                .where(User.status == "active", User.profile_visibility == "public")
                .order_by(desc(User.created_at), User.username)
                .limit(limit)
            )
        )

    async def _board_by_slug(self, slug: str) -> Board | None:
        """Return the board with decoded ``slug`` regardless of visibility.

        The nullable result is used only to distinguish missing from restricted
        shell responses; related/private fields are not loaded and no writes occur.
        """

        return await self.session.scalar(
            select(Board).options(noload("*")).where(Board.slug == slug)
        )

    async def _public_board(self, slug: str) -> Board:
        """Return one public board or raise a privacy-preserving not-found error.

        ``slug`` is the decoded board identifier. The method has no write side
        effects and treats private and unknown boards identically.
        """

        board = await self._board_by_slug(slug)
        if board is None or board.visibility != "public":
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def _topic_by_id(self, topic_id: str) -> Topic | None:
        """Return one topic with only its board and author relationships loaded.

        ``topic_id`` is the stable primary key. The nullable result is read-only
        and exists to classify missing versus restricted document states.
        """

        return await self.session.scalar(
            select(Topic)
            .options(
                noload("*"),
                selectinload(Topic.board).noload("*"),
                selectinload(Topic.author).noload("*"),
            )
            .where(Topic.id == topic_id)
        )

    async def _public_topic(self, topic_id: str, *, follow_merge: bool = False) -> Topic:
        """Return one public canonical topic, optionally following one merge target.

        ``topic_id`` is the source ID and ``follow_merge`` enables legacy redirect
        resolution. Private, hidden, deleted, or unresolved merged topics raise
        ``NotFoundError``; the method never changes content or counters.
        """

        topic = await self._topic_by_id(topic_id)
        if topic is not None and topic.merged_into_topic_id is not None:
            if not follow_merge:
                raise NotFoundError("topic_not_found", "Topic not found")
            topic = await self._topic_by_id(topic.merged_into_topic_id)
        if topic is None or not self._topic_is_public(topic) or topic.merged_into_topic_id:
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    async def _visible_topic_posts(self, topic_id: str, *, limit: int) -> list[Post]:
        """Return up to ``limit`` undeleted posts with their public display authors.

        ``topic_id`` selects one already-public topic. Results are ordered by post
        number, do not load unrelated relationships, and never update view counts.
        """

        return list(
            await self.session.scalars(
                select(Post)
                .options(noload("*"), selectinload(Post.author).noload("*"))
                .where(Post.topic_id == topic_id, Post.deleted_at.is_(None))
                .order_by(Post.post_number)
                .limit(limit)
            )
        )

    async def _user_by_id(self, user_id: str) -> User | None:
        """Return the profile row for ``user_id`` without related private records.

        The nullable result supports response-state classification and the query
        performs no writes.
        """

        return await self.session.scalar(
            select(User).options(noload("*")).where(User.id == user_id)
        )

    async def _public_user(self, user_id: str) -> User:
        """Return one active profile marked public or raise ``NotFoundError``.

        ``user_id`` is the stable profile key. Members/private visibility is
        intentionally indistinguishable from absence to metadata callers.
        """

        user = await self._user_by_id(user_id)
        if user is None or user.status != "active" or user.profile_visibility != "public":
            raise NotFoundError("user_not_found", "User not found")
        return user

    async def _public_topic_count_for_user(self, user_id: str) -> int:
        """Count canonical public topics authored by ``user_id``.

        The integer return value excludes private, hidden, deleted, and merged
        topics and the aggregate query has no side effects.
        """

        return (
            await self.session.scalar(
                select(func.count(Topic.id))
                .join(Topic.board)
                .where(
                    Topic.user_id == user_id,
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                    Topic.status != "hidden",
                    Topic.merged_into_topic_id.is_(None),
                    Board.visibility == "public",
                )
            )
            or 0
        )

    async def _public_post_count_for_user(self, user_id: str) -> int:
        """Count undeleted posts by ``user_id`` inside canonical public topics.

        The aggregate return value reflects only anonymously visible content and
        the query does not mutate counters or business data.
        """

        return (
            await self.session.scalar(
                select(func.count(Post.id))
                .join(Post.topic)
                .join(Topic.board)
                .where(
                    Post.user_id == user_id,
                    Post.deleted_at.is_(None),
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                    Topic.status != "hidden",
                    Topic.merged_into_topic_id.is_(None),
                    Board.visibility == "public",
                )
            )
            or 0
        )

    async def _public_board_activity(self) -> dict[str, datetime]:
        """Return each public board's latest canonical public-topic activity.

        Keys are board IDs and values are latest post timestamps. The grouped
        query excludes non-indexable topics and has no side effects.
        """

        rows = await self.session.execute(
            select(Topic.board_id, func.max(Topic.last_posted_at))
            .join(Topic.board)
            .where(
                Board.visibility == "public",
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.deleted_at.is_(None),
                Topic.merged_into_topic_id.is_(None),
            )
            .group_by(Topic.board_id)
        )
        return {
            str(board_id): updated_at
            for board_id, updated_at in rows
            if updated_at is not None
        }

    async def _public_user_activity(self) -> dict[str, datetime]:
        """Return latest public content activity for each public-profile author.

        Keys are user IDs and values come from post creation, content revisions,
        or deletion. Engagement-counter-only writes are excluded. The aggregate
        queries are read-only and exclude non-indexable topic states.
        """

        created_rows = await self.session.execute(
            select(Post.user_id, func.max(Post.created_at))
            .join(Post.topic)
            .join(Topic.board)
            .join(User, User.id == Post.user_id)
            .where(
                User.status == "active",
                User.profile_visibility == "public",
                Post.deleted_at.is_(None),
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.merged_into_topic_id.is_(None),
                Board.visibility == "public",
            )
            .group_by(Post.user_id)
        )
        revision_rows = await self.session.execute(
            select(Post.user_id, func.max(PostRevision.created_at))
            .select_from(PostRevision)
            .join(Post, Post.id == PostRevision.post_id)
            .join(Topic, Topic.id == Post.topic_id)
            .join(Board, Board.id == Topic.board_id)
            .join(User, User.id == Post.user_id)
            .where(
                User.status == "active",
                User.profile_visibility == "public",
                Post.deleted_at.is_(None),
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.merged_into_topic_id.is_(None),
                Board.visibility == "public",
            )
            .group_by(Post.user_id)
        )
        deleted_rows = await self.session.execute(
            select(Post.user_id, func.max(Post.deleted_at))
            .join(Post.topic)
            .join(Topic.board)
            .join(User, User.id == Post.user_id)
            .where(
                User.status == "active",
                User.profile_visibility == "public",
                Post.deleted_at.is_not(None),
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.merged_into_topic_id.is_(None),
                Board.visibility == "public",
            )
            .group_by(Post.user_id)
        )
        return merge_activity_rows(created_rows, revision_rows, deleted_rows)

    async def _public_topic_content_activity(self) -> dict[str, datetime]:
        """Return latest post-content activity for each canonical public topic.

        Keys are topic IDs and values come from post creation, content revisions,
        or deletion. This avoids treating likes, votes, replies-to counters, or
        views as edits; all grouped queries are read-only.
        """

        created_rows = await self.session.execute(
            select(Post.topic_id, func.max(Post.created_at))
            .join(Post.topic)
            .join(Topic.board)
            .where(
                Post.deleted_at.is_(None),
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.merged_into_topic_id.is_(None),
                Board.visibility == "public",
            )
            .group_by(Post.topic_id)
        )
        revision_rows = await self.session.execute(
            select(Post.topic_id, func.max(PostRevision.created_at))
            .select_from(PostRevision)
            .join(Post, Post.id == PostRevision.post_id)
            .join(Topic, Topic.id == Post.topic_id)
            .join(Board, Board.id == Topic.board_id)
            .where(
                Post.deleted_at.is_(None),
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.merged_into_topic_id.is_(None),
                Board.visibility == "public",
            )
            .group_by(Post.topic_id)
        )
        deleted_rows = await self.session.execute(
            select(Post.topic_id, func.max(Post.deleted_at))
            .join(Post.topic)
            .join(Topic.board)
            .where(
                Post.deleted_at.is_not(None),
                Topic.deleted_at.is_(None),
                Topic.visibility == "public",
                Topic.status != "hidden",
                Topic.merged_into_topic_id.is_(None),
                Board.visibility == "public",
            )
            .group_by(Post.topic_id)
        )
        return merge_activity_rows(created_rows, revision_rows, deleted_rows)

    async def _post_revision_activity(
        self,
        post_ids: tuple[str, ...],
    ) -> dict[str, datetime]:
        """Return the latest true content-revision timestamp for ``post_ids``.

        The empty input returns immediately. Otherwise the grouped read uses the
        existing revision table and excludes engagement-only ``Post.updated_at``
        changes; the method has no write side effects.
        """

        if not post_ids:
            return {}
        rows = await self.session.execute(
            select(PostRevision.post_id, func.max(PostRevision.created_at))
            .where(PostRevision.post_id.in_(post_ids))
            .group_by(PostRevision.post_id)
        )
        return {
            str(post_id): revised_at
            for post_id, revised_at in rows
            if revised_at is not None
        }

    async def _site_identity(self) -> SeoSiteIdentity:
        """Read public site identity settings without creating missing defaults.

        The returned title, tagline, and protected logo path use code fallbacks
        when settings are absent or malformed. This GET-oriented query never
        invokes the admin default-seeding write path.
        """

        settings = list(
            await self.session.scalars(
                select(SiteSetting)
                .options(noload("*"))
                .where(
                    SiteSetting.public.is_(True),
                    SiteSetting.key.in_(PUBLIC_SITE_SETTING_KEYS),
                )
            )
        )
        values = {setting.key: setting.value for setting in settings}
        configured_logo = setting_text(values.get("brand_logo_url"), SITE_LOGO_FALLBACK)
        return SeoSiteIdentity(
            title=setting_text(values.get("site_title"), SITE_TITLE_FALLBACK),
            tagline=setting_text(values.get("site_tagline"), SITE_TAGLINE_FALLBACK),
            logo_url=(
                SITE_LOGO_FALLBACK
                if configured_logo in LEGACY_SITE_LOGO_URLS
                else configured_logo
            ),
        )

    def _topic_is_public(self, topic: Topic) -> bool:
        """Return whether loaded ``topic`` is anonymously indexable as canonical.

        The check includes topic, board, deletion, hidden, and merge state and has
        no side effects.
        """

        return (
            topic.deleted_at is None
            and topic.visibility == "public"
            and topic.status != "hidden"
            and topic.board.visibility == "public"
            and topic.merged_into_topic_id is None
        )

    def _site_meta(
        self,
        identity: SeoSiteIdentity,
        base_url: str,
        canonical_path: str,
        *,
        title: str,
        description: str,
        og_type: str = "website",
        robots: str = "index,follow",
    ) -> SeoMetaResponse:
        """Build one normalized metadata contract from trusted canonical inputs.

        ``identity`` supplies site naming, ``base_url`` and ``canonical_path``
        form absolute URLs, and keyword parameters control page copy/type/robots.
        The returned schema object is trimmed consistently and has no side effects.
        """

        _ = identity
        canonical_url = absolute_url(base_url, canonical_path)
        trimmed_description = truncate_text(description, 180)
        return SeoMetaResponse(
            title=title,
            description=trimmed_description,
            canonical_url=canonical_url,
            robots=robots,
            og_type=og_type,
            og_title=title,
            og_description=trimmed_description,
            og_url=canonical_url,
        )

    def _board_link(self, board: Board) -> SeoPageLink:
        """Map one public ``board`` model to a relative semantic navigation link.

        The return value contains display text and an escaped-at-render path; this
        pure mapping has no side effects.
        """

        return SeoPageLink(
            path=f"/b/{encode_path_segment(board.slug)}",
            label=board.name,
            description=truncate_text(board.description, 140),
        )

    def _topic_link(self, topic: Topic) -> SeoPageLink:
        """Map one canonical public ``topic`` to its stable relative link.

        The return value includes only public topic fields and this method has no
        side effects.
        """

        return SeoPageLink(
            path=topic_canonical_path(topic),
            label=topic.title,
            description=f"{topic.reply_count} 条回复 · {topic.view_count} 次浏览",
        )

    def _page_post(self, post: Post, *, modified_at: datetime) -> SeoPagePost:
        """Map one visible ``post`` to the renderer's typed public content record.

        ``modified_at`` is derived from content revisions, not engagement counters.
        The return value uses sanitized ``cooked_html`` and links only profiles
        visible to everyone; no mutation occurs.
        """

        author_path = (
            f"/members/{encode_path_segment(post.author.id)}"
            if post.author.status == "active" and post.author.profile_visibility == "public"
            else None
        )
        return SeoPagePost(
            author_name=post.author.username,
            author_path=author_path,
            published_at=post.created_at,
            modified_at=modified_at,
            plain_text=markdown_to_text(post.raw_md),
            content_html=post.cooked_html,
            post_number=post.post_number,
        )

    def _restricted_document(
        self,
        identity: SeoSiteIdentity,
        base_url: str,
        path: str,
    ) -> SeoPageDocument:
        """Build a 200 noindex shell for one existing but anonymous-restricted path.

        ``identity``, ``base_url``, and encoded ``path`` define generic shell
        metadata. The returned document includes no entity fields or page schema,
        allowing the authenticated SPA to take over without leaking content.
        """

        return SeoPageDocument(
            kind="restricted",
            status_code=200,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                path,
                title=f"受限内容 · {identity.title}",
                description="该内容需要相应访问权限，请在页面加载后登录查看。",
                robots="noindex,nofollow",
            ),
            heading="受限内容",
            intro="该内容需要相应访问权限。",
        )

    def _missing_document(
        self,
        identity: SeoSiteIdentity,
        base_url: str,
        path: str,
    ) -> SeoPageDocument:
        """Build a real 404 noindex shell without echoing missing entity data.

        ``identity``, ``base_url``, and encoded ``path`` supply generic metadata.
        The returned document contains no page schema or entity content and has no
        side effects.
        """

        return SeoPageDocument(
            kind="missing",
            status_code=404,
            site=identity,
            meta=self._site_meta(
                identity,
                base_url,
                path,
                title=f"页面不存在 · {identity.title}",
                description="请求的页面不存在或已被移除。",
                robots="noindex,nofollow",
            ),
            heading="页面不存在",
            intro="请求的页面不存在或已被移除。",
        )

    def _site_structured_data(self, identity: SeoSiteIdentity, base_url: str) -> JsonObject:
        """Build stable WebSite/Organization JSON-LD for a public document.

        ``identity`` contains public branding and ``base_url`` the canonical
        origin. The returned graph references the existing protected logo and has
        no side effects.
        """

        website_id = absolute_url(base_url, "/#website")
        organization_id = absolute_url(base_url, "/#organization")
        logo_url = absolute_asset_url(base_url, identity.logo_url) or absolute_url(
            base_url, SITE_LOGO_FALLBACK
        )
        name = site_brand_name(identity.title)
        alternate_names = site_alternate_names(identity.title, base_url)
        return {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "@id": website_id,
                    "url": absolute_url(base_url, "/"),
                    "name": name,
                    "alternateName": alternate_names,
                    "description": site_description(identity),
                    "inLanguage": "zh-CN",
                    "publisher": {"@id": organization_id},
                },
                {
                    "@type": "Organization",
                    "@id": organization_id,
                    "url": absolute_url(base_url, "/"),
                    "name": name,
                    "alternateName": alternate_names,
                    "logo": {"@type": "ImageObject", "url": logo_url},
                },
            ],
        }

    def _topic_structured_data(
        self,
        topic: Topic,
        posts: tuple[SeoPagePost, ...],
        base_url: str,
    ) -> JsonObject:
        """Build DiscussionForumPosting JSON-LD matching visible fallback posts.

        ``topic`` supplies public counters, ``posts`` is the bounded rendered post
        set, and ``base_url`` builds canonical URLs. The returned mapping includes
        no hidden/deleted content and has no side effects.
        """

        first_post = next(post for post in posts if post.post_number == 1)
        canonical_url = absolute_url(base_url, topic_canonical_path(topic))
        author: JsonObject = {
            "@type": "Person",
            "name": first_post.author_name,
        }
        if first_post.author_path is not None:
            author["url"] = absolute_url(base_url, first_post.author_path)

        comments: list[JsonObject] = []
        for post in posts:
            if post.post_number == 1:
                continue
            comment_author: JsonObject = {"@type": "Person", "name": post.author_name}
            if post.author_path is not None:
                comment_author["url"] = absolute_url(base_url, post.author_path)
            comments.append(
                {
                    "@type": "Comment",
                    "url": f"{canonical_url}#post-{post.post_number}",
                    "text": post.plain_text,
                    "datePublished": format_datetime(post.published_at),
                    "dateModified": format_datetime(post.modified_at),
                    "author": comment_author,
                }
            )

        schema: JsonObject = {
            "@context": "https://schema.org",
            "@type": "DiscussionForumPosting",
            "url": canonical_url,
            "mainEntityOfPage": canonical_url,
            "headline": topic.title,
            "text": first_post.plain_text,
            "articleBody": first_post.plain_text,
            "datePublished": format_datetime(first_post.published_at),
            "dateModified": format_datetime(
                latest_datetime(
                    topic.last_posted_at,
                    *(post.modified_at for post in posts),
                )
                or first_post.modified_at
            ),
            "author": author,
            "commentCount": topic.reply_count,
            "interactionStatistic": [
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/ViewAction",
                    "userInteractionCount": topic.view_count,
                },
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/LikeAction",
                    "userInteractionCount": topic.like_count,
                },
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/CommentAction",
                    "userInteractionCount": topic.reply_count,
                },
            ],
            "isPartOf": {
                "@type": "CollectionPage",
                "name": topic.board.name,
                "url": absolute_url(
                    base_url,
                    f"/b/{encode_path_segment(topic.board.slug)}",
                ),
            },
            "inLanguage": "zh-CN",
        }
        if comments:
            schema["comment"] = comments
        return schema

    def _profile_structured_data(
        self,
        user: User,
        *,
        topic_count: int,
        post_count: int,
        base_url: str,
    ) -> JsonObject:
        """Build ProfilePage/Person JSON-LD from one explicitly public profile.

        ``user`` supplies public fields, contribution counts summarize anonymous
        content, and ``base_url`` builds absolute URLs. The returned mapping has
        no side effects and must never be called for a non-public profile.
        """

        canonical_url = absolute_url(base_url, f"/members/{encode_path_segment(user.id)}")
        person: JsonObject = {
            "@type": "Person",
            "@id": f"{canonical_url}#person",
            "name": user.display_name or user.username,
            "alternateName": user.username,
            "url": canonical_url,
        }
        if user.bio:
            person["description"] = user.bio
        avatar_url = absolute_asset_url(base_url, user.avatar_url)
        if avatar_url is not None:
            person["image"] = avatar_url
        return {
            "@context": "https://schema.org",
            "@type": "ProfilePage",
            "url": canonical_url,
            "dateCreated": format_datetime(user.created_at),
            "mainEntity": person,
            "interactionStatistic": [
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/CreateAction",
                    "name": "公开主题",
                    "userInteractionCount": topic_count,
                },
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/WriteAction",
                    "name": "公开帖子",
                    "userInteractionCount": post_count,
                },
            ],
            "inLanguage": "zh-CN",
        }


def merge_activity_rows(
    *row_groups: Iterable[tuple[object, datetime | None]],
) -> dict[str, datetime]:
    """Merge grouped ``(entity_id, timestamp)`` rows by their latest timestamp.

    Each input iterable comes from a read-only creation, revision, or deletion
    aggregate. The returned mapping uses string IDs and UTC-comparable datetimes;
    the pure helper has no side effects.
    """

    activity: dict[str, datetime] = {}
    for rows in row_groups:
        for entity_id, changed_at in rows:
            if changed_at is None:
                continue
            key = str(entity_id)
            latest = latest_datetime(activity.get(key), changed_at)
            if latest is not None:
                activity[key] = latest
    return activity


def absolute_url(base_url: str, path: str) -> str:
    """Join canonical ``base_url`` and site-relative ``path`` without side effects."""

    base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def absolute_asset_url(base_url: str, value: str | None) -> str | None:
    """Return an absolute HTTP(S) asset URL for a configured relative/absolute value.

    ``base_url`` is canonical and ``value`` may be absent, root-relative, or an
    absolute HTTP(S) URL. Unsupported schemes return ``None``; no side effects occur.
    """

    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    if not parsed.scheme and not parsed.netloc and value.startswith("/"):
        return absolute_url(base_url, value)
    return None


def encode_path_segment(value: str) -> str:
    """Percent-encode one route ``value`` as an isolated path segment."""

    return quote(value, safe="")


def normalize_path(path: str) -> str:
    """Return a leading-slash path without query, fragment, or trailing slash."""

    value = (path or "/").strip()
    if not value.startswith("/"):
        value = f"/{value}"
    return value.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"


def topic_id_from_path(path: str) -> str | None:
    """Extract a topic ID from supported canonical or legacy ``path`` patterns."""

    topic_match = re.match(r"^/topics/([^/]+)(?:/[^/]+)?$", path)
    if topic_match:
        return topic_match.group(1)
    legacy_match = re.match(r"^/t/[^/]+/([^/]+)$", path)
    if legacy_match:
        return legacy_match.group(1)
    compact_match = re.match(r"^/p/([^/]+)$", path)
    if compact_match:
        return compact_match.group(1)
    return None


def topic_canonical_path(topic: Topic) -> str:
    """Return the stable canonical relative path for loaded ``topic``."""

    return f"/topics/{encode_path_segment(topic.id)}/{encode_path_segment(topic.slug)}"


def topic_excerpt(topic: Topic, first_post: Post | None) -> str:
    """Return a concise public description from ``first_post`` or topic context."""

    if first_post is None:
        return f"{topic.board.name} 中的公开主题：{topic.title}"
    return truncate_text(markdown_to_text(first_post.raw_md), 180)


def markdown_to_text(value: str) -> str:
    """Convert lightweight Markdown ``value`` to compact plain text for metadata/schema."""

    without_images = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", value)
    with_link_labels = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", without_images)
    without_code_fences = re.sub(r"```[^\n]*\n?(.*?)```", r"\1", with_link_labels, flags=re.S)
    without_inline_code = re.sub(r"`([^`]+)`", r"\1", without_code_fences)
    without_markup = re.sub(r"[*_>#\[\]()`~]", " ", without_inline_code)
    return " ".join(without_markup.split())


def truncate_text(value: str, limit: int) -> str:
    """Compact ``value`` to ``limit`` characters with a readable fallback/ellipsis."""

    compact = " ".join(value.split()).strip()
    if len(compact) <= limit:
        return compact or SITE_DESCRIPTION_FALLBACK
    return f"{compact[: max(0, limit - 1)].rstrip()}…"


def setting_text(value: object, fallback: str) -> str:
    """Return a non-empty string setting ``value`` or the supplied ``fallback``."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def site_description(identity: SeoSiteIdentity) -> str:
    """Return stable public-site description text from ``identity`` fields."""

    return f"{site_brand_name(identity.title)}：{identity.tagline}。浏览公开版块与可追溯讨论。"


def site_brand_name(public_title: str) -> str:
    """Return the unique bilingual SEO name for a configured public title.

    ``public_title`` is the administrator-visible site title. The returned name
    preserves it and appends the stable Latin brand exactly once; the helper has
    no side effects.
    """

    title = public_title.strip() or SITE_TITLE_FALLBACK
    if SITE_BRAND_NAME.casefold() in title.casefold():
        return title
    return f"{title} {SITE_BRAND_NAME}"


def site_alternate_names(public_title: str, base_url: str) -> list[str]:
    """Return deduplicated public-title, brand, and hostname aliases.

    ``public_title`` and canonical ``base_url`` identify legitimate brand names.
    The returned order prefers human-readable aliases before the lowercase host;
    invalid or duplicate values are omitted and no side effects occur.
    """

    primary_name = site_brand_name(public_title)
    hostname = (urlsplit(base_url).hostname or "").lower()
    candidates = (public_title.strip(), SITE_TITLE_FALLBACK, SITE_BRAND_NAME, hostname)
    aliases: list[str] = []
    seen = {primary_name.casefold()}
    for candidate in candidates:
        normalized = candidate.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        aliases.append(normalized)
    return aliases


def latest_datetime(*values: datetime | None) -> datetime | None:
    """Return the latest UTC-normalized timestamp among nullable ``values``."""

    present = [as_utc_datetime(value) for value in values if value is not None]
    return max(present) if present else None


def format_datetime(value: datetime) -> str:
    """Return ``value`` as a UTC ISO-8601 timestamp suitable for XML and JSON-LD."""

    return as_utc_datetime(value).isoformat().replace("+00:00", "Z")
