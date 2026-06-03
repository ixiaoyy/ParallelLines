from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.exceptions import ValidationError
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.models.forum import Board, Post, Topic, TopicView
from app.models.interaction import Bookmark, Reaction
from app.models.user import User
from app.schemas.forum import PostCreateRequest
from app.services.forum import ForumService, calculate_hot_score
from app.services.interactions import InteractionService
from scripts.seed_persona_discussions import PERSONAS, rename_legacy_personas, upsert_personas

DEFAULT_SEED = "persona-engagement-v1"
LINK_RE = re.compile(r"https?://\S+|/api/v1/uploads/\S+|/uploads/\S+")
MARKDOWN_RE = re.compile(r"[#>*_`\\[\\](){}~-]+")
SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
QUESTION_MARKERS = ("？", "?", "怎么", "有没有", "能不能", "是否", "是不是", "求助", "大家")
ACTION_MARKERS = (
    "希望",
    "想",
    "准备",
    "打算",
    "可以",
    "需要",
    "应该",
    "会先",
    "我会",
    "试",
    "调整",
    "处理",
    "解决",
    "补充",
)
EXPRESSION_MARKERS = (
    "觉得",
    "发现",
    "怀疑",
    "担心",
    "在意",
    "困扰",
    "舒服",
    "焦虑",
    "紧张",
    "轻松",
    "有用",
    "麻烦",
    "问题",
    "细节",
)
CONCRETE_MARKERS = (
    "半小时",
    "十分钟",
    "两周",
    "每天",
    "每月",
    "周末",
    "工作",
    "外卖",
    "工具",
    "会员",
    "备注",
    "清单",
    "账单",
    "收藏",
)


@dataclass(frozen=True)
class TopicUnderstanding:
    """Store the extracted meaning signals from the poster's full first post.

    Key fields separate the poster's main point, concrete details, questions,
    intended actions, and ending emphasis. Return value: immutable analysis used
    by reply generation; it has no database side effects.
    """

    main_point: str
    detail_points: tuple[str, ...]
    question_points: tuple[str, ...]
    action_points: tuple[str, ...]
    ending_point: str


@dataclass(frozen=True)
class VoiceProfile:
    """Describe one visible reply style for a persona.

    Key fields: `tone` names the identity angle, `openers` and `closers` are
    sampled by `build_reply_body`. Return value: immutable data used only for
    seeded content generation; it has no database side effects.
    """

    tone: str
    openers: tuple[str, ...]
    closers: tuple[str, ...]


@dataclass(frozen=True)
class TopicDraft:
    """Hold the visible topic data needed to plan persona engagement.

    Key fields: `topic`, `first_post`, `text`, and `understanding` keep the ORM
    row plus normalized full-text signals. Side effect: none; this is a planning
    DTO.
    """

    topic: Topic
    first_post: Post
    text: str
    understanding: TopicUnderstanding


@dataclass(frozen=True)
class PlannedViewer:
    """Represent one deterministic topic view identity.

    Key fields: `label` is shown in dry-run output, `viewer_key` is the
    deduplicated `topic_views` key, and `authenticated` marks persona-backed
    views. Return value: immutable DTO with no side effects.
    """

    label: str
    viewer_key: str
    authenticated: bool


@dataclass
class EngagementStats:
    """Accumulate dry-run or write-run seed results.

    Key fields count planned and created views/likes/bookmarks/replies. Side effect:
    callers mutate the counters while processing topics, then serialize through
    `to_dict`.
    """

    dry_run: bool
    seed: str
    topics_seen: int = 0
    personas_seen: int = 0
    views_created: int = 0
    views_existing: int = 0
    user_views_planned: int = 0
    anonymous_views_planned: int = 0
    topic_likes_created: int = 0
    topic_likes_existing: int = 0
    post_likes_created: int = 0
    post_likes_existing: int = 0
    bookmarks_created: int = 0
    bookmarks_existing: int = 0
    replies_created: int = 0
    replies_existing: int = 0
    replies_failed: int = 0
    skipped_self_actions: int = 0
    topics: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe summary of the engagement run.

        Key parameters: none. Return value includes global counters and a
        compact per-topic plan. Side effect: none.
        """

        return {
            "dry_run": self.dry_run,
            "seed": self.seed,
            "topics_seen": self.topics_seen,
            "personas_seen": self.personas_seen,
            "views_created": self.views_created,
            "views_existing": self.views_existing,
            "user_views_planned": self.user_views_planned,
            "anonymous_views_planned": self.anonymous_views_planned,
            "topic_likes_created": self.topic_likes_created,
            "topic_likes_existing": self.topic_likes_existing,
            "post_likes_created": self.post_likes_created,
            "post_likes_existing": self.post_likes_existing,
            "bookmarks_created": self.bookmarks_created,
            "bookmarks_existing": self.bookmarks_existing,
            "replies_created": self.replies_created,
            "replies_existing": self.replies_existing,
            "replies_failed": self.replies_failed,
            "skipped_self_actions": self.skipped_self_actions,
            "topics": self.topics,
        }


VOICE_PROFILES: dict[str, VoiceProfile] = {
    "不吃香菜的猫": VoiceProfile(
        "生活感观察",
        ("我看到这里第一反应是", "这个点有点戳我", "这段读下来挺有画面感"),
        ("先记一笔，我回头也试试。", "感觉这个细节很真实。", "谢谢分享，挺像日常里会遇到的事。"),
    ),
    "一杯冰美式续命": VoiceProfile(
        "清醒打工人",
        ("作为一个靠咖啡续命的人", "我会先把它拆成可执行的小步骤", "这个思路挺适合工作日"),
        ("能省一点精力就是赚到。", "我可能会放进下周的待办里试一下。", "挺实用，不花哨。"),
    ),
    "外卖备注写错了": VoiceProfile(
        "提问型补充",
        ("我有个小问题", "如果换成我的情况", "这里是不是还可以补一个前提"),
        ("想听听楼主后续怎么处理。", "这个场景我也踩过坑。", "先收藏，等更多回复。"),
    ),
    "冰箱里还有半瓶可乐": VoiceProfile(
        "松弛随手记",
        (
            "读完有种半瓶可乐突然被想起来的感觉",
            "这个表达很轻，但我懂",
            "我喜欢这种不急着下结论的写法",
        ),
        ("有时候小事确实会把人拉回来。", "慢慢来就好。", "留个脚印。"),
    ),
    "刚下班别催": VoiceProfile(
        "边界感实践",
        ("这个我强烈同意", "我现在也更在意边界了", "这里最打动我的是"),
        (
            "不一定马上改变，但先意识到就挺重要。",
            "这类经验真的需要多一点。",
            "下班后看到这个很应景。",
        ),
    ),
    "雾里看山": VoiceProfile(
        "慢读反思",
        ("我会把这篇当成慢慢看的材料", "读到这里停了一下", "这个角度让我想到"),
        ("不急着评价，先放在脑子里。", "谢谢，把话说得很柔和。", "这种讨论适合慢慢延展开。"),
    ),
    "远山便利店": VoiceProfile(
        "工具派补充",
        ("从工具/方法角度看", "我会把这个拆成一个小清单", "这个点其实很适合做成固定流程"),
        ("以后需要时能直接拿来用。", "很朴素，但有用。", "我先放进收藏夹。"),
    ),
    "老槐": VoiceProfile(
        "老派稳重",
        ("这事看起来小，其实不小", "我赞同这个判断", "经验上看"),
        ("慢慢调整，比一下子用力更稳。", "说到底还是要回到具体生活里。", "这类提醒挺必要。"),
    ),
    "oldhuai": VoiceProfile(
        "路过补充",
        ("路过补一句", "我也注意到这个现象", "这个方向我觉得可以继续观察"),
        ("看看后面有没有更多案例。", "先留个标记。", "有点意思。"),
    ),
    "huai_07": VoiceProfile(
        "产品细节控",
        ("从体验上说", "我比较在意这里的细节", "这个反馈点很具体"),
        ("如果能再明确一步会更好。", "这个可以进优化清单。", "支持继续打磨。"),
    ),
    "Aki_慢慢来": VoiceProfile(
        "温和行动派",
        ("我喜欢这个不着急的方向", "先从很小的一步开始就好", "这个方法的好处是"),
        ("能开始就已经不错了。", "慢慢做，也是在做。", "我会试一个低成本版本。"),
    ),
    "momo-离线": VoiceProfile(
        "低电量旁观",
        ("离线状态下看这个很舒服", "我可能不会马上行动，但会记住", "这个说法让我松了一点"),
        ("先不卷结论。", "很适合周末慢慢想。", "谢谢，读完没那么紧绷。"),
    ),
    "kk不在线": VoiceProfile(
        "收藏型用户",
        ("这个我先收藏", "对我这种收藏夹爆满的人来说", "这里有个点值得留下"),
        ("之后整理时再翻出来。", "感觉会用得上。", "希望后面还有补充。"),
    ),
    "Nate_路过": VoiceProfile(
        "简短路过",
        ("路过说两句", "我看下来最有用的是", "这个点挺直接"),
        ("不展开了，支持一下。", "给个赞。", "等后续。"),
    ),
    "小K_再看看": VoiceProfile(
        "谨慎观望",
        ("我先持保留态度，但这个点可以看", "这个方向值得再观察", "如果后续能验证"),
        ("我会再看看。", "暂时先不下结论。", "期待更多例子。"),
    ),
    "rain_404": VoiceProfile(
        "轻微自嘲",
        ("我这种经常坚持失败的人也能看懂", "这个方法对我来说门槛不高", "如果不要求完美"),
        ("说不定真能坚持。", "先从失败率低的版本开始。", "感谢，给自己一点余地。"),
    ),
    "zzZ_醒了": VoiceProfile(
        "睡醒式感想",
        ("刚醒脑看到这个", "这段像是给早晨的人看的", "我理解成一句话就是"),
        ("明天试试看。", "希望我别又忘了。", "先给醒着的自己留个提醒。"),
    ),
    "beta路人": VoiceProfile(
        "省钱/风险意识",
        ("从成本角度看", "这个提醒挺适合定期复盘", "我会多看一眼隐藏成本"),
        ("省下来的不只是钱，还有注意力。", "这个坑越早发现越好。", "实用，感谢提醒。"),
    ),
    "loop_一下": VoiceProfile(
        "复盘迭代",
        ("我想把这个问题绕回来再看一遍", "如果拆成原因和行动", "这里其实有一个可迭代的点"),
        ("下次可以对照看看。", "这个讨论可以继续循环优化。", "先标记，后面复盘。"),
    ),
    "穿猫的靴子": VoiceProfile(
        "趋势观察",
        ("这个变化我也观察到了", "从趋势上看", "如果把它放到更长一点的时间里"),
        ("方向挺清楚的。", "之后应该还会有类似讨论。", "这个角度值得留意。"),
    ),
}

DEFAULT_REPLY_MODES = ("warm", "practical", "question", "calm")

PERSONA_REPLY_MODES: dict[str, tuple[str, ...]] = {
    "不吃香菜的猫": ("warm", "detail", "humor"),
    "一杯冰美式续命": ("practical", "calm", "sharp"),
    "外卖备注写错了": ("question", "practical", "self_mock"),
    "冰箱里还有半瓶可乐": ("humor", "warm", "slack"),
    "刚下班别催": ("boundary", "sharp", "calm"),
    "雾里看山": ("calm", "reflect", "warm"),
    "远山便利店": ("practical", "organize", "detail"),
    "老槐": ("calm", "sharp", "reflect"),
    "oldhuai": ("passing", "skeptical", "detail"),
    "huai_07": ("product", "sharp", "question"),
    "Aki_慢慢来": ("warm", "practical", "calm"),
    "momo-离线": ("slack", "calm", "warm"),
    "kk不在线": ("slack", "question", "practical"),
    "Nate_路过": ("passing", "short", "detail"),
    "小K_再看看": ("skeptical", "contrarian", "question"),
    "rain_404": ("self_mock", "practical", "warm"),
    "zzZ_醒了": ("humor", "slack", "short"),
    "beta路人": ("risk", "sharp", "practical"),
    "loop_一下": ("contrarian", "reflect", "organize"),
    "穿猫的靴子": ("trend", "interesting", "calm"),
}


# Parse CLI options for a deterministic persona engagement seed run.
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for dry-run or write-run engagement seeding.

    Key parameters: optional raw `argv` for tests. Return value is an argparse
    namespace consumed by `seed_engagement`. Side effect: none.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Seed persona views, likes, bookmarks, and contextual replies for public open topics."
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print the plan.")
    parser.add_argument("--seed", default=DEFAULT_SEED, help="Stable random seed namespace.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional topic limit for smoke runs.",
    )
    parser.add_argument("--view-min", type=int, default=8)
    parser.add_argument("--view-max", type=int, default=18)
    parser.add_argument("--topic-like-min", type=int, default=2)
    parser.add_argument("--topic-like-max", type=int, default=6)
    parser.add_argument("--post-like-min", type=int, default=1)
    parser.add_argument("--post-like-max", type=int, default=4)
    parser.add_argument("--bookmark-min", type=int, default=1)
    parser.add_argument("--bookmark-max", type=int, default=3)
    parser.add_argument(
        "--reply-min",
        type=int,
        default=0,
        help="Minimum contextual replies per topic; defaults to 0 for metrics-only seeding.",
    )
    parser.add_argument(
        "--reply-max",
        type=int,
        default=0,
        help="Maximum contextual replies per topic; raise this only when replies are desired.",
    )
    return parser.parse_args(argv)


# Open a database session and run the persona engagement workflow.
async def async_main(argv: Sequence[str] | None = None) -> None:
    """Run the engagement seed and print a JSON summary.

    Key parameters: optional raw `argv`. Return value: none. Side effect: writes
    views/likes/bookmarks/replies unless `--dry-run` is supplied.
    """

    configure_logging()
    args = parse_args(argv)
    async with AsyncSessionLocal() as session:
        result = await seed_engagement(session, args)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))


# Seed deterministic persona engagement against the current public topic set.
async def seed_engagement(session: AsyncSession, args: argparse.Namespace) -> EngagementStats:
    """Plan and optionally write persona views, likes, bookmarks, and replies.

    Key parameters: `session` is the active async DB session and `args` controls
    ranges/seed/dry-run. Return value is `EngagementStats`. Side effect: in
    write mode creates interactions and posts via service functions.
    """

    validate_ranges(args)
    await rename_legacy_personas(session, dry_run=args.dry_run)
    personas = await upsert_personas(session, dry_run=args.dry_run)
    if not args.dry_run:
        await session.commit()
    topics = await load_public_open_topics(session, limit=args.limit)
    stats = EngagementStats(dry_run=args.dry_run, seed=args.seed)
    stats.topics_seen = len(topics)
    stats.personas_seen = len(personas)
    persona_list = [personas[persona.username] for persona in PERSONAS]

    for draft in topics:
        await process_topic(session, args, draft, persona_list, stats)
    return stats


# Validate random-count ranges before doing any write work.
def validate_ranges(args: argparse.Namespace) -> None:
    """Validate configured random min/max counts.

    Key parameters: parsed CLI `args`. Return value: none. Side effect: raises
    `ValueError` for impossible ranges before database writes happen.
    """

    range_fields = (
        ("view", args.view_min, args.view_max),
        ("topic-like", args.topic_like_min, args.topic_like_max),
        ("post-like", args.post_like_min, args.post_like_max),
        ("bookmark", args.bookmark_min, args.bookmark_max),
        ("reply", args.reply_min, args.reply_max),
    )
    for label, minimum, maximum in range_fields:
        if minimum < 0 or maximum < minimum:
            raise ValueError(f"Invalid {label} range: {minimum}..{maximum}")


# Load only public, open, non-deleted topics that can receive ordinary replies.
async def load_public_open_topics(
    session: AsyncSession,
    *,
    limit: int | None,
) -> list[TopicDraft]:
    """Return current public open topics with their first visible post text.

    Key parameters: `limit` optionally caps the result for smoke runs. Return
    value is a list of `TopicDraft`. Side effect: none.
    """

    statement = (
        select(Topic)
        .join(Board, Board.id == Topic.board_id)
        .options(
            selectinload(Topic.board),
            selectinload(Topic.author),
            selectinload(Topic.tags),
            selectinload(Topic.posts).selectinload(Post.author),
        )
        .where(
            Topic.deleted_at.is_(None),
            Topic.status == "open",
            Topic.visibility != "private_message",
            Board.visibility == "public",
        )
        .order_by(Topic.created_at, Topic.id)
    )
    if limit:
        statement = statement.limit(limit)
    topics = list(await session.scalars(statement))
    drafts: list[TopicDraft] = []
    for topic in topics:
        visible_posts = sorted(
            [post for post in topic.posts if post.deleted_at is None],
            key=lambda post: post.post_number,
        )
        if not visible_posts:
            continue
        first_post = visible_posts[0]
        text = plain_text(f"{topic.title}\n{first_post.raw_md}")
        understanding = understand_topic(topic.title, first_post.raw_md)
        drafts.append(
            TopicDraft(topic=topic, first_post=first_post, text=text, understanding=understanding)
        )
    return drafts


# Process one topic's planned views, likes, bookmarks, and contextual replies.
async def process_topic(
    session: AsyncSession,
    args: argparse.Namespace,
    draft: TopicDraft,
    personas: Sequence[User],
    stats: EngagementStats,
) -> None:
    """Apply or count engagement for one topic.

    Key parameters: `draft` is the target topic data and `personas` are candidate
    actors. Return value: none. Side effect: may write views/interactions/replies
    and appends a per-topic summary to `stats`.
    """

    topic = draft.topic
    topic_rng = seeded_rng(args.seed, "topic", topic.id)
    non_author_personas = [persona for persona in personas if persona.id != topic.user_id]
    if len(non_author_personas) < 1:
        return

    viewers = sample_viewers(
        non_author_personas,
        topic_rng.randint(args.view_min, args.view_max),
        args.seed,
        topic.id,
    )
    topic_likers = sample_users(
        non_author_personas,
        topic_rng.randint(args.topic_like_min, args.topic_like_max),
        args.seed,
        "topic-like",
        topic.id,
    )
    bookmarkers = sample_users(
        non_author_personas,
        topic_rng.randint(args.bookmark_min, args.bookmark_max),
        args.seed,
        "bookmark",
        topic.id,
    )
    post_likers = sample_users(
        non_author_personas,
        topic_rng.randint(args.post_like_min, args.post_like_max),
        args.seed,
        "post-like",
        draft.first_post.id,
    )
    repliers = sample_users(
        non_author_personas,
        topic_rng.randint(args.reply_min, args.reply_max),
        args.seed,
        "reply",
        topic.id,
    )
    topic_summary = {
        "topic_id": topic.id,
        "title": topic.title,
        "board": topic.board.slug,
        "viewers": [viewer.label for viewer in viewers],
        "topic_likers": [user.username for user in topic_likers],
        "post_likers": [user.username for user in post_likers],
        "bookmarkers": [user.username for user in bookmarkers],
        "repliers": [user.username for user in repliers],
    }
    stats.topics.append(topic_summary)

    await apply_topic_views(session, args, topic, viewers, stats)
    await apply_topic_likes(session, args, topic, topic_likers, stats)
    await apply_post_likes(session, args, draft.first_post, post_likers, stats)
    await apply_bookmarks(session, args, topic, bookmarkers, stats)
    await apply_replies(session, args, draft, repliers, stats)
    if not args.dry_run:
        await recompute_topic_like_cache(session, topic.id)


# Create missing deduplicated topic views and refresh cached view counters.
async def apply_topic_views(
    session: AsyncSession,
    args: argparse.Namespace,
    topic: Topic,
    viewers: Sequence[PlannedViewer],
    stats: EngagementStats,
) -> None:
    """Create or count topic views for selected persona/anonymous viewers.

    Key parameters: target `topic` and planned `viewers`. Return value: none.
    Side effect: write mode inserts missing `topic_views` rows and updates
    `topics.view_count`/`hot_score` in the same session.
    """

    for viewer in viewers:
        if viewer.authenticated:
            stats.user_views_planned += 1
        else:
            stats.anonymous_views_planned += 1
        if await topic_view_exists(session, topic.id, viewer.viewer_key):
            stats.views_existing += 1
            continue
        stats.views_created += 1
        if not args.dry_run:
            session.add(TopicView(topic_id=topic.id, viewer_key=viewer.viewer_key))
            topic.view_count += 1
            topic.hot_score = calculate_hot_score(
                reply_count=topic.reply_count,
                like_count=topic.like_count,
                view_count=topic.view_count,
            )


# Create missing topic-level likes using the interaction service.
async def apply_topic_likes(
    session: AsyncSession,
    args: argparse.Namespace,
    topic: Topic,
    users: Sequence[User],
    stats: EngagementStats,
) -> None:
    """Create or count topic likes for selected persona users.

    Key parameters: `topic` target and `users` actors. Return value: none. Side
    effect: write mode calls `InteractionService.like_topic` for missing rows.
    """

    service = InteractionService(session)
    for user in users:
        if user.id == topic.user_id:
            stats.skipped_self_actions += 1
            continue
        if await reaction_exists(session, "topic", topic.id, user.id):
            stats.topic_likes_existing += 1
            continue
        stats.topic_likes_created += 1
        if not args.dry_run:
            await service.like_topic(topic.id, user)


# Create missing first-post likes using the interaction service.
async def apply_post_likes(
    session: AsyncSession,
    args: argparse.Namespace,
    post: Post,
    users: Sequence[User],
    stats: EngagementStats,
) -> None:
    """Create or count post likes for selected persona users.

    Key parameters: `post` target and `users` actors. Return value: none. Side
    effect: write mode calls `InteractionService.like_post` for missing rows.
    """

    service = InteractionService(session)
    for user in users:
        if user.id == post.user_id:
            stats.skipped_self_actions += 1
            continue
        if await reaction_exists(session, "post", post.id, user.id):
            stats.post_likes_existing += 1
            continue
        stats.post_likes_created += 1
        if not args.dry_run:
            await service.like_post(post.id, user)


# Create missing topic bookmarks using the interaction service.
async def apply_bookmarks(
    session: AsyncSession,
    args: argparse.Namespace,
    topic: Topic,
    users: Sequence[User],
    stats: EngagementStats,
) -> None:
    """Create or count topic bookmarks for selected persona users.

    Key parameters: `topic` target and `users` actors. Return value: none. Side
    effect: write mode calls `InteractionService.bookmark_topic` for missing rows.
    """

    service = InteractionService(session)
    for user in users:
        if user.id == topic.user_id:
            stats.skipped_self_actions += 1
            continue
        if await bookmark_exists(session, topic.id, user.id):
            stats.bookmarks_existing += 1
            continue
        stats.bookmarks_created += 1
        if not args.dry_run:
            await service.bookmark_topic(topic.id, user)


# Create missing contextual replies using the forum service.
async def apply_replies(
    session: AsyncSession,
    args: argparse.Namespace,
    draft: TopicDraft,
    users: Sequence[User],
    stats: EngagementStats,
) -> None:
    """Create or count contextual replies for selected persona users.

    Key parameters: `draft` target content and `users` actors. Return value: none.
    Side effect: write mode calls `ForumService.reply_to_topic` for missing rows.
    """

    service = ForumService(session)
    for index, user in enumerate(users, start=1):
        if user.id == draft.topic.user_id:
            stats.skipped_self_actions += 1
            continue
        reply = build_reply_body(
            draft,
            user,
            seeded_rng(args.seed, "reply-body", draft.topic.id, user.id, index),
        )
        if await reply_exists(session, draft.topic.id, user.id, reply):
            stats.replies_existing += 1
            continue
        stats.replies_created += 1
        if not args.dry_run:
            try:
                await service.reply_to_topic(
                    draft.topic.id,
                    PostCreateRequest(raw_md=reply),
                    user,
                    skip_spam_checks=True,
                )
            except ValidationError:
                stats.replies_failed += 1
                stats.replies_created = max(0, stats.replies_created - 1)
                await session.rollback()


# Build one natural-language reply from topic content and persona style.
def build_reply_body(draft: TopicDraft, user: User, rng: random.Random) -> str:
    """Generate a contextual Chinese reply for one persona and topic.

    Key parameters: `draft` contains actual title/body text and `user` selects a
    voice profile. Return value is Markdown text. Side effect: none.
    """

    profile = VOICE_PROFILES.get(
        user.username,
        VoiceProfile(
            "路过",
            ("我读完之后想到", "这个点挺值得聊", "先补一个小感受"),
            ("留个脚印。", "谢谢分享。", "继续关注。"),
        ),
    )
    kind = classify_topic(draft)
    signals = draft.understanding
    mode = select_reply_mode(user.username, kind, signals, rng)
    opener = rng.choice(profile.openers)
    closer = rng.choice(profile.closers)
    bridge = build_content_bridge(draft, signals, mode, rng)
    middle = topic_specific_sentence(kind, profile, signals, mode, rng)
    optional_question = optional_follow_up(mode, signals, rng)
    return f"{opener}，{bridge}{middle}\n\n{closer}{optional_question}"


# Pick a reply strategy from the persona identity and topic signals.
def select_reply_mode(
    username: str,
    kind: str,
    signals: TopicUnderstanding,
    rng: random.Random,
) -> str:
    """Return one deterministic-random speaking mode for this persona reply.

    Key parameters: persona username, topic kind, extracted `signals`, and RNG.
    Return value is a style key such as `humor`, `sharp`, or `slack`. Side
    effect: none.
    """

    modes = list(PERSONA_REPLY_MODES.get(username, DEFAULT_REPLY_MODES))
    if kind == "qna" and "question" not in modes:
        modes.append("question")
    if signals.question_points and "question" not in modes and rng.random() < 0.45:
        modes.append("question")
    if signals.action_points and "practical" not in modes and rng.random() < 0.35:
        modes.append("practical")
    return rng.choice(tuple(modes))


# Build the opening bridge from title-level reading into full-post signals.
def build_content_bridge(
    draft: TopicDraft,
    signals: TopicUnderstanding,
    mode: str,
    rng: random.Random,
) -> str:
    """Return a bridge that proves the reply read beyond the title.

    Key parameters: `draft`, extracted `signals`, style `mode`, and RNG. Return
    value is a sentence fragment ending with Chinese punctuation. Side effect:
    none.
    """

    title = compact(draft.topic.title, 28)
    main = choose_signal((signals.main_point,), rng, title)
    detail = choose_signal(signals.detail_points, rng, main)
    ending = choose_signal((signals.ending_point,), rng, detail)
    options = [
        f"我读完不是只看到标题「{title}」，更像是在说「{main}」，",
        f"前面「{detail}」和后面「{ending}」连起来看，",
        f"楼主的重点我理解成「{main}」，",
    ]
    if mode in {"contrarian", "skeptical"}:
        options.append(f"我先抬个小杠：只看「{detail}」还不够，")
    if mode in {"slack", "short", "passing"}:
        options.append(f"划水读完也能抓到一个点：{detail}，")
    if mode in {"practical", "organize", "product"}:
        options.append(f"如果要落地，我会先抓「{detail}」这个触发点，")
    return rng.choice(tuple(dict.fromkeys(options)))


# Classify the topic so replies can reference content with a matching angle.
def classify_topic(draft: TopicDraft) -> str:
    """Return a coarse topic kind for contextual reply templates.

    Key parameters: `draft` has board slug, title, tags, and body text. Return
    value is a string kind. Side effect: none.
    """

    board_slug = draft.topic.board.slug
    text = f"{draft.topic.title} {draft.text}".lower()
    if board_slug in {"qna", "questions", "support"} or "求助" in text or "怎么" in text:
        return "qna"
    if board_slug in {"reading"} or "读" in text or "书" in text:
        return "reading"
    if board_slug in {"benefits"} or "省钱" in text or "会员" in text or "优惠" in text:
        return "benefits"
    if board_slug in {"resources", "plugins"} or "工具" in text or "分享" in text:
        return "resources"
    if board_slug in {"health"} or "健康" in text or "运动" in text or "身体" in text:
        return "health"
    if board_slug in {"feedback"} or "建议" in text or "体验" in text:
        return "feedback"
    if board_slug in {"announcements", "official"}:
        return "announcement"
    if board_slug in {"news", "frontier"} or "趋势" in text:
        return "news"
    if board_slug in {"memory-notes"} or "每日" in text or "记录" in text:
        return "memory"
    return "lounge"


# Produce the middle sentence that ties the reply to the classified topic.
def topic_specific_sentence(
    kind: str,
    profile: VoiceProfile,
    signals: TopicUnderstanding,
    mode: str,
    rng: random.Random,
) -> str:
    """Return a topic-kind-specific sentence with persona tone.

    Key parameters: `kind`, `profile`, extracted `signals`, style `mode`, and
    seeded `rng`. Return value is one sentence fragment used by
    `build_reply_body`. Side effect: none.
    """

    main = choose_signal((signals.main_point,), rng, "这个问题")
    detail = choose_signal(signals.detail_points, rng, main)
    question = choose_signal(signals.question_points, rng, "")
    action = choose_signal(signals.action_points, rng, detail)
    topic_hint = topic_kind_hint(kind, detail, rng)
    mode_sentences = {
        "warm": f"我更愿意把它看成一次很具体的自我校准，尤其是「{detail}」这一段很真实。",
        "detail": f"细节上我会记住「{detail}」，这比泛泛说一个观点更能让人代入。",
        "humor": f"「{detail}」有点像生活突然拍桌提醒：别装没看见，先处理这个。",
        "practical": f"我会先围绕「{action}」做一个最小版本，别一上来就把方案搞复杂。",
        "organize": f"如果拆成清单，我会把「{main}」放第一项，再把其它条件往后排。",
        "question": f"你这个问题最好先限定场景，尤其是「{question or main}」这句，不然答案会飘。",
        "calm": f"冷静看，楼主不是急着要结论，而是在把「{main}」这件事讲清楚。",
        "reflect": f"它让我想回头看自己的类似经历：很多变化都是从「{detail}」这种小处开始的。",
        "sharp": f"说犀利一点，真正麻烦的不是「{detail}」，而是它反复出现却没人当回事。",
        "boundary": f"这里的边界感很明确：先承认「{main}」，再决定自己要不要继续被它牵着走。",
        "skeptical": f"我先保留一点怀疑：这个思路成立，但最好看「{action}」后能不能稳定复现。",
        "contrarian": f"抬杠一句：如果只停在「{detail}」，可能还不够，关键是后面怎么验证。",
        "slack": f"以划水视角看，我会先保留「{detail}」这个最低成本入口，能少折腾就少折腾。",
        "passing": f"路过看下来，这帖不是空泛感慨，至少「{detail}」是一个能接着聊的点。",
        "short": f"我抓到的重点是「{main}」。短评：有用，等后续。",
        "self_mock": f"我这种经常执行失败的人会先抓「{action}」，听起来失败率没那么高。",
        "product": f"从体验上看，「{detail}」就是触发点；如果后续补条件，判断会更准。",
        "risk": f"我会多看一眼隐藏成本：{detail}。这类小坑通常不吵，但会一直扣血。",
        "trend": f"有趣的是它不只是单个案例，「{detail}」背后像是使用习惯在慢慢转向。",
        "interesting": f"有意思的是，楼主讲的是「{main}」，但真正勾人的反而是「{detail}」。",
    }
    sentence = mode_sentences.get(mode, f"{topic_hint}，我会先抓住「{detail}」再往下看。")
    if topic_hint and rng.random() < 0.2:
        sentence = f"{topic_hint}；{sentence}"
    if rng.random() < 0.22:
        sentence = f"用“{profile.tone}”的视角看，{sentence}"
    return sentence


# Add a short optional tail that keeps the reply conversational.
def optional_follow_up(mode: str, signals: TopicUnderstanding, rng: random.Random) -> str:
    """Return an optional second paragraph for follow-up curiosity.

    Key parameters: style `mode`, extracted `signals`, and RNG. Return value is
    either an empty string or a Markdown paragraph. Side effect: none.
    """

    if rng.random() > 0.42:
        return ""
    question = choose_signal(signals.question_points, rng, "")
    action = choose_signal(signals.action_points, rng, signals.ending_point)
    if mode in {"question", "skeptical", "contrarian"} and question:
        return f"\n\n我更想看楼主后续怎么验证「{question}」这一点。"
    if mode in {"practical", "organize", "product"}:
        return f"\n\n如果后面有补充，可以直接说说「{action}」这一步实际效果。"
    return "\n\n楼主后面如果还有补充，我也想看看实际效果。"


# Read the whole first post and extract reusable meaning signals.
def understand_topic(title: str, raw_md: str) -> TopicUnderstanding:
    """Return a local full-post understanding used before persona replies.

    Key parameters: topic `title` and first-post Markdown `raw_md`. Return value
    is a `TopicUnderstanding` with main/detail/question/action signals. Side
    effect: none.
    """

    title_text = compact(title, 64)
    paragraphs = split_markdown_paragraphs(raw_md)
    if not paragraphs:
        paragraphs = (title_text or "这个话题",)

    paragraph_points: list[str] = []
    all_sentences: list[str] = []
    for paragraph in paragraphs:
        sentences = split_sentences(paragraph)
        all_sentences.extend(sentences)
        candidates = sentences or [paragraph]
        paragraph_points.append(max(candidates, key=content_signal_score))

    scored_sentences = sorted(all_sentences, key=content_signal_score, reverse=True)
    main_source = scored_sentences[0] if scored_sentences else paragraph_points[0]
    main_point = compact(main_source or title_text, 64)
    detail_candidates = [
        point for point in [*paragraph_points, *scored_sentences] if not is_question_sentence(point)
    ]
    if not detail_candidates:
        detail_candidates = [*paragraph_points, *scored_sentences]
    detail_points = tuple(
        point
        for point in unique_snippets(detail_candidates, limit=7)
        if point and point != main_point
    )
    if not detail_points:
        detail_points = (main_point,)

    question_points = unique_snippets(
        [sentence for sentence in all_sentences if is_question_sentence(sentence)],
        limit=4,
    )
    action_points = unique_snippets(
        [sentence for sentence in all_sentences if is_action_sentence(sentence)],
        limit=4,
    )
    final_sentences = split_sentences(paragraphs[-1])
    ending_point = compact(final_sentences[-1] if final_sentences else paragraphs[-1], 64)
    return TopicUnderstanding(
        main_point=main_point,
        detail_points=detail_points,
        question_points=question_points,
        action_points=action_points,
        ending_point=ending_point,
    )


# Split Markdown into normalized paragraphs so later paragraphs are not ignored.
def split_markdown_paragraphs(raw_md: str) -> tuple[str, ...]:
    """Return non-empty plain-text paragraphs from Markdown.

    Key parameter: raw Markdown from the first post. Return value preserves
    paragraph order after whitespace/link/Markdown cleanup. Side effect: none.
    """

    paragraphs = []
    for block in re.split(r"\n\s*\n+", raw_md):
        paragraph = plain_text(block)
        if paragraph:
            paragraphs.append(paragraph)
    return tuple(paragraphs)


# Split normalized text into Chinese/English-ish sentence candidates.
def split_sentences(text: str) -> list[str]:
    """Return compact sentence candidates from normalized text.

    Key parameter: text from a paragraph or title. Return value is an ordered
    list of non-empty sentence strings. Side effect: none.
    """

    normalized = plain_text(text)
    if not normalized:
        return []
    sentences = [plain_text(match.group(0)) for match in SENTENCE_RE.finditer(normalized)]
    sentences = [sentence for sentence in sentences if sentence]
    return sentences or [normalized]


# Score a sentence by how likely it captures the poster's real expression.
def content_signal_score(sentence: str) -> int:
    """Return a deterministic score for choosing representative post signals.

    Key parameter: one candidate sentence. Return value is a higher-is-better
    integer based on length, concrete detail, action, and emotion markers. Side
    effect: none.
    """

    normalized = plain_text(sentence)
    length = len(normalized)
    score = min(length, 90)
    if 12 <= length <= 90:
        score += 30
    if length < 8:
        score -= 25
    if is_question_sentence(normalized):
        score += 18
    if is_action_sentence(normalized):
        score += 16
    if contains_any(normalized, EXPRESSION_MARKERS):
        score += 14
    if contains_any(normalized, CONCRETE_MARKERS):
        score += 12
    if re.search(r"\d|[一二三四五六七八九十两半]+(天|周|月|年|分钟|小时|件|条|杯|次)", normalized):
        score += 10
    return score


# Detect whether a sentence carries an explicit question or request.
def is_question_sentence(sentence: str) -> bool:
    """Return whether `sentence` looks like a question from the poster.

    Key parameter: normalized or raw sentence text. Return value is boolean.
    Side effect: none.
    """

    return contains_any(sentence, QUESTION_MARKERS)


# Detect whether a sentence describes intended action or desired next step.
def is_action_sentence(sentence: str) -> bool:
    """Return whether `sentence` contains an action/need marker.

    Key parameter: normalized or raw sentence text. Return value is boolean.
    Side effect: none.
    """

    return contains_any(sentence, ACTION_MARKERS)


# Check if any configured marker appears in a candidate sentence.
def contains_any(value: str, markers: Sequence[str]) -> bool:
    """Return true when any marker is present in `value`.

    Key parameters: candidate text and marker sequence. Return value is boolean.
    Side effect: none.
    """

    return any(marker in value for marker in markers)


# Choose one non-empty signal with a seeded RNG and safe fallback.
def choose_signal(values: Sequence[str], rng: random.Random, fallback: str) -> str:
    """Return one signal from `values`, or `fallback` when no signal exists.

    Key parameters: candidate strings, seeded RNG, and fallback text. Return
    value is a compact string. Side effect: none.
    """

    candidates = [compact(value, 58) for value in values if value]
    if not candidates:
        return compact(fallback, 58)
    return rng.choice(candidates)


# De-duplicate snippets while keeping their original reading order.
def unique_snippets(values: Sequence[str], *, limit: int) -> tuple[str, ...]:
    """Return compact unique snippets from `values`.

    Key parameters: ordered strings and maximum result `limit`. Return value is
    a tuple preserving first occurrence order. Side effect: none.
    """

    snippets: list[str] = []
    seen: set[str] = set()
    for value in values:
        snippet = compact(value, 58)
        key = snippet.rstrip("。！？!?；;，,")
        if not key or key in seen:
            continue
        snippets.append(snippet)
        seen.add(key)
        if len(snippets) >= limit:
            break
    return tuple(snippets)


# Provide a small board/kind hint without overriding persona style.
def topic_kind_hint(kind: str, detail: str, rng: random.Random) -> str:
    """Return a concise topic-kind hint tied to the selected detail.

    Key parameters: classified `kind`, selected `detail`, and RNG. Return value
    may be empty when no extra hint is useful. Side effect: none.
    """

    hints = {
        "qna": ("这类求助最怕条件互相打架", "先把需求优先级排出来会更清楚"),
        "reading": ("慢读的价值在于留下自己的理解", "它更像一个对照经验的入口"),
        "benefits": ("省钱帖最关键的是先确认真实需要", "隐藏成本往往比优惠本身更重要"),
        "resources": ("工具帖最好按场景归类", "这种内容的价值在于后续可复用"),
        "health": ("健康调整贵在不打断生活节奏", "身体信号通常藏在小习惯里"),
        "feedback": ("反馈越具体越容易验证", "这个体验点后面适合补触发条件"),
        "announcement": ("规则先讲边界会更友好", "说明类内容最好配具体例子"),
        "news": ("趋势判断需要再观察一段时间", "它背后可能是使用习惯在变"),
        "memory": (f"「{detail}」像记录里亮了一下的地方", "这类记录适合过一阵子回看"),
        "lounge": ("它胜在真实，不用拔高", "这种小秩序会慢慢影响状态"),
    }
    pool = hints.get(kind)
    if not pool:
        return ""
    return rng.choice(pool)


# Check whether a topic view row already exists for idempotent dry-runs and writes.
async def topic_view_exists(session: AsyncSession, topic_id: str, viewer_key: str) -> bool:
    """Return whether a planned viewer has already counted this topic.

    Key parameters: topic id and hashed `viewer_key`. Return value is boolean.
    Side effect: none.
    """

    existing = await session.scalar(
        select(TopicView.id).where(
            TopicView.topic_id == topic_id,
            TopicView.viewer_key == viewer_key,
        )
    )
    return existing is not None


# Check whether a reaction row already exists for idempotent dry-runs and writes.
async def reaction_exists(
    session: AsyncSession,
    target_type: str,
    target_id: str,
    user_id: str,
) -> bool:
    """Return whether the persona already liked a topic or post.

    Key parameters identify the reaction unique key. Return value is boolean.
    Side effect: none.
    """

    existing = await session.scalar(
        select(Reaction.id).where(
            Reaction.target_type == target_type,
            Reaction.target_id == target_id,
            Reaction.user_id == user_id,
            Reaction.type == "like",
        )
    )
    return existing is not None


# Check whether a topic bookmark row already exists for this persona.
async def bookmark_exists(session: AsyncSession, topic_id: str, user_id: str) -> bool:
    """Return whether the persona already bookmarked the topic.

    Key parameters: topic id and actor user id. Return value is boolean. Side
    effect: none.
    """

    existing = await session.scalar(
        select(Bookmark.id).where(
            Bookmark.target_type == "topic",
            Bookmark.target_id == topic_id,
            Bookmark.user_id == user_id,
        )
    )
    return existing is not None


# Check for an identical persona reply to keep repeated runs idempotent.
async def reply_exists(session: AsyncSession, topic_id: str, user_id: str, raw_md: str) -> bool:
    """Return whether the same persona reply text already exists in the topic.

    Key parameters identify topic, persona, and exact generated Markdown. Return
    value is boolean. Side effect: none.
    """

    existing = await session.scalar(
        select(Post.id).where(
            Post.topic_id == topic_id,
            Post.user_id == user_id,
            Post.raw_md == raw_md,
            Post.deleted_at.is_(None),
        )
    )
    return existing is not None


# Recompute topic counter caches after mixed view/topic-like/post-like writes.
async def recompute_topic_like_cache(session: AsyncSession, topic_id: str) -> None:
    """Refresh a topic's aggregate view/like count and hot score from rows.

    Key parameters: target `topic_id`. Return value: none. Side effect: updates
    `topics.view_count`/`like_count`/`hot_score` and commits the correction.
    """

    topic = await session.get(Topic, topic_id)
    if topic is None:
        return
    post_like_count = await session.scalar(
        select(func.count(Reaction.id))
        .join(Post, Post.id == Reaction.target_id)
        .where(
            Reaction.target_type == "post",
            Reaction.type == "like",
            Post.topic_id == topic_id,
            Post.deleted_at.is_(None),
        )
    )
    topic_like_count = await session.scalar(
        select(func.count(Reaction.id)).where(
            Reaction.target_type == "topic",
            Reaction.target_id == topic_id,
            Reaction.type == "like",
        )
    )
    view_count = await session.scalar(
        select(func.count(TopicView.id)).where(TopicView.topic_id == topic_id)
    )
    topic.view_count = int(view_count or 0)
    topic.like_count = int(post_like_count or 0) + int(topic_like_count or 0)
    topic.hot_score = calculate_hot_score(
        reply_count=topic.reply_count,
        like_count=topic.like_count,
        view_count=topic.view_count,
    )
    await session.commit()


# Sample authenticated personas first, then deterministic anonymous visitors.
def sample_viewers(
    users: Sequence[User],
    count: int,
    seed: str,
    topic_id: str,
) -> list[PlannedViewer]:
    """Return deterministic topic-view identities for one topic.

    Key parameters: candidate persona `users`, target `count`, seed namespace,
    and `topic_id`. Return value includes persona-backed and anonymous viewers.
    Side effect: none.
    """

    if count <= 0:
        return []
    user_viewers = [
        PlannedViewer(
            label=f"user:{user.username}",
            viewer_key=viewer_key_for_user(user),
            authenticated=True,
        )
        for user in sample_users(users, min(count, len(users)), seed, "view-user", topic_id)
    ]
    anonymous_count = max(0, count - len(user_viewers))
    anonymous_viewers = [
        PlannedViewer(
            label=f"anon:{index}",
            viewer_key=viewer_key_for_visitor(seed, topic_id, index),
            authenticated=False,
        )
        for index in range(1, anonymous_count + 1)
    ]
    return [*user_viewers, *anonymous_viewers]


# Build the same logged-in viewer hash shape as ForumService._topic_viewer_key.
def viewer_key_for_user(user: User) -> str:
    """Return the persisted dedupe key for an authenticated persona view.

    Key parameter: persona user row. Return value matches the `user:<sha256>`
    format used by the topic detail view service. Side effect: none.
    """

    digest = hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()
    return f"user:{digest}"


# Build a stable anonymous visitor hash shape for seeded topic views.
def viewer_key_for_visitor(seed: str, topic_id: str, index: int) -> str:
    """Return the persisted dedupe key for one anonymous seeded view.

    Key parameters identify the seed namespace, topic, and ordinal. Return
    value matches the `anon:<sha256>` format used by the topic detail service.
    Side effect: none.
    """

    visitor_id = f"seed-{seed}-{topic_id}-{index}"
    digest = hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()
    return f"anon:{digest}"


# Sample persona users with a deterministic order for one topic/action.
def sample_users(
    users: Sequence[User],
    count: int,
    seed: str,
    action: str,
    target_id: str,
) -> list[User]:
    """Return a deterministic pseudo-random user sample.

    Key parameters: candidate `users`, target `count`, and seed tuple. Return
    value is a stable random list. Side effect: none.
    """

    if not users or count <= 0:
        return []
    shuffled = list(users)
    seeded_rng(seed, action, target_id).shuffle(shuffled)
    return shuffled[: min(count, len(shuffled))]


# Build a stable RNG from seed parts so runs are repeatable.
def seeded_rng(*parts: object) -> random.Random:
    """Create a deterministic random generator from arbitrary seed parts.

    Key parameters: seed namespace parts. Return value is `random.Random`. Side
    effect: none.
    """

    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


# Convert Markdown-ish source text into a compact plain text basis.
def plain_text(value: str) -> str:
    """Normalize Markdown/source text into a compact plain text string.

    Key parameters: raw title/body text. Return value is whitespace-normalized
    text for snippets. Side effect: none.
    """

    without_links = LINK_RE.sub("", value)
    without_markdown = MARKDOWN_RE.sub("", without_links)
    return " ".join(without_markdown.split())


# Shorten text for natural snippets without cutting into empty output.
def compact(value: str, limit: int) -> str:
    """Return a short, ellipsis-trimmed text snippet.

    Key parameters: `value` and maximum visible character count. Return value is
    a non-empty snippet when possible. Side effect: none.
    """

    normalized = plain_text(value)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}…"


# Reconcile all public topic counters after a bulk seed run.
async def recompute_all_public_counters(session: AsyncSession) -> None:
    """Refresh cached post/topic counts for public topics touched by seed data.

    Key parameters: active DB `session`. Return value: none. Side effect: updates
    post like counts, topic reply/like/hot counters, and commits.
    """

    view_rows = await session.execute(
        select(TopicView.topic_id, func.count(TopicView.id)).group_by(TopicView.topic_id)
    )
    view_counts = {str(topic_id): int(count) for topic_id, count in view_rows.all()}
    post_like_rows = await session.execute(
        select(Reaction.target_id, func.count(Reaction.id))
        .where(Reaction.target_type == "post", Reaction.type == "like")
        .group_by(Reaction.target_id)
    )
    post_like_counts = {str(post_id): int(count) for post_id, count in post_like_rows.all()}
    posts = list(await session.scalars(select(Post).where(Post.deleted_at.is_(None))))
    for post in posts:
        post.like_count = post_like_counts.get(post.id, 0)

    topic_rows = list(
        await session.scalars(
            select(Topic).where(Topic.deleted_at.is_(None), Topic.visibility != "private_message")
        )
    )
    topic_like_rows = await session.execute(
        select(Reaction.target_id, func.count(Reaction.id))
        .where(Reaction.target_type == "topic", Reaction.type == "like")
        .group_by(Reaction.target_id)
    )
    topic_like_counts = {str(topic_id): int(count) for topic_id, count in topic_like_rows.all()}
    for topic in topic_rows:
        visible_posts = [post for post in posts if post.topic_id == topic.id]
        topic.reply_count = max(0, len(visible_posts) - 1)
        topic.view_count = view_counts.get(topic.id, 0)
        topic.like_count = topic_like_counts.get(topic.id, 0) + sum(
            post.like_count for post in visible_posts
        )
        topic.hot_score = calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
    await session.commit()


# CLI entry point for the persona engagement seed script.
def main() -> None:
    """Run `async_main` under asyncio for command-line usage.

    Key parameters: none. Return value: none. Side effect: may write seed data
    depending on CLI flags.
    """

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
