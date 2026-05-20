from fastapi import APIRouter, Request, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep, TokenDep
from app.core.security import decode_token
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailChangeConfirmRequest,
    EmailChangeRequest,
    EmailChangeStartResponse,
    LoginRequest,
    LoginResponse,
    OAuthProviderResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetStartResponse,
    RefreshRequest,
    RegisterRequest,
    RegistrationStartResponse,
    ResendVerificationRequest,
    SessionResponse,
    TokenPair,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorLoginVerifyRequest,
    TwoFactorRecoveryCodesResponse,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    VerifyEmailRequest,
)
from app.schemas.common import ApiResponse
from app.schemas.users import UserPublic
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[RegistrationStartResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[RegistrationStartResponse]:
    registration = await AuthService(session, settings).register(payload, request)
    return ApiResponse(data=registration)


@router.post("/verify-email", response_model=ApiResponse[TokenPair])
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[TokenPair]:
    token_pair = await AuthService(session, settings).verify_email(payload, request)
    return ApiResponse(data=token_pair)


@router.post("/resend-verification", response_model=ApiResponse[RegistrationStartResponse])
async def resend_verification(
    payload: ResendVerificationRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[RegistrationStartResponse]:
    registration = await AuthService(session, settings).resend_verification(payload)
    return ApiResponse(data=registration)


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[LoginResponse]:
    login_response = await AuthService(session, settings).login(payload, request)
    return ApiResponse(data=login_response)


@router.post("/2fa/verify-login", response_model=ApiResponse[TokenPair])
async def verify_two_factor_login(
    payload: TwoFactorLoginVerifyRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[TokenPair]:
    token_pair = await AuthService(session, settings).verify_two_factor_login(payload, request)
    return ApiResponse(data=token_pair)


@router.post("/refresh", response_model=ApiResponse[dict[str, str]])
async def refresh(
    payload: RefreshRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[dict[str, str]]:
    refreshed = await AuthService(session, settings).refresh(payload)
    return ApiResponse(data=refreshed)


@router.post("/logout", response_model=ApiResponse[dict[str, bool]])
async def logout(
    token: TokenDep,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[dict[str, bool]]:
    current_session_id = _current_session_id(token, settings)
    if current_session_id:
        await AuthService(session, settings).revoke_session(current_session_id, current_user)
    return ApiResponse(data={"ok": True})


@router.get("/me", response_model=ApiResponse[UserPublic])
async def me(current_user: CurrentUserDep) -> ApiResponse[UserPublic]:
    return ApiResponse(data=UserPublic.model_validate(current_user))


@router.post("/password-reset/request", response_model=ApiResponse[PasswordResetStartResponse])
async def request_password_reset(
    payload: PasswordResetRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[PasswordResetStartResponse]:
    result = await AuthService(session, settings).request_password_reset(payload)
    return ApiResponse(data=result)


@router.post("/password-reset/confirm", response_model=ApiResponse[dict[str, bool]])
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[dict[str, bool]]:
    await AuthService(session, settings).confirm_password_reset(payload)
    return ApiResponse(data={"ok": True})


@router.post("/password/change", response_model=ApiResponse[dict[str, bool]])
async def change_password(
    payload: ChangePasswordRequest,
    token: TokenDep,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[dict[str, bool]]:
    await AuthService(session, settings).change_password(
        payload,
        current_user,
        _current_session_id(token, settings),
    )
    return ApiResponse(data={"ok": True})


@router.post("/email-change/request", response_model=ApiResponse[EmailChangeStartResponse])
async def request_email_change(
    payload: EmailChangeRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EmailChangeStartResponse]:
    result = await AuthService(session, settings).request_email_change(payload, current_user)
    return ApiResponse(data=result)


@router.post("/email-change/confirm", response_model=ApiResponse[UserPublic])
async def confirm_email_change(
    payload: EmailChangeConfirmRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[UserPublic]:
    user = await AuthService(session, settings).confirm_email_change(payload)
    return ApiResponse(data=UserPublic.model_validate(user))


@router.post("/2fa/setup", response_model=ApiResponse[TwoFactorSetupResponse])
async def setup_two_factor(
    payload: TwoFactorSetupRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TwoFactorSetupResponse]:
    result = await AuthService(session, settings).setup_two_factor(payload, current_user)
    return ApiResponse(data=result)


@router.post("/2fa/enable", response_model=ApiResponse[TwoFactorRecoveryCodesResponse])
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TwoFactorRecoveryCodesResponse]:
    result = await AuthService(session, settings).enable_two_factor(payload, current_user)
    return ApiResponse(data=result)


@router.post("/2fa/disable", response_model=ApiResponse[dict[str, bool]])
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[dict[str, bool]]:
    await AuthService(session, settings).disable_two_factor(payload, current_user)
    return ApiResponse(data={"ok": True})


@router.post("/2fa/recovery-codes", response_model=ApiResponse[TwoFactorRecoveryCodesResponse])
async def regenerate_recovery_codes(
    payload: TwoFactorDisableRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TwoFactorRecoveryCodesResponse]:
    result = await AuthService(session, settings).regenerate_recovery_codes(payload, current_user)
    return ApiResponse(data=result)


@router.get("/sessions", response_model=ApiResponse[list[SessionResponse]])
async def list_sessions(
    token: TokenDep,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[SessionResponse]]:
    current_session_id = _current_session_id(token, settings)
    sessions = await AuthService(session, settings).list_sessions(current_user, current_session_id)
    return ApiResponse(
        data=[
            SessionResponse(
                id=item.id,
                user_agent=item.user_agent,
                ip_address=item.ip_address,
                current=getattr(item, "current", False),
                created_at=item.created_at,
                last_seen_at=item.last_seen_at,
                revoked_at=item.revoked_at,
            )
            for item in sessions
        ]
    )


@router.delete("/sessions/{session_id}", response_model=ApiResponse[dict[str, bool]])
async def revoke_session(
    session_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[dict[str, bool]]:
    await AuthService(session, settings).revoke_session(session_id, current_user)
    return ApiResponse(data={"ok": True})


@router.post("/sessions/revoke-others", response_model=ApiResponse[dict[str, int]])
async def revoke_other_sessions(
    token: TokenDep,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[dict[str, int]]:
    count = await AuthService(session, settings).revoke_other_sessions(
        current_user,
        _current_session_id(token, settings),
    )
    return ApiResponse(data={"revoked": count})


@router.get("/oauth/providers", response_model=ApiResponse[OAuthProviderResponse])
async def oauth_providers(
    session: SessionDep, settings: SettingsDep
) -> ApiResponse[OAuthProviderResponse]:
    return ApiResponse(data=AuthService(session, settings).oauth_providers())


def _current_session_id(token: str, settings) -> str | None:
    payload = decode_token(token, settings=settings, expected_type="access")
    session_id = payload.get("sid")
    return session_id if isinstance(session_id, str) else None
