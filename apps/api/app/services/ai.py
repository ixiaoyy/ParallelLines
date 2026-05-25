from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.permissions import is_global_moderator
from app.db.base import utcnow
from app.models.ai import AiTopicSummary
from app.models.forum import Board, Post, Topic
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.ai import (
    ModerationAdviceRequest,
    ModerationAdviceResponse,
    SimilarTopicResponse,
    SimilarTopicsRequest,
    TopicAiSummaryResponse,
)

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]{2,}", re.UNICODE)
HIGH_RISK_TERMS = {"自杀", "暴力", "仇恨", "泄露", "密码", "token", "攻击", "诈骗"}
MEDIUM_RISK_TERMS = {"辱骂", "广告", "spam", "垃圾", "政治", "成人", "引战"}


class AiAssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_topic_summary(self, topic_id: str) -> TopicAiSummaryResponse:
        summary = await self.session.scalar(
            select(AiTopicSummary).where(AiTopicSummary.topic_id == topic_id)
        )
        if summary is None:
            raise NotFoundError("ai_topic_summary_not_found", "AI topic summary not found")
        return TopicAiSummaryResponse.from_model(summary)

    async def refresh_topic_summary(
        self,
        topic_id: str,
        current_user: User,
    ) -> TopicAiSummaryResponse:
        topic = await self._topic_with_posts(topic_id)
        generated = build_topic_summary(topic)
        summary = await self.session.scalar(
            select(AiTopicSummary).where(AiTopicSummary.topic_id == topic.id)
        )
        now = utcnow()
        if summary is None:
            summary = AiTopicSummary(topic_id=topic.id, generated_at=now)
            self.session.add(summary)
        summary.summary = generated["summary"]
        summary.key_points = generated["key_points"]
        summary.key_post_ids = generated["key_post_ids"]
        summary.model_name = "local-deterministic-v1"
        summary.cost_units = generated["cost_units"]
        summary.refreshed_by_id = current_user.id
        summary.generated_at = now
        self.session.add(
            AuditLog(
                actor_id=current_user.id,
                action="ai_topic_summary_refreshed",
                target_type="topic",
                target_id=topic.id,
                board_id=topic.board_id,
                data={"cost_units": summary.cost_units, "model_name": summary.model_name},
                created_at=now,
            )
        )
        await self.session.commit()
        await self.session.refresh(summary)
        return TopicAiSummaryResponse.from_model(summary)

    async def suggest_similar_topics(
        self,
        payload: SimilarTopicsRequest,
    ) -> list[SimilarTopicResponse]:
        query_terms = set(tokenize(" ".join([payload.title, payload.raw_md, *payload.tags])))
        if not query_terms:
            return []
        topics = list(
            await self.session.scalars(
                select(Topic)
                .options(
                    selectinload(Topic.board), selectinload(Topic.posts), selectinload(Topic.tags)
                )
                .join(Board, Topic.board_id == Board.id)
                .where(
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                    Board.visibility == "public",
                )
                .order_by(desc(Topic.last_posted_at))
                .limit(200)
            )
        )
        scored: list[SimilarTopicResponse] = []
        for topic in topics:
            candidate_terms = set(
                tokenize(
                    " ".join(
                        [
                            topic.title,
                            " ".join(tag.name for tag in topic.tags),
                            first_post_text(topic),
                        ]
                    )
                )
            )
            matched = sorted(query_terms & candidate_terms)
            if not matched:
                continue
            score = round(
                len(matched) / max(1, len(query_terms)) + min(topic.reply_count, 20) / 100, 3
            )
            scored.append(
                SimilarTopicResponse(
                    id=topic.id,
                    title=topic.title,
                    slug=topic.slug,
                    board_slug=topic.board.slug,
                    board_name=topic.board.name,
                    score=score,
                    matched_terms=matched[:8],
                    excerpt=excerpt(first_post_text(topic), 160),
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[: payload.limit]

    async def moderation_advice(
        self,
        payload: ModerationAdviceRequest,
        current_user: User,
    ) -> ModerationAdviceResponse:
        if not is_global_moderator(current_user):
            raise PermissionDeniedError("moderator_required", "Moderator role required")
        text = " ".join([payload.title or "", payload.raw_text, payload.reason or ""]).lower()
        reasons: list[str] = []
        if any(term.lower() in text for term in HIGH_RISK_TERMS):
            risk = "high"
            reasons.append("命中高风险词或疑似敏感凭据/人身安全内容")
        elif any(term.lower() in text for term in MEDIUM_RISK_TERMS):
            risk = "medium"
            reasons.append("命中中风险词，建议人工复核语境")
        else:
            risk = "low"
            reasons.append("未命中首版高风险规则，仍需人工确认")
        actions = ["保留并继续观察", "请求作者补充上下文"]
        if risk == "medium":
            actions = ["隐藏前人工复核", "提醒作者修改措辞", "必要时合并到已有主题"]
        if risk == "high":
            actions = ["立即人工复核", "必要时临时隐藏", "不要自动封禁或删除"]
        return ModerationAdviceResponse(
            risk_level=risk,
            summary=excerpt(payload.raw_text, 220),
            reasons=reasons,
            suggested_actions=actions,
            requires_human_review=True,
            auto_action_allowed=False,
            cost_units=estimate_cost_units(payload.raw_text),
        )

    async def _topic_with_posts(self, topic_id: str) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(selectinload(Topic.posts), selectinload(Topic.board), selectinload(Topic.tags))
            .where(Topic.id == topic_id, Topic.deleted_at.is_(None))
        )
        if topic is None:
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic


def build_topic_summary(topic: Topic) -> dict[str, object]:
    visible_posts = sorted(
        [post for post in topic.posts if post.deleted_at is None],
        key=lambda post: post.post_number,
    )
    text = " ".join(post.raw_md for post in visible_posts)
    key_posts = visible_posts[:1] + [post for post in visible_posts[1:] if post.like_count > 0][:2]
    key_points = build_key_points(topic, visible_posts)
    return {
        "summary": (
            f"《{topic.title}》共有 {len(visible_posts)} 个楼层，"
            f"核心内容：{excerpt(text, 260)}"
        ),
        "key_points": key_points,
        "key_post_ids": [post.id for post in key_posts[:3]],
        "cost_units": estimate_cost_units(text),
    }


def build_key_points(topic: Topic, posts: list[Post]) -> list[str]:
    terms = Counter(tokenize(" ".join(post.raw_md for post in posts)))
    points = [
        f"主题位于 {topic.board.name}，标签：{', '.join(tag.name for tag in topic.tags) or '无'}"
    ]
    if topic.accepted_answer_post_id:
        points.append("该主题已有采纳答案，可优先阅读解决方案。")
    if terms:
        points.append("高频关键词：" + "、".join(term for term, _count in terms.most_common(6)))
    if len(posts) >= 5:
        points.append("讨论较长，建议从首帖和高赞回复开始阅读。")
    return points[:4]


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(value) if len(token.strip()) >= 2]


def first_post_text(topic: Topic) -> str:
    posts = sorted(topic.posts, key=lambda post: post.post_number)
    return posts[0].raw_md if posts else ""


def excerpt(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    return f"{cleaned[:limit]}…" if len(cleaned) > limit else cleaned


def estimate_cost_units(value: str) -> int:
    return max(1, min(20, len(value) // 1000 + 1))
