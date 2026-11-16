"""Documents a kitchen needs (Markets country setting kitchen_documents): checked
when an admin saves them, and served in the visitor's language with English as the fallback."""
import pytest

from core_api.modules.markets.service import kitchen_docs
from core_api.modules.markets.service.rules import MarketRuleError

FSSAI = {"key": "fssai", "title": {"en": "FSSAI licence", "hi": "FSSAI लाइसेंस"},
         "why": {"en": "Every kitchen that sells food in India needs one."}}


def test_a_good_list_and_clearing_pass() -> None:
    kitchen_docs.check_settings({"kitchen_documents": [FSSAI]})
    kitchen_docs.check_settings({"kitchen_documents": []})
    kitchen_docs.check_settings({"kitchen_documents": None})  # clears it
    kitchen_docs.check_settings({"hero_photo": "x"})  # not this setting


@pytest.mark.parametrize("bad", [
    "FSSAI",  # not a list
    [{"title": {"en": "x"}, "why": {"en": "y"}}],  # no key
    [{"key": "Bad Key", "title": {"en": "x"}, "why": {"en": "y"}}],
    [{"key": "fssai", "title": {"hi": "x"}, "why": {"en": "y"}}],  # no English
    [{"key": "fssai", "title": {"en": "x"}, "why": {"en": "y" * 241}}],  # too long
    [{"key": "fssai", "title": {"en": "x", "hindi": "y"}, "why": {"en": "y"}}],  # not a language code
    [FSSAI, FSSAI],  # twice
    [FSSAI] * 13,
])
def test_a_bad_list_is_refused(bad: object) -> None:
    with pytest.raises(MarketRuleError):
        kitchen_docs.check_settings({"kitchen_documents": bad})


def test_served_in_the_language_with_english_fallback() -> None:
    settings = {"kitchen_documents": [FSSAI]}
    assert kitchen_docs.localized(settings, "hi") == [
        {"key": "fssai", "title": "FSSAI लाइसेंस", "why": "Every kitchen that sells food in India needs one."}]
    assert kitchen_docs.localized(settings, "es")[0]["title"] == "FSSAI licence"
    assert kitchen_docs.localized({}, "en") == []
    assert kitchen_docs.localized(None, "en") == []
