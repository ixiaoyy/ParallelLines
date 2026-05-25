from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.localization import TopicLocalizationResponse, TopicLocalizationUpdateRequest
from app.services.localization import LocalizationService

router = APIRouter(tags=["localization"])


@router.get(
    "/topics/{topic_id}/localizations/{locale}",
    response_model=ApiResponse[TopicLocalizationResponse],
)
async def get_topic_localization(
    topic_id: str,
    locale: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[TopicLocalizationResponse]:
    return ApiResponse(
        data=await LocalizationService(session).topic_localization(topic_id, locale, current_user)
    )


@router.put(
    "/topics/{topic_id}/localizations/{locale}",
    response_model=ApiResponse[TopicLocalizationResponse],
)
async def update_topic_localization(
    topic_id: str,
    locale: str,
    payload: TopicLocalizationUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicLocalizationResponse]:
    return ApiResponse(
        data=await LocalizationService(session).update_topic_localization(
            topic_id,
            locale,
            payload,
            current_user,
        )
    )
