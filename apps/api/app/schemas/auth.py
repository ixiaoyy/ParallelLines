from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.users import UserPublic


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[\p{L}\p{N}_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    account: str = Field(description="Email or username")
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic
    session_id: str | None = None


class LoginResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserPublic | None = None
    session_id: str | None = None
    two_factor_required: bool = False
    challenge_token: str | None = None


class RegistrationStartResponse(BaseModel):
    email: EmailStr
    verification_required: bool = True
    expires_in_seconds: int
    resend_after_seconds: int
    dev_verification_code: str | None = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetStartResponse(BaseModel):
    ok: bool = True
    expires_in_seconds: int


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr | None = None
    token: str = Field(min_length=6, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    password: str


class EmailChangeStartResponse(BaseModel):
    email: EmailStr
    expires_in_seconds: int


class EmailChangeConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class TwoFactorSetupRequest(BaseModel):
    password: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class TwoFactorEnableRequest(BaseModel):
    secret: str = Field(min_length=16, max_length=64)
    code: str = Field(min_length=6, max_length=32)


class TwoFactorRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class TwoFactorLoginVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=32)


class TwoFactorDisableRequest(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=32)


class SessionResponse(BaseModel):
    id: str
    user_agent: str | None
    ip_address: str | None
    current: bool = False
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None


class OAuthProviderResponse(BaseModel):
    providers: list[str]
