"""Local providers: selection, production guard, and notify.send delivery."""
import pytest

from shared import notify
from shared.config import get_settings
from shared.providers import ProviderConfigError
from shared.providers.email import LogEmail, SmtpEmail, get_email_provider
from shared.providers.push import LogPush, get_push_provider
from shared.providers.sms import LogSms, get_sms_provider


def test_defaults_are_local_and_need_no_account() -> None:
    assert isinstance(get_sms_provider(), LogSms)
    assert isinstance(get_push_provider(), LogPush)
    assert isinstance(get_email_provider(), LogEmail)


def test_smtp_selected_for_mailpit(monkeypatch) -> None:
    monkeypatch.setattr(get_settings().providers, "EMAIL_PROVIDER", "smtp")
    assert isinstance(get_email_provider(), SmtpEmail)


@pytest.mark.parametrize("getter", [get_sms_provider, get_push_provider, get_email_provider])
def test_log_providers_refused_in_production(monkeypatch, getter) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(ProviderConfigError):
        getter()


async def test_notify_without_queue_delivers_in_process(monkeypatch, capsys) -> None:
    monkeypatch.setattr(get_settings().worker, "SQS_QUEUE_URL_NOTIFICATION", "")
    assert await notify.send("sms", "+9190000101", "Your BhojanGo verification code is: 123456", country="IN")
    assert "[SMS to +9190000101] Your BhojanGo verification code is: 123456" in capsys.readouterr().out


async def test_dispatcher_delivers_notify_events(capsys) -> None:
    from app.services.dispatcher import dispatch_event

    event = {"event_type": notify.EVENT_TYPE,
             "payload": {"channel": "sms", "to": "+120855500101", "body": "hello", "country": "US"}}
    await dispatch_event(event, db=None)  # type: ignore[arg-type]  # notify.send never touches the DB
    assert "[SMS to +120855500101] hello" in capsys.readouterr().out


def test_fixed_otp_only_for_seed_phones_outside_production(monkeypatch) -> None:
    from core_api.modules.identity.service.otp import _fixed_code_for

    assert _fixed_code_for("+9190000101") == "123456"
    assert _fixed_code_for("+120855500101") == "123456"
    assert _fixed_code_for("+919876543210") is None
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert _fixed_code_for("+9190000101") is None
