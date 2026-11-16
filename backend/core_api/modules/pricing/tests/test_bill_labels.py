"""Bill lines leave the API with today's words (Round 8): an order priced before the
wording change keeps "Tip for your rider" in its pricing snapshot, but every client
reads "Tip for your delivery partner", in the reader's language."""
from core_api.modules.pricing.service.lookup import customer_lines, relabel
from shared.texts import BILL_LINES, LANGUAGES, bill_line_label

OLD = [
    {"code": "food", "label": "Food", "amount": "240.00", "rule_id": "r1"},
    {"code": "tax", "label": "GST", "amount": "12.00", "detail": {"rate_percent": "5"}},
    {"code": "tip", "label": "Tip for your rider", "amount": "20.00"},
]


def test_an_old_tip_reads_delivery_partner_in_english() -> None:
    lines = customer_lines(OLD)
    assert [ln["label"] for ln in lines] == ["Food", "GST", "Tip for your delivery partner"]
    assert all("rule_id" not in ln for ln in lines)  # still no rule ids for the customer
    assert lines[2]["amount"] == "20.00" and lines[1]["detail"] == {"rate_percent": "5"}


def test_the_tip_in_the_readers_language() -> None:
    assert customer_lines(OLD, "te-IN")[2]["label"] == "మీ డెలివరీ పార్ట్‌నర్‌కు టిప్"
    assert customer_lines(OLD, "hi-IN")[2]["label"] == "आपके डिलीवरी पार्टनर के लिए टिप"
    assert customer_lines(OLD, "es-US")[2]["label"] == "Propina para tu repartidor"
    assert customer_lines(OLD, "fr-FR")[2]["label"] == "Tip for your delivery partner"  # not written: English
    assert customer_lines(OLD, None)[2]["label"] == "Tip for your delivery partner"


def test_other_lines_keep_their_stored_label() -> None:
    out = relabel([{"code": "promotion", "label": "Code BHOJAN10", "amount": "-50"}, {"label": "no code", "amount": "1"}])
    assert [ln["label"] for ln in out] == ["Code BHOJAN10", "no code"]
    assert bill_line_label("delivery_fee", "Delivery · 4.2 km", "hi") == "Delivery · 4.2 km"


def test_every_language_has_the_tip_and_none_says_rider() -> None:
    assert set(BILL_LINES["tip"]) == set(LANGUAGES)
    for text in BILL_LINES["tip"].values():
        assert "rider" not in text.lower()
