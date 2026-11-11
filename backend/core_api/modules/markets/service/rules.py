"""Market rules that need no database: statuses, inheritance, launch checklist.

Status meanings (every level):
  draft   being set up; customers never see it
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
                     zones: list[ZoneState], now: datetime) -> dict[str, bool]:
    """What a city needs before it can open (shown on the country page as "setup 2 of 5")."""
    return {
        "country_open": country_status in OPEN,
        "state_open": region_status in OPEN,
        "zones_drawn": len(zones) > 0,
        "zone_open": any(z.is_open(now) for z in zones),
        "service_hours_set": bool(service_hours),
    }


def check_city_status(new_status: str, checklist: dict[str, bool]) -> None:
    if new_status not in OPEN:
        return  # draft and paused are always allowed
    missing = [k for k, ok in checklist.items() if not ok]
    if missing:
        words = {
            "country_open": "the country is not open yet",
            "state_open": "the state is not open yet",
            "zones_drawn": "no zones are drawn",
            "zone_open": "no zone is beta or live",
            "service_hours_set": "service hours are not set",
        }
        raise MarketRuleError("Can't open this city: " + "; ".join(words[m] for m in missing))


def check_parent_open(new_status: str, parent_status: str, parent_label: str) -> None:
    """A state can't open inside a draft country, and so on."""
    if new_status in OPEN and parent_status == "draft":
        raise MarketRuleError(f"Can't open this while {parent_label} is still a draft")


# Settings every level shows; country columns seed them, then each level's
# ``settings`` JSON can override any key (None removes an override).
COUNTRY_COLUMNS = ("currency", "locales", "timezone", "distance_unit", "phone_code", "payment_providers", "tax_regime")
LOCKED_BELOW_COUNTRY = frozenset({"currency", "phone_code", "tax_regime"})


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
