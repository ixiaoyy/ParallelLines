from datetime import datetime

from pydantic import EmailStr

from app.schemas.common import ORMModel


class UserPublic(ORMModel):
    id: str
    username: str
    email: EmailStr
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime
