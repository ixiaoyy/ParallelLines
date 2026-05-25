from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.ai import (
    ModerationAdviceRequest,
    ModerationAdviceResponse,
    SimilarTopicResponse,
    SimilarTopicsRequest,
    TopicAiSummaryResponse,
)
from app.schemas.common import ApiResponse
from app.services.ai import AiAssistantService

router = APIRouter(tags=["ai"])


@router.get("/topics/{topic_id}/ai-summary", response_model=ApiResponse[TopicAiSummaryResponse])
async def get_topic_ai_summary(
    topic_id: str,
    session: SessionDep,
) -> ApiResponse[TopicAiSummaryResponse]:
    return ApiResponse(data=await AiAssistantService(session).get_topic_summary(topic_id))


@router.post(
    "/topics/{topic_id}/ai-summary/refresh",
    response_model=ApiResponse[TopicAiSummaryResponse],
)
async def refresh_topic_ai_summary(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicAiSummaryResponse]:
    return ApiResponse(
        data=await AiAssistantService(session).refresh_topic_summary(topic_id, current_user)
    )


@router.post("/ai/similar-topics", response_model=ApiResponse[list[SimilarTopicResponse]])
async def suggest_similar_topics(
    payload: SimilarTopicsRequest,
    session: SessionDep,
) -> ApiResponse[list[SimilarTopicResponse]]:
    return ApiResponse(data=await AiAssistantService(session).suggest_similar_topics(payload))


@router.post("/ai/moderation-advice", response_model=ApiResponse[ModerationAdviceResponse])
async def moderation_ai_advice(
    payload: ModerationAdviceRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ModerationAdviceResponse]:
    return ApiResponse(
        data=await AiAssistantService(session).moderation_advice(payload, current_user)
    )
