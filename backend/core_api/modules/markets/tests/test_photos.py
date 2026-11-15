"""A country's landing hero photo (Markets setting hero_photo): library slugs only."""
import pytest

from core_api.modules.markets.service import photos, rules
from core_api.modules.markets.service.rules import MarketRuleError


def test_library_is_the_generated_list() -> None:
    lib = photos.library()
    assert len(lib) >= 10
    assert photos.DEFAULT_HERO in lib
    assert all(s == s.lower() and " " not in s for s in lib)


def test_check_settings() -> None:
    some = sorted(photos.library())[0]
    photos.check_settings({"hero_photo": some})
    photos.check_settings({"hero_photo": None})  # clears the choice
    photos.check_settings({"payment_methods": ["card"]})
    photos.check_settings(None)
    for bad in ("not-a-dish", "../etc/passwd", "", 3, ["poke-bowl"]):
        with pytest.raises(MarketRuleError, match="library"):
            photos.check_settings({"hero_photo": bad})


def test_hero_photo_falls_back_to_the_default() -> None:
    some = sorted(photos.library())[0]
    assert photos.hero_photo({"hero_photo": some}) == some
    assert photos.hero_photo({}) == photos.DEFAULT_HERO
    assert photos.hero_photo(None) == photos.DEFAULT_HERO
    assert photos.hero_photo({"hero_photo": "removed-from-library"}) == photos.DEFAULT_HERO


def test_only_the_country_sets_the_hero() -> None:
    with pytest.raises(MarketRuleError, match="hero_photo"):
        rules.check_overrides({"hero_photo": photos.DEFAULT_HERO})
