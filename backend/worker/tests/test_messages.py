"""P15 messages: every message in English, Hindi and Telugu, in the brand voice."""
import re
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.services import messages as m

PARAMS = {"restaurant": "Spice Route Kitchen", "code": "#AB12CD", "eta": "8:24 PM", "rider": "Imran",
          "refund": "₹638.22", "amount": "₹187.00", "items": 3, "total": "₹638.22", "accept_by": "8:03 PM",
          "period": "3–9 Nov", "name": "Imran", "text": "I'm outside."}
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
DEVANAGARI, TELUGU = re.compile("[ऀ-ॿ]"), re.compile("[ఀ-౿]")


@pytest.mark.parametrize("key", sorted(m.CATALOGUE))
@pytest.mark.parametrize("lang", m.LANGUAGES)
def test_every_message_renders_in_every_language(key: str, lang: str) -> None:
    r = m.render(key, lang, **PARAMS)
    text = r.title + r.body
    assert "{" not in text and "}" not in text
    assert not EMOJI.search(text), "brand voice: no emoji"
    translated = r.title if key in m.VERBATIM else r.body  # a quick message is the sender's own words
    if lang == "hi":
        assert DEVANAGARI.search(translated)
    if lang == "te":
        assert TELUGU.search(translated)
    # SMS with ₹ or Indian scripts is UCS-2: 70 characters a part; keep to 3 parts.
    assert len(r.sms) <= 201, len(r.sms)
    assert r.dlt_template == f"{key}_{lang}"


def test_board_voice_samples() -> None:
    assert m.render("order_preparing", "en", restaurant="Spice Route", eta="8:24 PM").body == \
        "Spice Route is cooking your order. Arriving around 8:24 PM."
    assert m.render("payment_failed", "en", code="#AB12CD").body.startswith(
        "Payment didn't go through. You have not been charged.")


def test_eta_sentence_left_out_without_an_estimate() -> None:
    assert m.render("order_preparing", "en", restaurant="Spice Route", eta=None).body == \
        "Spice Route is cooking your order."
    assert m.render("order_preparing", "te", restaurant="Spice Route", eta="8:24 PM").body.endswith("సుమారు 8:24 PMకి చేరుతుంది.")


def test_item_counts_read_naturally() -> None:
    one = m.render("partner_new_order", "en", code="#A", items=1, total="₹99.00", accept_by="8:03 PM")
    assert one.body == "1 item, ₹99.00. Accept by 8:03 PM."
    assert m.render("partner_new_order", "te", code="#A", items=3, total="₹99.00", accept_by="8:03 PM").body.startswith(
        "3 ఐటమ్స్, ₹99.00.")


def test_dlt_variables_are_only_the_ones_used() -> None:
    r = m.render("order_picked_up", "hi", **PARAMS)
    assert set(r.params) == {"rider", "arriving"}


@pytest.mark.parametrize("locale,lang", [("hi-IN", "hi"), ("te-IN", "te"), ("en-IN", "en"), ("en-US", "en"),
                                         ("fr-FR", "en"), (None, "en")])
def test_language_from_locale(locale: str | None, lang: str) -> None:
    assert m.language_for(locale) == lang


def test_money() -> None:
    assert m.money(Decimal("638.22"), "INR") == "₹638.22"
    assert m.money(Decimal("124050"), "INR") == "₹1,24,050.00"
    assert m.money(Decimal("12405000.5"), "INR") == "₹1,24,05,000.50"
    assert m.money(Decimal("1240.5"), "USD") == "$1,240.50"
    assert m.minor_to_money(63822, "INR") == "₹638.22"
    assert m.minor_to_money(1696, "USD") == "$16.96"


def test_clock_in_the_city_time_zone() -> None:
    at = datetime(2026, 11, 14, 14, 54, tzinfo=UTC)
    assert m.clock(at, "Asia/Kolkata") == "8:24 PM"
    assert m.clock(at.isoformat(), "America/Boise") == "7:54 AM"
    assert m.clock(None, "Asia/Kolkata") is None


def test_order_code_and_period() -> None:
    assert m.order_code("ab12cd34-0000-0000-0000-000000000000") == "#AB12CD"
    assert m.period(date(2026, 11, 3), date(2026, 11, 10)) == "3–9 Nov"
    assert m.period(date(2026, 10, 27), date(2026, 11, 3)) == "27 Oct – 2 Nov"


def test_email_escapes_and_brands() -> None:
    r = m.render("order_delivered", "en", restaurant="Tom & Jerry's <Diner>")
    page = m.email_html(r, total="$39.73", code="#AB12CD")
    assert "Tom &amp; Jerry&#x27;s &lt;Diner&gt;" in page and "<Diner>" not in page
    assert "#0B5D66" in page and "Total $39.73" in page and 'lang="en"' in page
