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
            "在《打造第二大脑》中，作者提到自己曾因疾病导致表达能力退化。后来，"
            "他通过持续记录、整理信息，以及对生活习惯的不断调整，逐渐让混乱重新变得有序。\n\n"
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
        tags=["社区说明", "成长记录"],
    ),
    QualityPostSpec(
        key="community-guidelines",
        title="社区规范：理性交流、尊重原创与保护隐私",
        raw_md=(
            "# 社区规范：理性交流、尊重原创与保护隐私\n\n"
            "平行线希望长期保存有价值的记录，也希望每一次讨论都能让人更清晰、更安全、"
            "更愿意继续表达。这份规范来自《论坛规范》文档，用来帮助大家理解什么是被鼓励的"
            "高质量内容，以及平台如何处理服务责任与隐私保护。\n\n"
            "## 我们鼓励什么\n\n"
            "- **开源与分享**：欢迎原创技术文章、开源项目、踩坑记录、行业观察和业务理解。\n"
            "- **建设性讨论**：指出代码或观点问题时，请聚焦事实，给出可参考的方案、"
            "资料或文档链接。\n"
            "- **完整上下文**：提问时尽量补充报错信息、运行环境、复现步骤，"
            "并使用 Markdown 格式化代码。\n"
            "- **对事不对人**：讨论技术方案、产品判断和实践路径，不攻击表达者本身。\n\n"
            "## 我们不接受什么\n\n"
            "- 人身攻击、地域歧视、技术路线歧视、恶意引战、侮辱性言论或挂人。\n"
            "- 纯广告、无意义刷屏、重复灌水，以及与社区目标无关的敏感或跑题内容。\n"
            "- 抄袭、洗稿，或把他人文章、代码、开源成果据为己有；转载必须注明作者和出处。\n\n"
            "## 服务与责任边界\n\n"
            "- 请妥善保管账号，不转借、不售卖，并对账号下的行为负责。\n"
            "- 用户发布的原创内容，著作权仍归原作者所有；发布即表示授权社区在平台内进行展示、"
            "推荐和合规使用。\n"
            "- 社区中的代码、教程和架构方案仅供参考。用于生产环境或个人项目之前，"
            "请自行评估、测试"
            "和备份；因直接使用导致的数据丢失、系统故障或财产损失，平台与原作者不承担相应责任。\n"
            "- 对违反规范的内容，站方可进行修改、隐藏或删除；对违规账号可采取提醒、"
            "禁言、限制使用"
            "或封禁等措施。\n\n"
            "## 隐私与数据使用\n\n"
            "- 平台仅在必要范围内收集注册邮箱等账号信息、登录 IP、登录状态 Cookie、"
            "夜间模式偏好等信息。\n"
            "- 这些信息用于维护社区安全、反垃圾内容和优化阅读体验，不会出售给第三方商业机构。\n"
            "- 若未来接入 GitHub 登录、图片托管等第三方服务，"
            "相关数据流转将同时遵循第三方隐私政策。\n\n"
            "## 一起维护这个空间\n\n"
            "好的社区不是靠规则压出来的，而是靠每个人在发帖、回复、引用和质疑时多做一步确认。"
            "希望大家在这里既能大胆表达，也能被认真对待。"
        ),
        tags=["社区说明", "隐私保护"],
    ),
]

QUALITY_POST_AUTHOR_USERNAME = "多动脑子z"


async def sync_quality_posts(
    session: AsyncSession,
    *,
    board_slug: str = "announcements",
    author_username: str | None = QUALITY_POST_AUTHOR_USERNAME,
) -> list[Topic]:
    """Idempotently write pinned/featured starter posts into the current database."""

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
    elif board.owner_id is not None:
        author = await session.scalar(select(User).where(User.id == board.owner_id))
    else:
        author = await session.scalar(
            select(User).where(User.role == "admin", User.status == "active").order_by(User.id)
        )

    if author is None:
        raise RuntimeError(
            "No quality-post author is available; create user "
            f"{author_username or QUALITY_POST_AUTHOR_USERNAME!r} or pass --author-username."
        )
    return author


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
        .where(Topic.board_id == board.id, Topic.title == spec.title, Topic.deleted_at.is_(None))
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
