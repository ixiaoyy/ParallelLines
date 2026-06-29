from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote
from xml.sax.saxutils import escape

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.forum import Board, Topic
from app.models.user import User
from app.schemas.seo import SeoMetaResponse, SitemapUrl

MAX_SITEMAP_ITEMS_PER_TYPE = 1000
SITE_TITLE_FALLBACK = "平行线"
SITE_DESCRIPTION_FALLBACK = "让答案可追溯的中文技术论坛。"


@dataclass(frozen=True)
class LegacyTopicRedirect:
    status_code: int
    location: str


class SeoService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sitemap_urls(self, base_url: str) -> list[SitemapUrl]:
        public_boards = await self._public_boards(MAX_SITEMAP_ITEMS_PER_TYPE)
        public_topics = await self._public_topics(MAX_SITEMAP_ITEMS_PER_TYPE)
        public_users = await self._active_users(MAX_SITEMAP_ITEMS_PER_TYPE)
        urls = [
            SitemapUrl(loc=absolute_url(base_url, "/"), changefreq="daily", priority=1.0),
            SitemapUrl(
                loc=absolute_url(base_url, "/boards"),
                changefreq="daily",
                priority=0.8,
            ),
        ]
        urls.extend(
            SitemapUrl(
                loc=absolute_url(base_url, f"/b/{encode_path_segment(board.slug)}"),
                lastmod=board.updated_at,
                changefreq="daily",
                priority=0.7,
            )
            for board in public_boards
        )
        urls.extend(
            SitemapUrl(
                loc=absolute_url(
                    base_url,
                    f"/topics/{encode_path_segment(topic.id)}/{encode_path_segment(topic.slug)}",
                ),
                lastmod=max(topic.updated_at, topic.last_posted_at),
                changefreq="daily",
                priority=0.8,
            )
            for topic in public_topics
        )
        urls.extend(
            SitemapUrl(
                loc=absolute_url(base_url, f"/members/{encode_path_segment(user.id)}"),
                lastmod=user.updated_at,
                changefreq="weekly",
                priority=0.5,
            )
            for user in public_users
        )
        return urls

    async def robots_txt(self, base_url: str) -> str:
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
        normalized = normalize_path(path)
        if normalized in {"", "/"}:
            return self._site_meta(
                base_url,
                "/",
                title=SITE_TITLE_FALLBACK,
                description=SITE_DESCRIPTION_FALLBACK,
            )
        if normalized == "/boards":
            return self._site_meta(
                base_url,
                "/boards",
                title=f"全部版块 · {SITE_TITLE_FALLBACK}",
                description="浏览平行线公开技术版块、最新主题和精选讨论。",
            )
        if normalized.startswith("/b/"):
            slug = normalized.removeprefix("/b/").split("/", 1)[0]
            return await self.board_meta(slug, base_url)
        if normalized.startswith("/members/"):
            user_id = normalized.removeprefix("/members/").split("/", 1)[0]
            return await self.user_meta(user_id, base_url)
        topic_id = topic_id_from_path(normalized)
        if topic_id:
            return await self.topic_meta(topic_id, base_url)
        raise NotFoundError("seo_meta_not_found", "SEO metadata target not found")

    async def topic_meta(self, topic_id: str, base_url: str) -> SeoMetaResponse:
        topic = await self._public_topic(topic_id)
        description = topic_excerpt(topic)
        canonical_path = topic_canonical_path(topic)
        return self._site_meta(
            base_url,
            canonical_path,
            title=f"{topic.title} · {topic.board.name} · {SITE_TITLE_FALLBACK}",
            description=description,
            og_type="article",
        )

    async def board_meta(self, slug: str, base_url: str) -> SeoMetaResponse:
        board = await self._public_board(slug)
        return self._site_meta(
            base_url,
            f"/b/{encode_path_segment(board.slug)}",
            title=f"{board.name} · {SITE_TITLE_FALLBACK}",
            description=truncate_text(board.description, 180),
        )

    # user_meta 用途：按稳定用户 ID 生成公开成员页 SEO 元数据。
    # 关键参数：user_id 来自 `/members/{user_id}`，base_url 用于生成绝对 canonical URL。
    # 返回值/副作用：返回 SEO 响应对象，不写入数据库。
    async def user_meta(self, user_id: str, base_url: str) -> SeoMetaResponse:
        user = await self._active_user(user_id)
        topic_count = await self._public_topic_count_for_user(user.id)
        description = f"{user.username} 在平行线发布了 {topic_count} 个公开主题。"
        return self._site_meta(
            base_url,
            f"/members/{encode_path_segment(user.id)}",
            title=f"{user.username} 的公开档案 · {SITE_TITLE_FALLBACK}",
            description=description,
        )

    async def legacy_topic_redirect(
        self,
        topic_id: str,
        base_url: str,
    ) -> LegacyTopicRedirect:
        topic = await self._public_topic(topic_id, follow_merge=True)
        canonical_path = topic_canonical_path(topic)
        return LegacyTopicRedirect(status_code=301, location=absolute_url(base_url, canonical_path))

    def build_sitemap_xml(self, urls: list[SitemapUrl]) -> str:
        rows = ['<?xml version="1.0" encoding="UTF-8"?>']
        rows.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        for item in urls:
            rows.append("  <url>")
            rows.append(f"    <loc>{escape(item.loc)}</loc>")
            if item.lastmod is not None:
                rows.append(f"    <lastmod>{escape(item.lastmod.date().isoformat())}</lastmod>")
            rows.append(f"    <changefreq>{item.changefreq}</changefreq>")
            rows.append(f"    <priority>{item.priority:.1f}</priority>")
            rows.append("  </url>")
        rows.append("</urlset>")
        return "\n".join(rows) + "\n"

    async def _public_boards(self, limit: int) -> list[Board]:
        return list(
            await self.session.scalars(
                select(Board)
                .where(Board.visibility == "public")
                .order_by(desc(Board.topic_count), Board.name)
                .limit(limit)
            )
        )

    async def _public_topics(self, limit: int) -> list[Topic]:
        return list(
            await self.session.scalars(
                select(Topic)
                .join(Topic.board)
                .where(
                    Board.visibility == "public",
                    Topic.visibility == "public",
                    Topic.status != "hidden",
                    Topic.deleted_at.is_(None),
                    Topic.merged_into_topic_id.is_(None),
                )
                .order_by(desc(Topic.last_posted_at), desc(Topic.created_at))
                .limit(limit)
            )
        )

    async def _active_users(self, limit: int) -> list[User]:
        return list(
            await self.session.scalars(
                select(User)
                .where(User.status == "active")
                .order_by(desc(User.updated_at), User.username)
                .limit(limit)
            )
        )

    async def _public_board(self, slug: str) -> Board:
        board = await self.session.scalar(
            select(Board).where(Board.slug == slug, Board.visibility == "public")
        )
        if board is None:
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def _public_topic(self, topic_id: str, *, follow_merge: bool = False) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.posts),
            )
            .where(Topic.id == topic_id)
        )
        if topic is not None and follow_merge and topic.merged_into_topic_id:
            topic = await self.session.scalar(
                select(Topic)
                .options(
                    selectinload(Topic.board),
                    selectinload(Topic.author),
                    selectinload(Topic.posts),
                )
                .where(Topic.id == topic.merged_into_topic_id)
            )
        if (
            topic is None
            or topic.deleted_at is not None
            or topic.visibility != "public"
            or topic.status == "hidden"
            or topic.board.visibility != "public"
        ):
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    # _active_user 用途：按用户 ID 读取可索引的活跃用户。
    # 关键参数：user_id 为用户主键；找不到时抛出 NotFoundError。
    # 返回值/副作用：返回 User 模型，无写入副作用。
    async def _active_user(self, user_id: str) -> User:
        user = await self.session.scalar(
            select(User).where(User.id == user_id, User.status == "active")
        )
        if user is None:
            raise NotFoundError("user_not_found", "User not found")
        return user

    async def _public_topic_count_for_user(self, user_id: str) -> int:
        return (
            await self.session.scalar(
                select(func.count(Topic.id))
                .join(Topic.board)
                .where(
                    Topic.user_id == user_id,
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                    Topic.status != "hidden",
                    Board.visibility == "public",
                )
            )
            or 0
        )

    def _site_meta(
        self,
        base_url: str,
        canonical_path: str,
        *,
        title: str,
        description: str,
        og_type: str = "website",
    ) -> SeoMetaResponse:
        canonical_url = absolute_url(base_url, canonical_path)
        trimmed_description = truncate_text(description, 180)
        return SeoMetaResponse(
            title=title,
            description=trimmed_description,
            canonical_url=canonical_url,
            og_type=og_type,
            og_title=title,
            og_description=trimmed_description,
            og_url=canonical_url,
        )


def absolute_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def encode_path_segment(value: str) -> str:
    return quote(value, safe="")


def normalize_path(path: str) -> str:
    value = (path or "/").strip()
    if not value.startswith("/"):
        value = f"/{value}"
    return value.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"


def topic_id_from_path(path: str) -> str | None:
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
    return f"/topics/{encode_path_segment(topic.id)}/{encode_path_segment(topic.slug)}"


def topic_excerpt(topic: Topic) -> str:
    first_post = next((post for post in topic.posts if post.post_number == 1), None)
    if first_post is None:
        return f"{topic.board.name} 中的公开主题：{topic.title}"
    return truncate_text(markdown_to_text(first_post.raw_md), 180)


def markdown_to_text(value: str) -> str:
    without_code = re.sub(r"`{1,3}[^`]+`{1,3}", " ", value)
    without_markup = re.sub(r"[*_>#\[\]()`~]", " ", without_code)
    return " ".join(without_markup.split())


def truncate_text(value: str, limit: int) -> str:
    compact = " ".join(value.split()).strip()
    if len(compact) <= limit:
        return compact or SITE_DESCRIPTION_FALLBACK
    return f"{compact[: max(0, limit - 1)].rstrip()}…"
