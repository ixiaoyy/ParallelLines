from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User, UserSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]
OptionalTokenDep = Annotated[str | None, Depends(optional_oauth2_scheme)]


async def get_current_user(
    token: TokenDep,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    payload = decode_token(token, settings=settings, expected_type="access")
    user = await session.get(User, payload["sub"])
    if not user or user.status != "active":
        raise AuthenticationError("invalid_token", "Invalid or expired token")
    await _validate_session(payload.get("sid"), user, session)
    return user


async def get_optional_current_user(
    token: OptionalTokenDep,
    session: SessionDep,
    settings: SettingsDep,
) -> User | None:
    if not token:
        return None
    payload = decode_token(token, settings=settings, expected_type="access")
    user = await session.get(User, payload["sub"])
    if not user or user.status != "active":
        raise AuthenticationError("invalid_token", "Invalid or expired token")
    await _validate_session(payload.get("sid"), user, session)
    return user


async def _validate_session(
    session_id: object,
    user: User,
    session: AsyncSession,
) -> None:
    if not isinstance(session_id, str) or not session_id:
        return
    user_session = await session.get(UserSession, session_id)
    if not user_session or user_session.user_id != user.id or user_session.revoked_at is not None:
        raise AuthenticationError("invalid_token", "Invalid or expired token")


CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalCurrentUserDep = Annotated[User | None, Depends(get_optional_current_user)]
