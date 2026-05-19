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


class RefreshRequest(BaseModel):
    refresh_token: str
