"""B2: no phone numbers in quick messages; one of preset or text."""
import pytest
from pydantic import ValidationError

from core_api.modules.orders.api.v1.messages import PRESETS, QuickMessageIn, mask_phone_numbers


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
    for side in PRESETS.values():
        for text in side.values():
            assert "call" not in text.lower() and not any(ch.isdigit() for ch in text)
