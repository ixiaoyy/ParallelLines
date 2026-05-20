from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    BoardInviteCreateRequest,
    BoardInviteResponse,
    BoardResponse,
    MyBoardInvitesResponse,
)
from app.services.forum import ForumService

router = APIRouter(prefix="/invites", tags=["invites"])


@router.get("", response_model=ApiResponse[MyBoardInvitesResponse])
async def list_my_invites(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[MyBoardInvitesResponse]:
    received, managed, owned_boards = await ForumService(session).list_my_board_invites(
        current_user
    )
    return ApiResponse(
        data=MyBoardInvitesResponse(
            received=[BoardInviteResponse.from_model(invite) for invite in received],
            managed=[BoardInviteResponse.from_model(invite) for invite in managed],
            owned_boards=[BoardResponse.model_validate(board) for board in owned_boards],
        )
    )


@router.post(
    "",
    response_model=ApiResponse[BoardInviteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    payload: BoardInviteCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardInviteResponse]:
    invitation = await ForumService(session).create_board_invite(payload, current_user)
    return ApiResponse(data=BoardInviteResponse.from_model(invitation))


@router.put("/{invite_id}/accept", response_model=ApiResponse[BoardInviteResponse])
async def accept_invite(
    invite_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardInviteResponse]:
    invitation = await ForumService(session).accept_board_invite(invite_id, current_user)
    return ApiResponse(data=BoardInviteResponse.from_model(invitation))


@router.put("/{invite_id}/decline", response_model=ApiResponse[BoardInviteResponse])
async def decline_invite(
    invite_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardInviteResponse]:
    invitation = await ForumService(session).decline_board_invite(invite_id, current_user)
    return ApiResponse(data=BoardInviteResponse.from_model(invitation))


@router.put("/{invite_id}/revoke", response_model=ApiResponse[BoardInviteResponse])
async def revoke_invite(
    invite_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardInviteResponse]:
    invitation = await ForumService(session).revoke_board_invite(invite_id, current_user)
    return ApiResponse(data=BoardInviteResponse.from_model(invitation))
