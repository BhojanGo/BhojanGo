"""Fakes refuse to start in any environment named production (QA on Railway)."""
import pytest

from shared.config import ProductionConfigError, Settings

LIVE = {"PAYMENT_PROVIDER": "live", "PAYOUT_PROVIDER": "live", "OTP_FIXED_CODE": ""}


def make(monkeypatch, **env: str) -> Settings:  # type: ignore[no-untyped-def]
    for k in ("APP_ENV", "RAILWAY_ENVIRONMENT_NAME", *LIVE):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("names", [{"APP_ENV": "production"}, {"APP_ENV": "Prod"},
                                   {"APP_ENV": "qa", "RAILWAY_ENVIRONMENT_NAME": "production"}])
@pytest.mark.parametrize("bad", [{"PAYMENT_PROVIDER": "fake"}, {"PAYMENT_PROVIDER": "auto"},
                                 {"PAYOUT_PROVIDER": "fake"}, {"OTP_FIXED_CODE": "123456"}])
def test_production_refuses_fakes(monkeypatch, names, bad) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ProductionConfigError, match="refusing to start in production"):
        make(monkeypatch, **{**names, **LIVE, **bad})


def test_production_with_live_providers_starts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert make(monkeypatch, APP_ENV="production", **LIVE).production_named


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
