"""Market rules that need no database: statuses, inheritance, launch checklist.

Status meanings (every level):
  draft   being set up; customers never see it
  soon    announced: the website lists it as "coming soon" and collects sign-ups,
          but nobody can order there yet
  beta    open to customers, flagged as beta (soft launch)
  live    open to customers
  paused  temporarily closed (e.g. heavy rain); comes back without new setup

Customers can order only where the whole chain is open: country, state, city
and zone each beta or live.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

OPEN = frozenset({"beta", "live"})
# Shown to the public (the website's directory): open, or announced as coming soon.
PUBLIC = OPEN | {"soon"}


class MarketRuleError(ValueError):
    """A change the market rules don't allow; the message is shown to admins."""


@dataclass(frozen=True)
class ZoneState:
    status: str
    paused_until: datetime | None = None

    def is_open(self, now: datetime) -> bool:
        if self.status == "paused" and self.paused_until is not None and self.paused_until <= now:
            return True  # the pause has run out
        return self.status in OPEN


def chain_open(*statuses: str) -> bool:
    return all(s in OPEN for s in statuses)


def launch_checklist(*, country_status: str, region_status: str, service_hours: dict | None,
                     zones: list[ZoneState], now: datetime, priced: bool, payout_provider: str) -> dict[str, bool]:
    """What a city needs before it can open (shown on the country page as "setup 2 of 5")."""
    return {
        "country_open": country_status in OPEN,
        "state_open": region_status in OPEN,
        "zones_drawn": len(zones) > 0,
        "zone_open": any(z.is_open(now) for z in zones),
        "service_hours_set": bool(service_hours),
        # a delivery fee applies (the city's own or the country's default): without
        # one no order can be priced, and the website would list no kitchens
        "pricing_set": priced,
        # someone pays the kitchens and riders (the country's payout provider in Markets)
        "payouts_set": payout_provider != "none",
    }


def check_city_status(new_status: str, checklist: dict[str, bool]) -> None:
    if new_status not in OPEN:
        return  # draft, soon and paused are always allowed
    missing = [k for k, ok in checklist.items() if not ok]
    if missing:
        words = {
            "country_open": "the country is not open yet",
            "state_open": "the state is not open yet",
            "zones_drawn": "no zones are drawn",
            "zone_open": "no zone is beta or live",
            "service_hours_set": "service hours are not set",
            "pricing_set": "no delivery fee applies (add one in Pricing, for the city or the country)",
            "payouts_set": "the country has no payout provider (choose one on the country's page in Markets)",
        }
        raise MarketRuleError("Can't open this city: " + "; ".join(words[m] for m in missing))


def check_country_payouts(status: str, payout_provider: str, *, production: bool) -> None:
    """A country opens only with a payout provider; production never uses the fake one."""
    if payout_provider == "fake" and production:
        raise MarketRuleError("The fake payout provider moves no money: production needs Stripe Connect or Razorpay Route")
    if status in OPEN and payout_provider == "none":
        raise MarketRuleError("Can't open this country: it has no payout provider, so kitchens and delivery partners couldn't be "
                              "paid. Choose one (Payout provider) first")


def check_country_languages(status: str, locales: list[str] | tuple[str, ...]) -> None:
    """A country opens only in languages we have words for: the website, the apps,
    notifications and quick messages are written in shared/texts.py LANGUAGES
    (tools/i18n/check_locales.py keeps them complete for every open country)."""
    from shared.texts import LANGUAGES

    if status not in OPEN:
        return
    missing = [loc for loc in locales if loc.replace("_", "-").split("-")[0].lower() not in LANGUAGES]
    if missing:
        raise MarketRuleError(f"Can't open this country in {', '.join(missing)}: BhojanGo has no translations for "
                              f"{'that language' if len(missing) == 1 else 'those languages'} yet. Remove "
                              f"{'it' if len(missing) == 1 else 'them'} from the locales, or add the translations first")


def check_parent_open(new_status: str, parent_status: str, parent_label: str) -> None:
    """A state can't open inside a draft country, and so on."""
    if new_status in OPEN and parent_status == "draft":
        raise MarketRuleError(f"Can't open this while {parent_label} is still a draft")


# Settings every level shows; country columns seed them, then each level's
# ``settings`` JSON can override any key (None removes an override).
COUNTRY_COLUMNS = ("currency", "locales", "timezone", "distance_unit", "phone_code", "payment_providers", "tax_regime")
# hero_photo: the website's landing hero is per country (service/photos.py)
LOCKED_BELOW_COUNTRY = frozenset({"currency", "phone_code", "tax_regime", "hero_photo"})


def effective_settings(country: Any, region: Any, city: Any) -> list[dict]:
    """Merge country -> region -> city; each value says where it comes from."""
    out: dict[str, dict] = {}

    def put(key: str, value: Any, level: str, name: str) -> None:
        if value is None:
            return
        out[key] = {"key": key, "value": value, "source": name, "source_level": level}

    for col in COUNTRY_COLUMNS:
        put(col, getattr(country, col), "country", country.name)
    for k, v in (country.settings or {}).items():
        put(k, v, "country", country.name)
    if region is not None:
        put("timezone", region.timezone, "region", region.name)
        for k, v in (region.settings or {}).items():
            if k not in LOCKED_BELOW_COUNTRY:
                put(k, v, "region", region.name)
    if city is not None:
        put("timezone", city.timezone, "city", city.name)
        put("service_hours", city.service_hours, "city", city.name)
        for k, v in (city.settings or {}).items():
            if k not in LOCKED_BELOW_COUNTRY:
                put(k, v, "city", city.name)
    return sorted(out.values(), key=lambda s: s["key"])


def merge_settings(current: dict, patch: dict) -> dict:
    """Apply a settings patch: a value sets an override, None removes it (reset to inherited)."""
    merged = dict(current or {})
    for k, v in patch.items():
        if v is None:
            merged.pop(k, None)
        else:
            merged[k] = v
    return merged


def check_overrides(patch: dict) -> None:
    locked = sorted(set(patch) & LOCKED_BELOW_COUNTRY)
    if locked:
        raise MarketRuleError(f"Only the country sets {', '.join(locked)}")
