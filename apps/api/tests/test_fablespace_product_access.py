from datetime import UTC, datetime, timedelta

from app.main import create_app
from app.models.product_access import ProductAccessGrant
from app.models.user import User
from app.services.product_access import (
    FABLESPACE_CAPABILITIES_BY_LEVEL,
    fablespace_authorization_from_grant,
    fablespace_capabilities,
)


def _user(*, role: str = "user", status: str = "active") -> User:
    """Build an in-memory user model for pure authorization tests."""

    return User(
        id="100",
        username="access-user",
        email="access-user@example.com",
        hashed_password="not-used",
        role=role,
        status=status,
    )


def _grant(
    *,
    level: str = "access",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    version: int = 1,
) -> ProductAccessGrant:
    """Build an in-memory FableSpace grant for pure authorization tests."""

    return ProductAccessGrant(
        id="200",
        product="fablespace",
        user_id="100",
        access_level=level,
        expires_at=expires_at,
        revoked_at=revoked_at,
        authorization_version=version,
    )


def test_fablespace_capabilities_are_hierarchical() -> None:
    """Higher levels should retain every lower-level product capability."""

    assert fablespace_capabilities("access") == ("fablespace.access",)
    assert fablespace_capabilities("creator") == (
        "fablespace.access",
        "fablespace.creator",
    )
    assert fablespace_capabilities("operator") == (
        "fablespace.access",
        "fablespace.creator",
        "fablespace.operator",
    )
    assert fablespace_capabilities("admin") == FABLESPACE_CAPABILITIES_BY_LEVEL["admin"]
    assert fablespace_capabilities("unknown") == ()


def test_active_forum_accounts_receive_baseline_fablespace_access() -> None:
    """Every active forum account should receive the same baseline product access."""

    ordinary_user = fablespace_authorization_from_grant(_user(), None)
    forum_admin = fablespace_authorization_from_grant(_user(role="admin"), None)
    with_grant = fablespace_authorization_from_grant(
        _user(role="admin"),
        _grant(level="admin"),
    )

    assert ordinary_user.allowed is True
    assert ordinary_user.access_level == "access"
    assert ordinary_user.capabilities == ("fablespace.access",)
    assert forum_admin == ordinary_user
    assert forum_admin.authorization_version == 0
    assert with_grant.allowed is True
    assert with_grant.access_level == "admin"
    assert with_grant.capabilities[-1] == "fablespace.admin"


def test_explicit_grant_respects_level_and_falls_back_to_baseline() -> None:
    """Expired or revoked grants should lose elevation while active accounts keep access."""

    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    active_grant = _grant(level="creator", expires_at=now + timedelta(hours=1), version=7)
    active = fablespace_authorization_from_grant(_user(), active_grant, now=now)
    expired = fablespace_authorization_from_grant(
        _user(),
        _grant(expires_at=now, version=8),
        now=now,
    )
    revoked = fablespace_authorization_from_grant(
        _user(),
        _grant(revoked_at=now - timedelta(minutes=1), version=9),
        now=now,
    )
    suspended = fablespace_authorization_from_grant(
        _user(status="suspended"),
        active_grant,
        now=now,
    )

    assert active.allowed is True
    assert active.access_level == "creator"
    assert active.capabilities == ("fablespace.access", "fablespace.creator")
    assert active.authorization_version == 7
    assert expired.allowed is True and expired.access_level == "access"
    assert expired.capabilities == ("fablespace.access",)
    assert expired.authorization_version == 8
    assert expired.expires_at is None
    assert revoked.allowed is True and revoked.access_level == "access"
    assert revoked.capabilities == ("fablespace.access",)
    assert revoked.authorization_version == 9
    assert revoked.expires_at is None
    assert suspended.allowed is False and suspended.authorization_version == 7


def test_naive_database_expiry_is_normalized_to_utc() -> None:
    """MySQL-style naive UTC timestamps should cross the API boundary with a timezone."""

    now = datetime(2026, 7, 15, 4, tzinfo=UTC)
    authorization = fablespace_authorization_from_grant(
        _user(),
        _grant(expires_at=datetime(2026, 7, 15, 12)),
        now=now,
    )

    assert authorization.expires_at == datetime(2026, 7, 15, 12, tzinfo=UTC)


def test_fablespace_access_routes_are_in_openapi_contract() -> None:
    """The generated API contract should expose user, admin, and server access paths."""

    paths = create_app().openapi()["paths"]

    assert "get" in paths["/api/v1/auth/fablespace/access"]
    assert "post" in paths["/api/v1/auth/fablespace/ticket"]
    assert "post" in paths["/api/v1/auth/fablespace/exchange"]
    assert "post" in paths["/api/v1/auth/fablespace/introspect"]
    assert "get" in paths["/api/v1/admin/fablespace/access-grants"]
    assert {"put", "delete"} <= set(
        paths["/api/v1/admin/fablespace/access-grants/{user_id}"]
    )
