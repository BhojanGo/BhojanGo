import pytest
from httpx import AsyncClient


REGISTER_DATA = {
    "email": "test@bhojango.com",
    "password": "SecurePass1",
    "full_name": "Test User",
    "country": "US",
    "preferred_currency": "USD",
    "preferred_locale": "en-US",
}


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER_DATA)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == REGISTER_DATA["email"]
    assert data["user"]["role"] == "customer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_DATA)
    response = await client.post("/api/v1/auth/register", json=REGISTER_DATA)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    data = {**REGISTER_DATA, "email": "weak@bhojango.com", "password": "weak"}
    response = await client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    register_data = {**REGISTER_DATA, "email": "login@bhojango.com"}
    await client.post("/api/v1/auth/register", json=register_data)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@bhojango.com", "password": "SecurePass1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    register_data = {**REGISTER_DATA, "email": "wrongpw@bhojango.com"}
    await client.post("/api/v1/auth/register", json=register_data)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@bhojango.com", "password": "WrongPass1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@bhojango.com", "password": "SomePass1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient) -> None:
    reg_data = {**REGISTER_DATA, "email": "me@bhojango.com"}
    reg_resp = await client.post("/api/v1/auth/register", json=reg_data)
    token = reg_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@bhojango.com"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 403  # HTTPBearer returns 403 when no credentials


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "user-svc"
    assert "status" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient) -> None:
    reg_data = {**REGISTER_DATA, "email": "update@bhojango.com"}
    reg_resp = await client.post("/api/v1/auth/register", json=reg_data)
    token = reg_resp.json()["access_token"]

    response = await client.put(
        "/api/v1/users/me",
        json={"full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_send_otp(client: AsyncClient) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.otp.send_otp", lambda phone, country: True)
        response = await client.post(
            "/api/v1/auth/send-otp",
            json={"phone": "+14155552671", "country": "US"},
        )
    assert response.status_code == 200
