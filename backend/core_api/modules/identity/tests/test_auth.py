import pytest
from httpx import AsyncClient

from core_api.modules.identity.tests.signin import email_sign_up

PASSWORD = "Secure-pass-2026"


async def test_sign_up_then_sign_in_with_the_password(client: AsyncClient) -> None:
    data = await email_sign_up(client, "test@example.com", PASSWORD)
    assert data["access_token"] and data["refresh_token"] and data["is_new_user"] is True
    assert data["user"]["email"] == "test@example.com" and data["user"]["role"] == "customer"
    assert data["user"]["is_verified"] is True

    r = await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["token_type"] == "bearer" and r.json()["mfa_required"] is False


async def test_register_is_gone(client: AsyncClient) -> None:
    """Accounts are made by /auth/email/sign-up (email verified first), not /auth/register."""
    r = await client.post("/api/v1/auth/register", json={"email": "x@example.com", "password": PASSWORD})
    assert r.status_code in (404, 405)


async def test_login_wrong_password_and_unknown_email_answer_alike(client: AsyncClient) -> None:
    await email_sign_up(client, "wrongpw@example.com", PASSWORD)
    wrong = await client.post("/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "Wrong-pass-1"})
    nobody = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Wrong-pass-1"})
    assert wrong.status_code == nobody.status_code == 401
    assert wrong.json() == nobody.json()


async def test_get_me_authenticated(client: AsyncClient) -> None:
    token = (await email_sign_up(client, "me@example.com", PASSWORD))["access_token"]
    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 403  # HTTPBearer returns 403 when no credentials


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "core-api"  # /health is now shared by all core_api modules
    assert "status" in data
    assert "checks" in data


async def test_update_me_changes_the_name_but_never_the_phone(client: AsyncClient) -> None:
    token = (await email_sign_up(client, "update@example.com", PASSWORD))["access_token"]
    response = await client.put(
        "/api/v1/users/me",
        json={"full_name": "Updated Name", "phone": "+14155550111"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
    assert response.json()["phone"] is None  # a phone is linked with a code (/me/phone), not set here


@pytest.mark.asyncio
async def test_send_otp(client: AsyncClient) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("core_api.modules.identity.service.otp.send_otp", lambda phone, country: True)
        response = await client.post(
            "/api/v1/auth/send-otp",
            json={"phone": "+14155552671", "country": "US"},
        )
    assert response.status_code == 200
