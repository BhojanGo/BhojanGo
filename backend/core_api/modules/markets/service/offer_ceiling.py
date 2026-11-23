"""The most a kitchen's own offer may give (R22 security review, S11).

A kitchen funds its own offers (catalog/api/v1/partner.py): they come off its weekly
statement. Before R22 a flat amount off and the weekly cap had no ceiling, so a
kitchen working with a customer could give away more than it earns, take its
statement below zero, and leave BhojanGo with the loss.

The ceiling is a Markets setting, ``kitchen_offer_ceiling``, in the country's currency:

    {"flat_off": "200", "max_discount": "200", "weekly_cap": "25000"}

- ``flat_off``: the most a flat-amount offer takes off one order;
- ``max_discount``: the most a percent-off offer takes off one order (an offer without
  its own maximum gets this one; one above it is refused);
- ``weekly_cap``: the most a kitchen's offers (not ended) may give away in a week, together.

Set per country in admin (Markets, the country's page), and overridden per state or
city (the city's page); a city inherits country -> state -> city like every other
setting (rules.effective_settings). A key missing at every level falls back to
DEFAULTS for the country's currency; a currency with no default and no setting
refuses kitchen offers (fail closed) until an admin sets one.
"""
from decimal import Decimal, InvalidOperation
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

SETTING = "kitchen_offer_ceiling"
KEYS = ("flat_off", "max_discount", "weekly_cap")
MAX_VALUE = Decimal("100000000")  # a typo guard: no ceiling is this large

# Conservative launch values per currency (tools/seed/markets.py sets the same on IN and US).
DEFAULTS: dict[str, dict[str, Decimal]] = {
    "INR": {"flat_off": Decimal("200"), "max_discount": Decimal("200"), "weekly_cap": Decimal("25000")},
    "USD": {"flat_off": Decimal("15"), "max_discount": Decimal("15"), "weekly_cap": Decimal("1500")},
}

WORDS = {"flat_off": "an amount off", "max_discount": "a percent-off offer's most off one order", "weekly_cap": "an offer's weekly cap"}


def _amount(key: str, value: Any) -> Decimal:
    if isinstance(value, bool):
        raise MarketRuleError(f"{SETTING}.{key} must be an amount")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MarketRuleError(f"{SETTING}.{key} must be an amount") from None
    if not d.is_finite() or d <= 0 or d > MAX_VALUE:
        raise MarketRuleError(f"{SETTING}.{key} must be more than 0 and less than {MAX_VALUE:,}")
    return d


def check_settings(patch: dict) -> None:
    """When an admin saves settings: the ceiling (if in the patch and not None, which resets
    it to the inherited value) is an object of positive amounts with known keys."""
    if SETTING not in patch or patch[SETTING] is None:
        return
    value = patch[SETTING]
    if not isinstance(value, dict) or not value:
        raise MarketRuleError(f"{SETTING} must be an object such as {{\"flat_off\": \"200\", \"weekly_cap\": \"25000\"}}")
    unknown = sorted(set(value) - set(KEYS))
    if unknown:
        raise MarketRuleError(f"{SETTING} takes only {', '.join(KEYS)} (not {', '.join(unknown)})")
    for k, v in value.items():
        _amount(k, v)


def ceiling(levels: list[dict | None], currency: str) -> dict[str, Decimal]:
    """The ceiling for a city: each key from the nearest level that sets it (``levels`` are the
    country's, the state's and the city's ``settings``, in that order), else the currency's default.
    A city that sets only flat_off keeps its country's weekly_cap."""
    out = dict(DEFAULTS.get(currency, {}))
    for settings in levels:
        value = (settings or {}).get(SETTING)
        if not isinstance(value, dict):
            continue
        for k, v in value.items():
            if k in KEYS:
                try:
                    out[k] = _amount(k, v)
                except MarketRuleError:
                    continue  # a bad stored value never replaces a good one
    return out


async def for_restaurant(db: Any, restaurant: Any) -> dict[str, Decimal]:
    """The ceiling where this kitchen is (its city's chain; its country's when it has no city)."""
    from sqlalchemy import select

    from core_api.modules.catalog.service.lookup import restaurant_city_code
    from core_api.modules.markets.models import City, Country, Region

    code = await restaurant_city_code(db, restaurant.id)
    city = (await db.execute(select(City).where(City.code == code))).scalars().first() if code else None
    if city is not None:
        country, region = await db.get(Country, city.country_id), await db.get(Region, city.region_id)
        levels = [getattr(country, "settings", None), getattr(region, "settings", None), city.settings]
    else:
        country = (await db.execute(select(Country).where(Country.code == restaurant.country))).scalars().first()
        levels = [getattr(country, "settings", None)]
    return ceiling(levels, getattr(country, "currency", None) or restaurant.currency)


class OfferOverCeiling(ValueError):
    """The offer gives more than the kitchen's market allows; the message is shown to the kitchen."""


def apply(template: str, params: dict, limits: dict[str, Decimal], currency: str, running: Decimal = Decimal(0)) -> dict:
    """The offer's params within the ceiling (a percent-off without its own maximum gets the
    market's), or OfferOverCeiling. ``running``: the weekly caps of the kitchen's other offers
    (not ended): together they stay within the weekly cap, so more offers don't mean more loss."""
    def over(key: str, asked: Decimal) -> None:
        cap = limits.get(key)
        if cap is None:
            raise OfferOverCeiling(f"BhojanGo hasn't set offer limits for {currency} yet, so restaurant offers can't start here. "
                                   "Contact your partner manager")
        if asked > cap:
            raise OfferOverCeiling(f"The most {WORDS[key]} can be here is {cap.normalize():f} {currency}")

    out = dict(params)
    asked = Decimal(str(params["weekly_cap"]))
    over("weekly_cap", asked)
    if running and limits.get("weekly_cap") is not None and asked + running > limits["weekly_cap"]:
        left = max(limits["weekly_cap"] - running, Decimal(0))
        raise OfferOverCeiling(f"This restaurant's offers together can give at most {limits['weekly_cap'].normalize():f} {currency} a week; "
                               f"its other offers already use {running.normalize():f}, so this one can have a weekly cap of up to "
                               f"{left.normalize():f}. End an offer to make room")
    if template == "flat_off":
        over("flat_off", Decimal(str(params["amount"])))
    elif template == "percent_off":
        if params.get("max_discount") is None:
            if limits.get("max_discount") is None:
                over("max_discount", Decimal(0))
            out["max_discount"] = f"{limits['max_discount'].normalize():f}"
        else:
            over("max_discount", Decimal(str(params["max_discount"])))
    return out
