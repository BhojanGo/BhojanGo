"""R19: phone sign-in codes through Twilio Verify (OTP_PROVIDER=twilio_verify). No network:
Verify's API is an httpx.MockTransport here, or the module's two calls are replaced."""
import httpx
import pytest
from httpx import AsyncClient

from core_api.modules.identity.service import twilio_verify
from shared.config import get_settings

SID = "VA" + "0" * 32


@pytest.fixture
def verify_settings(monkeypatch):  # type: ignore[no-untyped-def]
    i = get_settings().identity
    monkeypatch.setattr(i, "OTP_PROVIDER", "twilio_verify")
    monkeypatch.setattr(i, "TWILIO_VERIFY_SERVICE_SID", SID)
    monkeypatch.setattr(i, "TWILIO_ACCOUNT_SID", "AC-test")
    monkeypatch.setattr(i, "TWILIO_AUTH_TOKEN", "test-token")
    return i


def mock(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_start_asks_verify_for_an_sms(verify_settings) -> None:  # type: ignore[no-untyped-def]
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(201, json={"status": "pending", "sid": "VE1"})

    assert await twilio_verify.start("+12085551234", "es", client=mock(handler))
    req = seen[0]
    assert str(req.url) == f"https://verify.twilio.com/v2/Services/{SID}/Verifications"
    form = dict(httpx.QueryParams(req.content.decode()))
    assert form == {"To": "+12085551234", "Channel": "sms", "Locale": "es"}


async def test_start_leaves_unsupported_languages_to_verify(verify_settings) -> None:  # type: ignore[no-untyped-def]
    forms: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        forms.append(dict(httpx.QueryParams(req.content.decode())))
        return httpx.Response(201, json={"status": "pending"})

    assert await twilio_verify.start("+12085551234", "te", client=mock(handler))
    assert "Locale" not in forms[0]


async def test_start_reports_failures(verify_settings) -> None:  # type: ignore[no-untyped-def]
    assert not await twilio_verify.start("+12085551234", client=mock(lambda r: httpx.Response(400, json={"code": 60200})))
    with pytest.raises(twilio_verify.TooManyCodes):
        await twilio_verify.start("+12085551234", client=mock(lambda r: httpx.Response(429, json={"code": 60203})))

    def down(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    assert not await twilio_verify.start("+12085551234", client=mock(down))


@pytest.mark.parametrize(("status", "body", "ok"), [
    (200, {"status": "approved"}, True),
    (200, {"status": "pending"}, False),  # wrong code
    (404, {"code": 20404}, False),  # expired, used or burnt
    (500, {}, False),
])
async def test_check(verify_settings, status, body, ok) -> None:  # type: ignore[no-untyped-def]
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(status, json=body)

    assert await twilio_verify.check("+12085551234", " 123456 ", client=mock(handler)) is ok
    assert str(seen[0].url).endswith(f"/{SID}/VerificationCheck")
    assert dict(httpx.QueryParams(seen[0].content.decode())) == {"To": "+12085551234", "Code": "123456"}


async def test_check_refuses_non_digits_without_calling(verify_settings) -> None:  # type: ignore[no-untyped-def]
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("no call")

    assert not await twilio_verify.check("+12085551234", "abc", client=mock(handler))


async def test_phone_sign_in_goes_through_verify(client: AsyncClient, outbox, verify_settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Verify sends and checks the code: nothing is stored or texted by us."""
    started: list[tuple[str, str]] = []

    async def start(phone, language="en"):  # type: ignore[no-untyped-def]
        started.append((phone, language))
        return True

    async def check(phone, code):  # type: ignore[no-untyped-def]
        return code == "246810"

    monkeypatch.setattr(twilio_verify, "start", start)
    monkeypatch.setattr(twilio_verify, "check", check)
    phone = "+12085559876"  # not a seed number
    assert (await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": "US"})).status_code == 200
    assert started == [(phone, "en")] and outbox == []
    assert await client.redis.get(f"otp:{phone}") is None  # type: ignore[attr-defined]
    bad = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "111111", "country": "US"})
    assert bad.status_code == 400
    good = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "246810", "country": "US"})
    assert good.status_code == 200


async def test_verify_refusal_is_too_many_codes(client: AsyncClient, verify_settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def start(phone, language="en"):  # type: ignore[no-untyped-def]
        raise twilio_verify.TooManyCodes()

    monkeypatch.setattr(twilio_verify, "start", start)
    r = await client.post("/api/v1/auth/send-otp", json={"phone": "+12085559877", "country": "US"})
    assert r.status_code == 429


async def test_seed_phones_keep_the_local_fixed_code(client: AsyncClient, verify_settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Outside production the seed numbers still sign in with the fixed code, without Verify."""
    async def never(*a, **k):  # type: ignore[no-untyped-def]
        raise AssertionError("Verify must not be called for a seed phone")

    monkeypatch.setattr(twilio_verify, "start", never)
    monkeypatch.setattr(twilio_verify, "check", never)
    phone = "+12085550999"
    assert (await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": "US"})).status_code == 200
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": "US"})
    assert r.status_code == 200
