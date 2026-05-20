from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.exceptions import AuthenticationError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_token(
    *,
    subject: str,
    token_type: Literal["access", "refresh", "two_factor"],
    settings: Settings,
    expires_delta: timedelta,
    session_id: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(
    token: str,
    *,
    settings: Settings,
    expected_type: str = "access",
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("invalid_token", "Invalid or expired token") from exc

    if payload.get("typ") != expected_type or not payload.get("sub"):
        raise AuthenticationError("invalid_token", "Invalid token type")

    return payload
