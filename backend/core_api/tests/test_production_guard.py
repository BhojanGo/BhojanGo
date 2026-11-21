"""Fakes refuse to start in any environment named production (QA on Railway)."""
import pytest

from shared.config import ProductionConfigError, Settings

LIVE = {"PAYMENT_PROVIDER": "live", "PAYOUT_PROVIDER": "live", "OTP_FIXED_CODE": ""}


def make(monkeypatch, **env: str) -> Settings:  # type: ignore[no-untyped-def]
    for k in ("APP_ENV", "RAILWAY_ENVIRONMENT_NAME", "DEMO_RIDER_SIM", "REVIEW_SIM", *LIVE):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("names", [{"APP_ENV": "production"}, {"APP_ENV": "Prod"},
                                   {"APP_ENV": "qa", "RAILWAY_ENVIRONMENT_NAME": "production"}])
@pytest.mark.parametrize("bad", [{"PAYMENT_PROVIDER": "fake"}, {"PAYMENT_PROVIDER": "auto"},
                                 {"PAYOUT_PROVIDER": "fake"}, {"OTP_FIXED_CODE": "123456"},
                                 {"DEMO_RIDER_SIM": "1"}])
def test_production_refuses_fakes(monkeypatch, names, bad) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ProductionConfigError, match="refusing to start in production"):
        make(monkeypatch, **{**names, **LIVE, **bad})


def test_production_with_live_providers_starts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert make(monkeypatch, APP_ENV="production", **LIVE).production_named


def test_production_allows_the_review_simulator_and_still_refuses_the_demo_rider(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """R20: REVIEW_SIM (app store review orders only) is the one simulator production starts with."""
    assert make(monkeypatch, APP_ENV="production", **LIVE, REVIEW_SIM="1").worker.REVIEW_SIM is True
    with pytest.raises(ProductionConfigError, match="DEMO_RIDER_SIM"):
        make(monkeypatch, APP_ENV="production", **LIVE, REVIEW_SIM="1", DEMO_RIDER_SIM="1")


def test_production_needs_the_fixed_otp_cleared(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The default fixed OTP (for seed phones) is on; production must switch it off."""
    with pytest.raises(ProductionConfigError, match="OTP_FIXED_CODE"):
        make(monkeypatch, APP_ENV="production", PAYMENT_PROVIDER="live")


@pytest.mark.parametrize("env", ["qa", "staging", "development", "test"])
def test_other_environments_keep_the_fakes(monkeypatch, env) -> None:  # type: ignore[no-untyped-def]
    s = make(monkeypatch, APP_ENV=env, RAILWAY_ENVIRONMENT_NAME="QA", PAYMENT_PROVIDER="fake")
    assert not s.production_named and s.providers.OTP_FIXED_CODE == "123456"


@pytest.mark.parametrize(("given", "used"), [("virtual-host", "virtual"), ("virtual", "virtual"), ("path", "path"),
                                             ("auto", "auto")])
def test_railway_bucket_url_style_maps_to_boto(monkeypatch, given, used) -> None:  # type: ignore[no-untyped-def]
    """`railway bucket credentials` gives urlStyle "virtual-host"; boto3 only knows "virtual"."""
    assert make(monkeypatch, APP_ENV="qa", S3_ADDRESSING_STYLE=given).providers.S3_ADDRESSING_STYLE == used


@pytest.mark.parametrize(("env", "expected"), [
    ({"APP_ENV": "development"}, "development"), ({"APP_ENV": "QA"}, "qa"),
    ({"APP_ENV": "staging", "RAILWAY_ENVIRONMENT_NAME": "staging"}, "staging"),
    # Railway's own name wins when it's one tests must never write to (tools/target_guard.py)
    ({"APP_ENV": "development", "RAILWAY_ENVIRONMENT_NAME": "QA"}, "qa"),
])
def test_environment_name_for_health(monkeypatch, env, expected) -> None:  # type: ignore[no-untyped-def]
    assert make(monkeypatch, **env).environment_name == expected


async def test_public_health_reports_the_environment() -> None:
    from httpx import ASGITransport, AsyncClient

    from core_api.main import app
    from shared.config import get_settings

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.json()["environment"] == get_settings().environment_name


# ── R19: what core_api needs in production (public addresses, two-step key, sign-in codes) ──

CORE_OK = {"PUBLIC_WEB_URL": "https://web.example.org", "PUBLIC_API_URL": "https://api.example.org",
           "OTP_PROVIDER": "twilio_verify", "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "t",
           "TWILIO_VERIFY_SERVICE_SID": "VA1", "SMS_PROVIDER": "off"}


def core(monkeypatch, **env: str) -> Settings:  # type: ignore[no-untyped-def]
    for k in (*CORE_OK, "IDENTITY_DATA_KEYS"):
        monkeypatch.delenv(k, raising=False)
    from cryptography.fernet import Fernet

    return make(monkeypatch, APP_ENV="production", **LIVE,
                **{"IDENTITY_DATA_KEYS": f'["{Fernet.generate_key().decode()}"]', **CORE_OK, **env})


def test_core_api_production_ready(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = core(monkeypatch)
    assert s.core_api_production_problems() == []
    s.check_core_api_production()


@pytest.mark.parametrize(("name", "value", "says"), [
    ("PUBLIC_WEB_URL", "", "PUBLIC_WEB_URL is not set"),
    ("PUBLIC_WEB_URL", "http://localhost:3000", "PUBLIC_WEB_URL must be an https"),
    ("PUBLIC_WEB_URL", "https://localhost:3000", "PUBLIC_WEB_URL points at localhost"),
    ("PUBLIC_WEB_URL", "http://web.example.org", "PUBLIC_WEB_URL must be an https"),
    ("PUBLIC_API_URL", "https://127.0.0.1:8001", "PUBLIC_API_URL points at 127.0.0.1"),
    ("PUBLIC_API_URL", "https://core-api.railway.internal", "PUBLIC_API_URL points at the private network"),
    ("PUBLIC_API_URL", "api.example.org", "PUBLIC_API_URL must be an https"),
])
def test_core_api_refuses_bad_public_addresses(monkeypatch, name, value, says) -> None:  # type: ignore[no-untyped-def]
    s = core(monkeypatch, **{name: value})
    with pytest.raises(ProductionConfigError, match=says):
        s.check_core_api_production()


def test_core_api_defaults_are_localhost_and_refused(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Left unset, both addresses are the localhost defaults: production names both."""
    monkeypatch.delenv("PUBLIC_WEB_URL", raising=False)
    s = core(monkeypatch)
    s.identity.PUBLIC_WEB_URL = "http://localhost:3000"
    s.payments.PUBLIC_API_URL = "http://localhost:8001"
    problems = " ".join(s.core_api_production_problems())
    assert "PUBLIC_WEB_URL" in problems and "PUBLIC_API_URL" in problems


def test_core_api_needs_identity_data_keys(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = core(monkeypatch, IDENTITY_DATA_KEYS="[]")
    with pytest.raises(ProductionConfigError, match="IDENTITY_DATA_KEYS"):
        s.check_core_api_production()


def test_core_api_needs_a_way_to_send_sign_in_codes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ProductionConfigError, match="TWILIO_VERIFY_SERVICE_SID"):
        core(monkeypatch, TWILIO_VERIFY_SERVICE_SID="").check_core_api_production()
    with pytest.raises(ProductionConfigError, match="OTP_PROVIDER"):
        core(monkeypatch, OTP_PROVIDER="local").check_core_api_production()
    # Our own codes are fine when the worker can text them
    core(monkeypatch, OTP_PROVIDER="local", SMS_PROVIDER="live").check_core_api_production()


def test_core_api_checks_nothing_outside_production(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = make(monkeypatch, APP_ENV="qa", RAILWAY_ENVIRONMENT_NAME="QA")
    assert s.core_api_production_problems() == []
