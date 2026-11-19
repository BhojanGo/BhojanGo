"""What the markets-only seed (tools/seed/markets.py) writes: production's base data, chosen
from the base seed's data (data.py) with no database (standard library; markets_test.py).

Srini's decisions (R19): production opens Boise only; India's markets are kept, switched off;
no demo kitchens, users, orders or payout accounts.

- Countries, states, cities and zones from data.COUNTRIES, with the legal entity names
  (settings.legal.name: DeepTrics LLC, DeepTrics Software Solutions Pvt Ltd).
  Statuses: the production cities (PRODUCTION_CITIES) are live; every other city that was open
  (beta or live) is a draft, with its zones; a state or country left with no open city is a
  draft (India). Cities announced as "soon" stay "soon" (shown only where the country is open).
- Rules from data.RULES: country, state, city and platform rules (US commission 15%, India's
  R16 tax rules, payment fees, delivery fees, pay for delivery partners, ...). Not the ones for
  a seed kitchen (restaurant scope) and no promotions (a launch offer is a business decision).
- Terms and Privacy (legal/<CC>-<kind>.md) as unpublished drafts, for the lawyer's text to be
  pasted over and published in the admin console (Content -> Legal).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import COUNTRIES, RULES  # noqa: E402

PRODUCTION_CITIES = ("US-ID-BOI",)
OPEN = frozenset({"beta", "live"})
SKIPPED_FAMILIES = frozenset({"promotion"})


def markets(countries: list[dict] = COUNTRIES, live: tuple[str, ...] = PRODUCTION_CITIES) -> list[dict]:
    """data.COUNTRIES with production's statuses (a copy; the base seed's data is unchanged)."""
    out = copy.deepcopy(countries)
    for c in out:
        country_open = False
        for r in c["regions"]:
            region_open = False
            for city in r["cities"]:
                if city["code"] in live:
                    city["status"] = "live"
                    region_open = True
                elif city["status"] in OPEN:
                    city["status"] = "draft"
                    city["zones"] = [(name, bounds, m, "draft", color) for name, bounds, m, _, color in city["zones"]]
            if region_open:
                r["status"] = "live"
            elif r["status"] in OPEN:
                r["status"] = "draft"
            country_open = country_open or region_open
        if country_open:
            c["status"] = "live"
        elif c["status"] in OPEN:
            c["status"] = "draft"
    return out


def rules(all_rules: list[tuple] = RULES) -> list[tuple]:
    """The market rules (no seed kitchen's rules, no promotions)."""
    return [r for r in all_rules if r[4] != "restaurant" and r[0] not in SKIPPED_FAMILIES]


def city_statuses(ms: list[dict]) -> dict[str, str]:
    return {city["code"]: city["status"] for c in ms for r in c["regions"] for city in r["cities"]}


def legal_entities(ms: list[dict]) -> dict[str, str]:
    return {c["code"]: (c["settings"].get("legal") or {}).get("name", "") for c in ms}
