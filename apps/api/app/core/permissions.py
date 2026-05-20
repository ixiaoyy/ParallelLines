from typing import Protocol

USER_ROLE_USER = "user"
USER_ROLE_MODERATOR = "moderator"
USER_ROLE_ADMIN = "admin"

GLOBAL_MODERATOR_ROLES = frozenset({USER_ROLE_ADMIN, USER_ROLE_MODERATOR})
BOARD_MODERATOR_ROLES = frozenset({"owner", "moderator"})


class RoleBearing(Protocol):
    role: str


def is_admin(user: RoleBearing) -> bool:
    return user.role == USER_ROLE_ADMIN


def is_global_moderator(user: RoleBearing) -> bool:
    return user.role in GLOBAL_MODERATOR_ROLES
