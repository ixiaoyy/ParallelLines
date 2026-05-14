from datetime import timedelta

from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.core.security import create_token, decode_token
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.common import ApiResponse
from app.schemas.users import UserPublic
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[TokenPair],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[TokenPair]:
    token_pair = await AuthService(session, settings).register(payload)
    return ApiResponse(data=token_pair)


@router.post("/login", response_model=ApiResponse[TokenPair])
async def login(
    payload: LoginRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[TokenPair]:
    token_pair = await AuthService(session, settings).login(payload)
    return ApiResponse(data=token_pair)


@router.post("/refresh", response_model=ApiResponse[dict[str, str]])
async def refresh(payload: RefreshRequest, settings: SettingsDep) -> ApiResponse[dict[str, str]]:
    token_payload = decode_token(payload.refresh_token, settings=settings, expected_type="refresh")
    access_token = create_token(
        subject=token_payload["sub"],
        token_type="access",
        settings=settings,
        expires_delta=timedelta(minutes=settings.access_token_minutes),
    )
    return ApiResponse(data={"access_token": access_token, "token_type": "bearer"})


@router.post("/logout", response_model=ApiResponse[dict[str, bool]])
async def logout() -> ApiResponse[dict[str, bool]]:
    return ApiResponse(data={"ok": True})


@router.get("/me", response_model=ApiResponse[UserPublic])
async def me(current_user: CurrentUserDep) -> ApiResponse[UserPublic]:
    return ApiResponse(data=UserPublic.model_validate(current_user))
