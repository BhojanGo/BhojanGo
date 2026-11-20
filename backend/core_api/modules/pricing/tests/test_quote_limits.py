"""R21 security review (S7): price checks are limited per person; 0 turns a limit off,
but never in production."""
import pytest

from core_api.modules.pricing.api.v1.pricing import quote_limits
from shared.config import get_settings


def test_default_limits() -> None:
    assert quote_limits() == [(60, 60), (86400, 2000)]


def test_zero_turns_a_limit_off_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "QUOTE_LIMIT_PER_MINUTE", 0)
    assert quote_limits() == [(86400, 2000)]
    monkeypatch.setattr(get_settings(), "QUOTE_LIMIT_PER_DAY", 0)
    assert quote_limits() == []


def test_production_always_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.setattr(get_settings(), "QUOTE_LIMIT_PER_MINUTE", 0)
    monkeypatch.setattr(get_settings(), "QUOTE_LIMIT_PER_DAY", 0)
    assert quote_limits() == [(60, 60), (86400, 2000)]
