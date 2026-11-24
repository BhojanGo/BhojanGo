"""R39 item 6: the paging webhook against a mock receiver (a real local HTTP server)."""
import asyncio

from core_api.integration.mock_webhook import MockWebhook
from shared import paging
from shared.config import get_settings


def test_pages_through_the_webhook(monkeypatch) -> None:
    with MockWebhook() as hook:
        monkeypatch.setattr(get_settings(), "PAGING_WEBHOOK_URL", hook.url)
        assert asyncio.run(paging.page("Orders without a partner", "3 orders in Boise", "critical", {"city": "US-ID-BOI"})) == "sent"
    (got,) = hook.received
    assert got["title"].startswith("[CRITICAL] Orders without a partner")
    assert got["text"].endswith("3 orders in Boise") and got["content"] == got["text"]  # Slack and Discord
    assert got["message"] == "3 orders in Boise" and got["priority"] == 5 and got["details"] == {"city": "US-ID-BOI"}


def test_off_without_a_url_and_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "PAGING_WEBHOOK_URL", "")
    assert asyncio.run(paging.page("x")) == "off"
    with MockWebhook(status=503) as hook:
        monkeypatch.setattr(get_settings(), "PAGING_WEBHOOK_URL", hook.url)
        assert asyncio.run(paging.page("x")) == "failed" and len(hook.received) == 1
    monkeypatch.setattr(get_settings(), "PAGING_WEBHOOK_URL", "http://127.0.0.1:9/nobody-listens")
    monkeypatch.setattr(get_settings(), "PAGING_TIMEOUT_SECONDS", 1.0)
    assert asyncio.run(paging.page("x")) == "failed"
