from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import USER_ROLE_ADMIN, is_admin
from app.db.base import as_utc_datetime, utcnow
from app.models.moderation import AuditLog
from app.models.product_access import ProductAccessGrant
from app.models.user import User
from app.schemas.product_access import (
    FableSpaceAccessGrantUpdateRequest,
    FableSpaceAdminAccessRow,
)

FABLESPACE_PRODUCT = "fablespace"
FABLESPACE_ACCESS_CAPABILITY = "fablespace.access"
FABLESPACE_CAPABILITIES_BY_LEVEL: dict[str, tuple[str, ...]] = {
    "access": (FABLESPACE_ACCESS_CAPABILITY,),
    "creator": (FABLESPACE_ACCESS_CAPABILITY, "fablespace.creator"),
    "operator": (
        FABLESPACE_ACCESS_CAPABILITY,
        "fablespace.creator",
        "fablespace.operator",
    ),
    "admin": (
        FABLESPACE_ACCESS_CAPABILITY,
        "fablespace.creator",
        "fablespace.operator",
        "fablespace.admin",
    ),
}


@dataclass(frozen=True)
class ProductAuthorization:
    """Effective product authorization returned to first- and third-party callers."""

    allowed: bool
    access_level: str | None
    capabilities: tuple[str, ...]
    authorization_version: int
    expires_at: datetime | None


def fablespace_capabilities(access_level: str | None) -> tuple[str, ...]:
    """Return ordered FableSpace capabilities for a hierarchical access level.

    Key parameter `access_level` is a persisted access, creator, operator, or admin
    level. The return value is an immutable capability tuple; unknown values safely
    return no capabilities. This function has no side effects.
    """

    return FABLESPACE_CAPABILITIES_BY_LEVEL.get(access_level or "", ())


def fablespace_authorization_from_grant(
    user: User,
    grant: ProductAccessGrant | None,
    *,
    now: datetime | None = None,
) -> ProductAuthorization:
    """Resolve effective FableSpace authorization from account and grant state.

    Key parameters are the forum `user`, an optional persisted `grant`, and an optional
    UTC clock value for deterministic tests. The return value is the current effective
    authorization. This function does not query or mutate the database.
    """

    evaluated_at = now or utcnow()
    version = grant.authorization_version if grant is not None else 0
    persisted_expiry = (
        as_utc_datetime(grant.expires_at)
        if grant is not None and grant.expires_at is not None
        else None
    )

    if user.status != "active":
        return ProductAuthorization(False, None, (), version, persisted_expiry)
    if grant is None or grant.revoked_at is not None:
        return ProductAuthorization(False, None, (), version, persisted_expiry)
    if grant.expires_at is not None and as_utc_datetime(grant.expires_at) <= evaluated_at:
        return ProductAuthorization(False, None, (), version, persisted_expiry)

    capabilities = fablespace_capabilities(grant.access_level)
    if FABLESPACE_ACCESS_CAPABILITY not in capabilities:
        return ProductAuthorization(False, None, (), version, persisted_expiry)
    return ProductAuthorization(
        True,
        grant.access_level,
        capabilities,
        version,
        persisted_expiry,
    )


class ProductAccessService:
    """Manage persistent product grants and resolve their effective capabilities."""

    def __init__(self, session: AsyncSession) -> None:
        """Store the request-scoped database session used by product access operations."""

        self.session = session

    async def fablespace_authorization(self, user: User) -> ProductAuthorization:
        """Load and return a user's current effective FableSpace authorization.

        Key parameter `user` is the authoritative forum account. The return value includes
        access, capabilities, expiry, and version. Side effect: reads one grant row.
        """

        grant = await self._fablespace_grant_for_user(user.id)
        return fablespace_authorization_from_grant(user, grant)

    async def list_fablespace_access_users(
        self,
        current_user: User,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[FableSpaceAdminAccessRow]:
        """List searchable forum users with effective and persisted FableSpace access.

        Key parameters are the administrator, optional username/email query, and result
        limit. The return value includes ungranted accounts so the UI can grant them.
        Side effect: reads users, grants, and grant-actor display names.
        """

        self._require_admin(current_user)
        join_condition = and_(
            ProductAccessGrant.user_id == User.id,
            ProductAccessGrant.product == FABLESPACE_PRODUCT,
        )
        statement = select(User, ProductAccessGrant).outerjoin(
            ProductAccessGrant,
            join_condition,
        )
        if query and query.strip():
            token = f"%{query.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.username).like(token),
                    func.lower(User.email).like(token),
                    func.lower(User.display_name).like(token),
                )
            )
        statement = statement.order_by(
            case(
                (User.role == USER_ROLE_ADMIN, 0),
                (ProductAccessGrant.id.is_not(None), 1),
                else_=2,
            ),
            User.username,
        ).limit(limit)
        rows = (await self.session.execute(statement)).all()
        return [self._admin_row(user, grant) for user, grant in rows]

    async def grant_or_update_fablespace_access(
        self,
        user_id: str,
        payload: FableSpaceAccessGrantUpdateRequest,
        current_user: User,
    ) -> FableSpaceAdminAccessRow:
        """Create, update, or reactivate one user's independent FableSpace grant.

        Key parameters identify the target user, desired level/expiry, and acting admin.
        The return value is the updated admin row. Side effects: mutates one grant, bumps
        its authorization version on real changes, and writes an audit log.
        """

        self._require_admin(current_user)
        target = await self._target_user_for_explicit_grant(user_id)
        expires_at = self._validated_expiry(payload.expires_at)
        grant = await self._fablespace_grant_for_user(user_id, for_update=True)

        if grant is None:
            grant = ProductAccessGrant(
                product=FABLESPACE_PRODUCT,
                user_id=target.id,
                access_level=payload.access_level,
                granted_by_id=current_user.id,
                expires_at=expires_at,
                authorization_version=1,
            )
            grant.user = target
            grant.granted_by = current_user
            self.session.add(grant)
            action = "fablespace_access_granted"
            before: dict[str, object] | None = None
        else:
            before = self._grant_snapshot(grant)
            reactivating = grant.revoked_at is not None
            changed = (
                reactivating
                or grant.access_level != payload.access_level
                or not self._same_expiry(grant.expires_at, expires_at)
            )
            if not changed:
                return self._admin_row(target, grant)
            grant.access_level = payload.access_level
            grant.expires_at = expires_at
            grant.revoked_at = None
            grant.revoked_by_id = None
            grant.revoked_by = None
            if reactivating:
                grant.granted_by_id = current_user.id
                grant.granted_by = current_user
            grant.authorization_version += 1
            action = (
                "fablespace_access_regranted"
                if reactivating
                else "fablespace_access_updated"
            )

        await self.session.flush()
        self._add_audit_log(
            actor_id=current_user.id,
            action=action,
            target_id=target.id,
            data={
                "product": FABLESPACE_PRODUCT,
                "before": before,
                "after": self._grant_snapshot(grant),
            },
        )
        await self.session.commit()
        return self._admin_row(target, grant)

    async def revoke_fablespace_access(
        self,
        user_id: str,
        current_user: User,
    ) -> FableSpaceAdminAccessRow:
        """Revoke one user's explicit FableSpace grant idempotently.

        Key parameters identify the target account and acting administrator. The return
        value is the resulting admin row. Side effects: marks the grant revoked, bumps its
        authorization version once, and writes an audit log.
        """

        self._require_admin(current_user)
        target = await self._target_user_for_explicit_grant(user_id, require_active=False)
        grant = await self._fablespace_grant_for_user(user_id, for_update=True)
        if grant is None:
            raise NotFoundError("product_access_grant_not_found", "Product access grant not found")
        if grant.revoked_at is not None:
            return self._admin_row(target, grant)

        before = self._grant_snapshot(grant)
        grant.revoked_at = utcnow()
        grant.revoked_by_id = current_user.id
        grant.revoked_by = current_user
        grant.authorization_version += 1
        self._add_audit_log(
            actor_id=current_user.id,
            action="fablespace_access_revoked",
            target_id=target.id,
            data={
                "product": FABLESPACE_PRODUCT,
                "before": before,
                "after": self._grant_snapshot(grant),
            },
        )
        await self.session.commit()
        return self._admin_row(target, grant)

    async def _target_user_for_explicit_grant(
        self,
        user_id: str,
        *,
        require_active: bool = True,
    ) -> User:
        """Load and validate a target that can receive or lose an explicit grant.

        Key parameters are the target ID and whether an active account is required. The
        return value is the persisted user. Side effect: reads one user row.
        """

        target = await self.session.get(User, user_id)
        if target is None:
            raise NotFoundError("user_not_found", "User not found")
        if require_active and target.status != "active":
            raise ValidationError("user_not_active", "Only active users can receive access")
        return target

    async def _fablespace_grant_for_user(
        self,
        user_id: str,
        *,
        for_update: bool = False,
    ) -> ProductAccessGrant | None:
        """Load one user's unique FableSpace grant, optionally locking it for mutation.

        Key parameters are the target user ID and row-lock flag. The return value is the
        grant or null. Side effect: reads and optionally locks one database row.
        """

        statement = select(ProductAccessGrant).where(
            ProductAccessGrant.product == FABLESPACE_PRODUCT,
            ProductAccessGrant.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    def _admin_row(
        self,
        user: User,
        grant: ProductAccessGrant | None,
    ) -> FableSpaceAdminAccessRow:
        """Build one admin-facing user row from account and optional grant state.

        Key parameters are the target account and loaded grant. The return value is a
        serialized management row. This helper has no database side effects.
        """

        authorization = fablespace_authorization_from_grant(user, grant)
        if grant is not None and grant.revoked_at is None:
            displayed_level = grant.access_level
        else:
            displayed_level = None
        granted_by = grant.granted_by if grant is not None else None
        return FableSpaceAdminAccessRow(
            user_id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            forum_role=user.role,
            account_status=user.status,
            access_allowed=authorization.allowed,
            access_level=displayed_level,  # type: ignore[arg-type]
            capabilities=list(authorization.capabilities),
            authorization_version=authorization.authorization_version,
            granted_by_id=grant.granted_by_id if grant is not None else None,
            granted_by_name=granted_by.username if granted_by is not None else None,
            expires_at=authorization.expires_at,
            revoked_at=(
                as_utc_datetime(grant.revoked_at)
                if grant is not None and grant.revoked_at is not None
                else None
            ),
            created_at=(
                as_utc_datetime(grant.created_at)
                if grant is not None and grant.created_at is not None
                else None
            ),
            updated_at=(
                as_utc_datetime(grant.updated_at)
                if grant is not None and grant.updated_at is not None
                else None
            ),
        )

    def _validated_expiry(self, expires_at: datetime | None) -> datetime | None:
        """Normalize a requested expiry and reject timestamps that are not in the future.

        Key parameter `expires_at` may be null for indefinite access. The return value is
        UTC-aware or null. This helper reads the system clock but has no other side effect.
        """

        if expires_at is None:
            return None
        normalized = as_utc_datetime(expires_at)
        if normalized <= utcnow():
            raise ValidationError("invalid_access_expiry", "Access expiry must be in the future")
        return normalized

    def _same_expiry(
        self,
        left: datetime | None,
        right: datetime | None,
    ) -> bool:
        """Compare nullable persisted expiry timestamps as UTC instants.

        Key parameters are two nullable datetimes. The return value reports instant
        equality. This helper has no side effects.
        """

        if left is None or right is None:
            return left is None and right is None
        return as_utc_datetime(left) == as_utc_datetime(right)

    def _grant_snapshot(self, grant: ProductAccessGrant) -> dict[str, object]:
        """Create a JSON-safe authorization snapshot for an audit event.

        Key parameter `grant` is the mutated persistence model. The return value contains
        no secrets and is safe for `audit_logs.data`. This helper has no side effects.
        """

        return {
            "access_level": grant.access_level,
            "expires_at": (
                as_utc_datetime(grant.expires_at).isoformat()
                if grant.expires_at
                else None
            ),
            "revoked_at": (
                as_utc_datetime(grant.revoked_at).isoformat()
                if grant.revoked_at
                else None
            ),
            "granted_by_id": grant.granted_by_id,
            "revoked_by_id": grant.revoked_by_id,
            "authorization_version": grant.authorization_version,
        }

    def _require_admin(self, current_user: User) -> None:
        """Require a forum administrator for product grant management operations.

        Key parameter `current_user` is the acting account. Return value is none. Side
        effect: raises a typed permission error when the role is insufficient.
        """

        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _add_audit_log(
        self,
        *,
        actor_id: str,
        action: str,
        target_id: str,
        data: dict[str, object],
    ) -> None:
        """Stage a product-access audit record in the current transaction.

        Key parameters identify the actor, action, target user, and safe change snapshot.
        Return value is none. Side effect: adds one uncommitted AuditLog model.
        """

        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type="product_access_grant",
                target_id=target_id,
                board_id=None,
                data=data,
                created_at=utcnow(),
            )
        )
