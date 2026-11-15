"""Sign-up countries come from Markets (conftest stands in IN and US live, FR a draft):
no list in the code, IN and US behave as before, a draft or unknown country is
refused, and a phone number must carry its country's calling code."""
from httpx import AsyncClient

SEED_US = "+12085550777"
SEED_IN = "+9190000778"


async def test_us_and_in_phone_sign_in_take_currency_and_language_from_the_country(client: AsyncClient) -> None:
    for phone, country, currency, locale in ((SEED_US, "US", "USD", "en-US"), (SEED_IN, "IN", "INR", "en-IN")):
        assert (await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": country})).status_code == 200
        r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": country})
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert (u["country"], u["preferred_currency"], u["preferred_locale"]) == (country, currency, locale)


async def test_a_draft_or_unknown_country_is_refused(client: AsyncClient) -> None:
    for country in ("FR", "ZZ"):
        r = await client.post("/api/v1/auth/send-otp", json={"phone": "+33612345678", "country": country})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "COUNTRY_NOT_AVAILABLE", r.text
        r = await client.post("/api/v1/auth/register", json={
            "email": f"x.{country.lower()}@example.com", "password": "SecurePass1", "full_name": "Test User",
            "country": country})
        assert r.status_code == 422, r.text


async def test_a_phone_number_must_carry_its_countrys_code(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/send-otp", json={"phone": SEED_US, "country": "IN"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PHONE_COUNTRY_MISMATCH", r.text
    r = await client.post("/api/v1/auth/phone", json={"phone": SEED_IN, "otp": "123456", "country": "US"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PHONE_COUNTRY_MISMATCH", r.text


async def test_register_currency_must_be_one_we_charge_in(client: AsyncClient) -> None:
    base = {"password": "SecurePass1", "full_name": "Test User", "country": "IN"}
    r = await client.post("/api/v1/auth/register", json={**base, "email": "eur@example.com", "preferred_currency": "EUR"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "CURRENCY_NOT_AVAILABLE", r.text
    r = await client.post("/api/v1/auth/register", json={**base, "email": "inr@example.com", "preferred_currency": "INR"})
    assert r.status_code == 201, r.text


async def test_openapi_types_country_and_currency_as_strings(client: AsyncClient) -> None:
    schemas = (await client.get("/openapi.json")).json()["components"]["schemas"]
    for name, field in (("OtpSendRequest", "country"), ("PhoneSignInRequest", "country"), ("RegisterRequest", "country"),
                        ("RegisterRequest", "preferred_currency"), ("RestaurantCreateRequest", "currency")):
        prop = schemas[name]["properties"][field]
        assert prop.get("type") == "string" and "enum" not in prop, (name, field, prop)
