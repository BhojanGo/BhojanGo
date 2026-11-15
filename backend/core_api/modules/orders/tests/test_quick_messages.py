"""B2: no phone numbers in quick messages; one of preset or text. Round 5: each
reader sees a preset in their own language."""
import pytest
from pydantic import ValidationError

from core_api.modules.orders.api.v1.messages import PRESETS, QuickMessageIn, _shown, mask_phone_numbers
from core_api.modules.orders.models import OrderMessage
from shared.texts import LANGUAGES, QUICK_PRESETS, fallback_name, preset_text


@pytest.mark.parametrize("text", ["Call me on 98480 22334", "my no is +91-984-802-2334", "ring (208) 555-0147",
                                  "9848022334 pls"])
def test_phone_numbers_are_masked(text: str) -> None:
    out = mask_phone_numbers(text)
    assert sum(ch.isdigit() for ch in out) < 7 and "•••" in out


@pytest.mark.parametrize("text", ["Flat 302, gate 2", "Block B, 4th floor", "Order #AB12CD", "Back in 5 min"])
def test_everyday_text_is_left_alone(text: str) -> None:
    assert mask_phone_numbers(text) == text


def test_one_of_preset_or_text() -> None:
    QuickMessageIn(preset="outside")
    QuickMessageIn(text="Gate 2 please")
    for bad in ({}, {"text": "   "}, {"preset": "outside", "text": "hi"}, {"text": "x" * 141}):
        with pytest.raises(ValidationError):
            QuickMessageIn(**bad)


def test_presets_never_ask_for_a_call() -> None:
    for side in QUICK_PRESETS.values():
        for texts in side.values():
            assert set(texts) == set(LANGUAGES)  # every language we write in
            for text in texts.values():
                assert "call" not in text.lower() and not any(ch.isdigit() for ch in text)


def test_presets_are_the_english_texts() -> None:
    assert PRESETS["rider"]["outside"] == "I'm outside."
    assert set(PRESETS["customer"]) == {"leave_at_door", "coming_down", "ring_bell", "ask_guard"}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_a_preset_is_shown_in_the_readers_language(lang: str) -> None:
    row = OrderMessage(sender_role="rider", preset="outside", text="I'm outside.")
    assert _shown(row, lang) == QUICK_PRESETS["rider"]["outside"][lang]
    assert _shown(row, lang) == preset_text("rider", "outside", lang)


def test_free_text_stays_as_written() -> None:
    row = OrderMessage(sender_role="customer", preset=None, text="Gate 2 please")
    assert _shown(row, "hi") == "Gate 2 please"
    # A preset that no longer exists: what was stored.
    assert _shown(OrderMessage(sender_role="rider", preset="gone", text="Old words"), "te") == "Old words"


def test_names_when_someone_has_none() -> None:
    assert fallback_name("rider", "en") == "Your rider" and fallback_name("customer", "es") == "El cliente"
    assert fallback_name("rider", "ta") == "உங்கள் ரைடர்"
