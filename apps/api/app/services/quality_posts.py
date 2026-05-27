from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.models.forum import Board, Post, Tag, Topic
from app.models.user import User
from app.schemas.forum import TopicCreateRequest
from app.services.forum import ForumService, normalize_tag_name, render_markdown, slugify
from app.services.search import SearchIndexService


@dataclass(frozen=True)
class QualityPostSpec:
    key: str
    title: str
    raw_md: str
    tags: list[str]
    pinned: bool = True
    featured: bool = True


QUALITY_POST_SPECS = [
    QualityPostSpec(
        key="forum-intent",
        title="论坛初衷：记录、连接与共同成长",
        raw_md=(
            "# 论坛初衷：记录、连接与共同成长\n\n"
            "这个论坛建立的初衷，是希望为每个人提供一个能够长期记录与连接的空间。\n\n"
            "你可以在这里保存灵感、整理知识、记录生活，也可以与他人交流观点，"
            "在讨论中不断完善自己的认知体系。\n\n"
            "**记录，本身就是一种力量。**\n\n"
            "它不仅帮助我们保存信息，更帮助我们理解自己。\n\n"
            "而成长，也很少是孤立完成的。一个人的坚持或许有限，但一群人的交流与陪伴，"
            "往往能够让改变发生得更快。\n\n"
            "## 你可以从这里开始\n\n"
            "- 保存一个突然出现的灵感，让它以后还能被找回。\n"
            "- 整理一段新学到的知识，把零散信息变成自己的理解。\n"
            "- 记录一次生活里的变化，给未来的自己留下线索。\n"
            "- 发起一个问题或观点，在交流中获得新的角度。\n\n"
            "希望这里能真正帮助到每一个愿意思考、表达与成长的人。"
        ),
        tags=["公告", "精华神帖"],
        pinned=False,
        featured=True,
    ),
    QualityPostSpec(
        key="community-guidelines",
        title="社区规范：友善交流、尊重原创与保护隐私",
        raw_md=(
            "# 社区规范：友善交流、尊重原创与保护隐私\n\n"
            "平行线希望长期保存有价值的记录，也希望每一次讨论都能让人更清晰、更安全、"
            "更愿意继续表达。\n\n"
            "## 我们鼓励什么\n\n"
            "- **真实表达**：欢迎原创经验、生活记录、读书感悟、工具分享和问题求助。\n"
            "- **建设性讨论**：指出问题时，请聚焦事实，给出可参考的方案或资料。\n"
            "- **完整上下文**：提问时尽量补充背景、已经尝试过什么、卡在哪里。\n"
            "- **对事不对人**：讨论观点和做法，不攻击表达者本身。\n\n"
            "## 我们不接受什么\n\n"
            "- 人身攻击、地域歧视、恶意引战、侮辱性言论或挂人。\n"
            "- 纯广告、无意义刷屏、重复灌水，以及明显跑题内容。\n"
            "- 抄袭、洗稿，或把他人文章、代码、开源成果据为己有；转载请注明作者和出处。\n\n"
            "## 一起维护这个空间\n\n"
            "好的社区不是靠规则压出来的，而是靠每个人在发帖、回复、引用和质疑时多做一步确认。"
            "希望大家在这里既能大胆表达，也能被认真对待。"
        ),
        tags=["公告", "发帖模板"],
        pinned=False,
        featured=True,
    ),
]

QUALITY_POST_AUTHOR_USERNAME = "多动脑子z"


async def sync_quality_posts(
    session: AsyncSession,
    *,
    board_slug: str = "announcements",
    author_username: str | None = QUALITY_POST_AUTHOR_USERNAME,
) -> list[Topic]:
    """Idempotently write official guide posts into the current database."""

    board = await session.scalar(select(Board).where(Board.slug == board_slug))
    if board is None:
        raise RuntimeError(f"Board {board_slug!r} does not exist; create the board before syncing.")

    author = await _resolve_author(session, board, author_username=author_username)
    forum = ForumService(session)
    topics: list[Topic] = []
    for spec in QUALITY_POST_SPECS:
        topics.append(await _upsert_quality_post(session, forum, board, author, spec))
    return topics


async def _resolve_author(
    session: AsyncSession,
    board: Board,
    *,
    author_username: str | None,
) -> User:
    if author_username:
        author = await session.scalar(select(User).where(User.username == author_username))
        if author is not None:
            return author
        if author_username != QUALITY_POST_AUTHOR_USERNAME:
            raise RuntimeError(
                "No quality-post author is available; create user "
                f"{author_username!r} or pass --author-username."
            )
    elif board.owner_id is not None:
        author = await session.scalar(select(User).where(User.id == board.owner_id))
    else:
        author = await session.scalar(
            select(User).where(User.role == "admin", User.status == "active").order_by(User.id)
        )

    if author is not None:
        return author

    if board.owner_id is not None:
        author = await session.scalar(select(User).where(User.id == board.owner_id))
        if author is not None:
            return author

    author = await session.scalar(
        select(User).where(User.role == "admin", User.status == "active").order_by(User.id)
    )
    if author is not None:
        return author

    raise RuntimeError(
        "No quality-post author is available; create user "
        f"{QUALITY_POST_AUTHOR_USERNAME!r} or pass --author-username."
    )


async def _upsert_quality_post(
    session: AsyncSession,
    forum: ForumService,
    board: Board,
    author: User,
    spec: QualityPostSpec,
) -> Topic:
    topic = await session.scalar(
        select(Topic)
        .options(selectinload(Topic.tags))
        .where(Topic.board_id == board.id, Topic.title == spec.title)
    )
    if topic is None:
        return await forum.create_topic(
            board.slug,
            TopicCreateRequest(
                title=spec.title,
                raw_md=spec.raw_md,
                tags=spec.tags,
                pinned=spec.pinned,
                featured=spec.featured,
            ),
            author,
            skip_spam_checks=True,
        )

    author_changed = topic.user_id != author.id
    topic.pinned = spec.pinned
    topic.featured = spec.featured
    topic.user_id = author.id
    topic.deleted_at = None
    topic.status = "open"
    topic.visibility = "public"
    await _sync_quality_tags(session, topic, spec.tags)
    first_post = await session.scalar(
        select(Post).where(Post.topic_id == topic.id, Post.post_number == 1)
    )
    if first_post is not None:
        first_post.user_id = author.id
        if first_post.raw_md != spec.raw_md.strip():
            first_post.raw_md = spec.raw_md.strip()
            first_post.cooked_html = render_markdown(first_post.raw_md)
            first_post.updated_at = utcnow()
            topic.updated_at = utcnow()
        elif author_changed:
            first_post.updated_at = utcnow()
            topic.updated_at = utcnow()

    await session.flush()
    await SearchIndexService(session).sync_topic(topic.id)
    await session.commit()
    return await forum.get_topic(topic.id, current_user=author)


async def _sync_quality_tags(
    session: AsyncSession,
    topic: Topic,
    tag_names: Iterable[str],
) -> None:
    desired_tags = await _get_or_create_tags(session, tag_names)
    current_tag_ids = {tag.id for tag in topic.tags}
    desired_tag_ids = {tag.id for tag in desired_tags}

    for tag in topic.tags:
        if tag.id not in desired_tag_ids:
            tag.topic_count = max(0, tag.topic_count - 1)
    for tag in desired_tags:
        if tag.id not in current_tag_ids:
            tag.topic_count += 1

    topic.tags = desired_tags


async def _get_or_create_tags(session: AsyncSession, tag_names: Iterable[str]) -> list[Tag]:
    normalized_names = []
    for tag_name in tag_names:
        normalized = normalize_tag_name(tag_name)
        if normalized and normalized not in normalized_names:
            normalized_names.append(normalized)

    tags: list[Tag] = []
    for name in normalized_names:
        slug = slugify(name, fallback_prefix="tag")[:64]
        tag = await session.scalar(select(Tag).where(or_(Tag.slug == slug, Tag.name == name)))
        if tag is None:
            tag = Tag(name=name, slug=slug, topic_count=0)
            session.add(tag)
            await session.flush()
        tags.append(tag)
    return tags
