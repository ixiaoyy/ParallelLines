from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.schemas.users import UserPublic


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def register(self, payload: RegisterRequest) -> TokenPair:
        existing = await self.session.scalar(
            select(User).where(or_(User.email == payload.email, User.username == payload.username))
        )
        if existing:
            raise ConflictError(
                "account_exists",
                "Username or email is already registered",
                {"username": payload.username, "email": payload.email},
            )

        user = User(
            username=payload.username,
            email=str(payload.email).lower(),
            hashed_password=hash_password(payload.password),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return self._token_pair(user)

    async def login(self, payload: LoginRequest) -> TokenPair:
        account = payload.account.lower()
        user = await self.session.scalar(
            select(User).where(or_(User.email == account, User.username == payload.account))
        )
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("invalid_credentials", "Invalid account or password")
        if user.status != "active":
            raise AuthenticationError("account_disabled", "This account is not active")
        return self._token_pair(user)

    def _token_pair(self, user: User) -> TokenPair:
        access_token = create_token(
            subject=user.id,
            token_type="access",
            settings=self.settings,
            expires_delta=timedelta(minutes=self.settings.access_token_minutes),
        )
        refresh_token = create_token(
            subject=user.id,
            token_type="refresh",
            settings=self.settings,
            expires_delta=timedelta(days=self.settings.refresh_token_days),
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserPublic.model_validate(user),
        )
