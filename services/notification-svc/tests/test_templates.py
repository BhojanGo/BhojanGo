import pytest

from app.services.templates import get_template


def test_en_us_order_created():
    title, body = get_template("order_created", "en-US", order_id="abc123xyz", restaurant_name="Spice Garden")
    assert "ABC123" in body or "ABC123XYZ" in body or "abc123" in body.lower()
    assert len(title) > 0


def test_hi_in_order_confirmed():
    title, body = get_template("order_confirmed", "hi-IN", order_id="xyz", restaurant_name="Test Rest")
    assert "Test Rest" in body
    assert len(title) > 0


def test_en_in_locale():
    title, body = get_template("order_delivered", "en-IN", order_id="xyz")
    assert len(title) > 0
    assert len(body) > 0


def test_fallback_to_en_us():
    title, body = get_template("order_created", "fr-FR", order_id="xyz")
    assert len(title) > 0
    assert len(body) > 0


def test_unknown_event_type():
    title, body = get_template("some_unknown_event", "en-US")
    assert title == "BhojanGo"


def test_all_locales_all_events():
    locales = ["en-US", "en-IN", "hi-IN"]
    events = [
        "order_created", "order_confirmed", "order_preparing",
        "order_ready", "order_picked_up", "order_delivered",
        "order_cancelled", "payment_succeeded", "payment_failed", "driver_assigned",
    ]
    for locale in locales:
        for event in events:
            title, body = get_template(event, locale, order_id="TEST123", restaurant_name="Test", driver_name="Driver", eta="20 mins", amount="500", currency="INR")
            assert len(title) > 0, f"Empty title for {locale}/{event}"
            assert len(body) > 0, f"Empty body for {locale}/{event}"
