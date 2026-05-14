from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(
    token: TokenDep,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    payload = decode_token(token, settings=settings, expected_type="access")
    user = await session.get(User, payload["sub"])
    if not user or user.status != "active":
        raise AuthenticationError("invalid_token", "Invalid or expired token")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
