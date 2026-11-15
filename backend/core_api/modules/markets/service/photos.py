"""The food photo library (the website's /food/<slug>-<width>.webp), as Markets sees it.

``photo_library.json`` lists every slug; it is generated from
docs/design/photos/LICENSES.md by tools/photos/credits.py and checked by
``make ci-photos``, so the backend never accepts a photo the website doesn't have.

A country's landing-page hero is its ``hero_photo`` setting (a slug, chosen in
admin: Markets -> country -> Hero dish); a country without one shows
``DEFAULT_HERO``, a photo that isn't any one country's dish.
"""
import json
from functools import cache
from pathlib import Path
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

HERO_SETTING = "hero_photo"
DEFAULT_HERO = "poke-bowl"


@cache
def library() -> frozenset[str]:
    return frozenset(json.loads((Path(__file__).resolve().parent.parent / "photo_library.json").read_text("utf-8")))


def check_settings(settings: dict[str, Any] | None) -> None:
    """A hero photo must be a library slug (None clears it: back to the default)."""
    value = (settings or {}).get(HERO_SETTING)
    if value is None:
        return
    if not isinstance(value, str) or value not in library():
        raise MarketRuleError(f"{value!r} isn't a photo in the library; pick one of the library's dishes")


def hero_photo(settings: dict[str, Any] | None) -> str:
    """The country's chosen hero photo, or the default when it has none (or one since removed)."""
    value = (settings or {}).get(HERO_SETTING)
    return value if isinstance(value, str) and value in library() else DEFAULT_HERO
