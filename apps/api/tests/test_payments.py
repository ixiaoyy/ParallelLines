import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.payment import UserSubscription
from app.models.user import User
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def promote_admin(session_factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = "admin"
        await session.commit()


def signed_payload(
    payload: dict[str, object], secret: str = "dev-payment-webhook-secret"
) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, f"sha256={digest}"


@pytest.mark.asyncio
async def test_signed_payment_webhook_grants_and_expires_entitlements() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "payinguser")
        admin = await register_and_verify_user(client, "paymentsadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        user_headers = {"Authorization": f"Bearer {user['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

        plans = await client.get("/api/v1/subscriptions/plans")
        assert plans.status_code == 200
        assert plans.json()["data"][0]["slug"] == "supporter"

        denied_events = await client.get("/api/v1/admin/payments/events", headers=user_headers)
        assert denied_events.status_code == 403

        bad_payload = {"id": "evt_bad", "type": "checkout.session.completed", "data": {}}
        bad_body = json.dumps(bad_payload).encode()
        bad = await client.post(
            "/api/v1/payments/webhooks/testpay",
            content=bad_body,
            headers={"X-ParallelLines-Signature": "sha256=bad"},
        )
        assert bad.status_code == 403
        assert bad.json()["error"]["code"] == "payment_webhook_signature_invalid"

        period_end = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        body, signature = signed_payload(
            {
                "id": "evt_paid_1",
                "type": "checkout.session.completed",
                "data": {
                    "user_id": user["user"]["id"],
                    "plan_slug": "supporter",
                    "subscription_id": "sub_123",
                    "customer_id": "cus_123",
                    "current_period_end": period_end,
                    "amount_cents": 990,
                    "currency": "CNY",
                },
            }
        )
        paid = await client.post(
            "/api/v1/payments/webhooks/testpay",
            content=body,
            headers={"X-ParallelLines-Signature": signature},
        )
        assert paid.status_code == 200
        assert paid.json()["data"]["subscription_status"] == "active"

        subscription = await client.get("/api/v1/subscriptions/me", headers=user_headers)
        assert subscription.status_code == 200
        subscription_data = subscription.json()["data"]
        assert subscription_data["status"] == "active"
        assert "paid_member" in subscription_data["entitlements"]

        admin_events = await client.get("/api/v1/admin/payments/events", headers=admin_headers)
        assert admin_events.status_code == 200
        assert admin_events.json()["data"][0]["event_id"] == "evt_paid_1"

    async with session_factory() as session:
        subscription = await session.get(UserSubscription, subscription_data["id"])
        assert subscription is not None
        subscription.current_period_end = datetime.now(UTC) - timedelta(days=1)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        expired = await client.get("/api/v1/subscriptions/me", headers=user_headers)
        assert expired.status_code == 200
        assert expired.json()["data"]["status"] == "expired"
        assert expired.json()["data"]["entitlements"] == []

    await engine.dispose()
