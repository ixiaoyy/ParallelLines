from httpx import AsyncClient


async def register_and_verify_user(
    client: AsyncClient,
    username: str,
    *,
    email: str | None = None,
    password: str = "strong-pass-123",
) -> dict[str, str]:
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
    )
    assert register.status_code == 201
    register_data = register.json()["data"]
    code = register_data["dev_verification_code"]
    assert code

    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_data["email"], "code": code},
    )
    assert verify.status_code == 200
    return verify.json()["data"]
