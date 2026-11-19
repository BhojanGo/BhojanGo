"""R19 production providers: Amazon SES email, SMS switched off, the worker's start-up check,
FCM without keys, Sentry off without a DSN. No network: SES is botocore's Stubber."""
import sys
import types

import pytest

from shared.config import get_settings
from shared.providers.email import SesEmail, get_email_provider
from shared.providers.sms import NoSms, get_sms_provider, sms_enabled


@pytest.fixture
def ses(monkeypatch):  # type: ignore[no-untyped-def]
    w = get_settings().worker
    for k, v in {"SES_REGION": "us-west-2", "SES_ACCESS_KEY_ID": "AKIDTEST", "SES_SECRET_ACCESS_KEY": "test-secret",
                 "EMAIL_FROM": "orders@example.org", "EMAIL_FROM_NAME": "BhojanGo", "SES_CONFIGURATION_SET": ""}.items():
        monkeypatch.setattr(w, k, v)
    return w


def stubbed(response: dict | None = None, error: str | None = None, expected: dict | None = None):  # type: ignore[no-untyped-def]
    import boto3
    from botocore.stub import Stubber

    client = boto3.client("sesv2", region_name="us-west-2", aws_access_key_id="AKIDTEST",
                          aws_secret_access_key="test-secret")
    stub = Stubber(client)
    if error:
        stub.add_client_error("send_email", service_error_code=error, http_status_code=400)
    else:
        stub.add_response("send_email", response or {"MessageId": "m-1"}, expected)
    stub.activate()
    return client, stub


def test_ses_selected(monkeypatch, ses) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings().providers, "EMAIL_PROVIDER", "ses")
    assert isinstance(get_email_provider(), SesEmail)


async def test_ses_sends_html_and_text(ses) -> None:  # type: ignore[no-untyped-def]
    expected = {
        "FromEmailAddress": "BhojanGo <orders@example.org>",
        "Destination": {"ToAddresses": ["a@example.org"]},
        "Content": {"Simple": {"Subject": {"Data": "Your code", "Charset": "UTF-8"},
                               "Body": {"Html": {"Data": "<p>123456</p>", "Charset": "UTF-8"},
                                        "Text": {"Data": "123456", "Charset": "UTF-8"}}}},
    }
    client, stub = stubbed(expected=expected)
    assert await SesEmail(client).send("a@example.org", "Your code", "<p>123456</p>", "123456")
    stub.assert_no_pending_responses()


async def test_ses_configuration_set_and_no_text(monkeypatch, ses) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(ses, "SES_CONFIGURATION_SET", "events")
    req = SesEmail(object()).request("a@example.org", "Hi", "<p>Hi</p>")
    assert req["ConfigurationSetName"] == "events"
    assert "Text" not in req["Content"]["Simple"]["Body"]


async def test_ses_failure_is_false_not_a_crash(ses) -> None:  # type: ignore[no-untyped-def]
    client, _ = stubbed(error="MessageRejected")
    assert not await SesEmail(client).send("a@example.org", "Hi", "<p>Hi</p>")


async def test_sms_off_sends_nothing(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings().providers, "SMS_PROVIDER", "off")
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")  # allowed in production: it's chosen
    provider = get_sms_provider("US")
    assert isinstance(provider, NoSms) and not sms_enabled()
    assert not await provider.send("+12085551234", "hello", "US")
    assert "[SMS to" not in capsys.readouterr().out


# ── the worker's production start-up check ───────────────────────────────────

def prod(monkeypatch, **providers: str):  # type: ignore[no-untyped-def]
    s = get_settings()
    monkeypatch.setattr(s, "APP_ENV", "production")
    for k, v in {"EMAIL_PROVIDER": "ses", "PUSH_PROVIDER": "live", "SMS_PROVIDER": "off", **providers}.items():
        monkeypatch.setattr(s.providers, k, v)
    monkeypatch.setattr("shared.bus.configured", lambda: True)
    return s


def test_worker_starts_in_production_with_ses_push_and_no_sms(monkeypatch, ses) -> None:  # type: ignore[no-untyped-def]
    from app.main import production_missing

    s = prod(monkeypatch)
    for k in ("TWILIO_ACCOUNT_SID", "SENDGRID_API_KEY", "FIREBASE_PROJECT_ID"):
        monkeypatch.setattr(s.worker, k, "")
    assert production_missing(s) == []


def test_worker_names_what_production_lacks(monkeypatch, ses) -> None:  # type: ignore[no-untyped-def]
    from app.main import production_missing

    s = prod(monkeypatch)
    monkeypatch.setattr(ses, "SES_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(ses, "EMAIL_FROM", "")
    assert production_missing(s) == ["SES_SECRET_ACCESS_KEY", "EMAIL_FROM"]
    s = prod(monkeypatch, SMS_PROVIDER="live", EMAIL_PROVIDER="log", PUSH_PROVIDER="log")
    monkeypatch.setattr(s.worker, "TWILIO_ACCOUNT_SID", "")
    missing = production_missing(s)
    assert "EMAIL_PROVIDER (one of: ses, sendgrid)" in missing and "PUSH_PROVIDER (one of: live)" in missing
    assert "TWILIO_ACCOUNT_SID" in missing


def test_worker_checks_nothing_outside_production(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.main import production_missing

    monkeypatch.setattr(get_settings(), "APP_ENV", "test")
    assert production_missing(get_settings()) == []


async def test_fcm_without_keys_is_not_counted_as_sent_in_production(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared.providers.push import Device, FcmPush, PushMessage

    monkeypatch.setattr("app.services.fcm.get_firebase_app", lambda: None)
    devices = [Device(token="fcm-token", provider="fcm")]
    assert (await FcmPush().send(devices, PushMessage("t", "b", {}))).sent == 1  # locally a stand-in
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert (await FcmPush().send(devices, PushMessage("t", "b", {}))).sent == 0


# ── Sentry: off without a DSN ────────────────────────────────────────────────

def test_sentry_off_without_a_dsn(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared import observability

    calls: list[dict] = []
    fake = types.SimpleNamespace(init=lambda **kw: calls.append(kw), set_tag=lambda *a: None)
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setattr(observability, "_sentry_on", False)
    monkeypatch.setattr(get_settings(), "SENTRY_DSN", "")
    observability._sentry("worker")
    assert calls == [] and not observability._sentry_on

    monkeypatch.setattr(get_settings(), "SENTRY_DSN", "https://key@o0.ingest.example/1")
    observability._sentry("worker")
    assert calls[0]["dsn"].endswith("/1") and calls[0]["send_default_pii"] is False
    assert calls[0]["traces_sample_rate"] == 0.0 and observability._sentry_on
