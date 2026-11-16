"""What it takes to deliver with BhojanGo in a country: Markets data, never code.

A country's ``delivery_partner`` setting (admin: Markets -> country -> Delivery
partners) holds what the website's /deliver page promises and asks for::

    {"min_age": 18,
     "vehicles": ["motorcycle", "scooter"],
     "documents": ["driving_licence", "vehicle_rc_insurance", "bank_account", "background_check"],
     "example_trip": {"distance": 3},
     "app_links": {"android": "https://play.google.com/...", "ios": "https://apps.apple.com/..."}}

The words are the website's (one message per key, in every language). Every
document is one the BhojanGo Delivery app actually collects in its onboarding
checklist (identity.api.v1.riders): ``APP_STEP`` says which step, so the page
can't promise a document the app never asks for. Store links stay empty until
the app is published: the page then says how to get the app for now.
"""
from decimal import Decimal, InvalidOperation
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

SETTING = "delivery_partner"
VEHICLES = ("motorcycle", "scooter", "electric_scooter", "car")
# document key -> the onboarding step in the delivery app that collects it
APP_STEP = {
    "driving_licence": "licence",
    "drivers_license": "licence",  # the same, in US words
    "vehicle_rc_insurance": "insurance",  # registration (RC) and insurance, one upload
    "vehicle_insurance": "insurance",
    "bank_account": "payout",
    "payout_account": "payout",
    "background_check": "background_check",
}
STORES = {"android": "https://play.google.com/", "ios": "https://apps.apple.com/"}
DEFAULT_EXAMPLE_DISTANCE = Decimal("3")


def _fail(msg: str) -> None:
    raise MarketRuleError(f"Delivery partners: {msg}")


def check_settings(settings: dict[str, Any] | None) -> None:
    """Refuse a ``delivery_partner`` value the website couldn't show truthfully
    (None clears it)."""
    value = (settings or {}).get(SETTING)
    if value is None:
        return
    if not isinstance(value, dict):
        _fail("expected an object")
    unknown = sorted(set(value) - {"min_age", "vehicles", "documents", "example_trip", "app_links"})
    if unknown:
        _fail(f"unknown field {', '.join(unknown)}")
    age = value.get("min_age")
    if age is not None and (not isinstance(age, int) or isinstance(age, bool) or not 16 <= age <= 25):
        _fail("the minimum age is a whole number from 16 to 25")
    vehicles = value.get("vehicles", ["car"])
    if not isinstance(vehicles, list) or not vehicles or any(v not in VEHICLES for v in vehicles) or len(set(vehicles)) != len(vehicles):
        _fail(f"vehicles is a list of {', '.join(VEHICLES)} (at least one)")
    docs = value.get("documents", [])
    if not isinstance(docs, list) or any(d not in APP_STEP for d in docs) or len(set(docs)) != len(docs):
        _fail(f"documents is a list of {', '.join(APP_STEP)}: what the delivery app collects")
    steps = [APP_STEP[d] for d in docs]
    if len(set(steps)) != len(steps):
        _fail("two documents name the same step in the app (e.g. bank_account and payout_account)")
    trip = value.get("example_trip")
    if trip is not None:
        if not isinstance(trip, dict) or set(trip) - {"distance"}:
            _fail("example_trip is {\"distance\": number}")
        try:
            d = Decimal(str(trip.get("distance")))
        except InvalidOperation:
            d = Decimal(0)
        if not Decimal("0.5") <= d <= Decimal("20"):
            _fail("the example trip is 0.5 to 20 km or miles")
    links = value.get("app_links")
    if links is not None:
        if not isinstance(links, dict) or set(links) - set(STORES):
            _fail("app_links is {\"android\": url, \"ios\": url}")
        for store, url in links.items():
            if url is not None and (not isinstance(url, str) or not url.startswith(STORES[store]) or len(url) > 300 or " " in url):
                _fail(f"the {store} link starts with {STORES[store]}")


def terms(settings: dict[str, Any] | None) -> dict[str, Any]:
    """The country's delivery partner terms with safe defaults: a country without
    the setting has no age, vehicles or documents to list (the page leaves those
    lines out), a 3 km/mi example trip and no store links."""
    value = (settings or {}).get(SETTING)
    value = value if isinstance(value, dict) else {}
    links = value.get("app_links") if isinstance(value.get("app_links"), dict) else {}
    trip = value.get("example_trip") if isinstance(value.get("example_trip"), dict) else {}
    try:
        distance = Decimal(str(trip.get("distance", DEFAULT_EXAMPLE_DISTANCE)))
    except InvalidOperation:
        distance = DEFAULT_EXAMPLE_DISTANCE
    return {
        "min_age": value.get("min_age") if isinstance(value.get("min_age"), int) else None,
        "vehicles": [v for v in value.get("vehicles") or [] if v in VEHICLES],
        "documents": [d for d in value.get("documents") or [] if d in APP_STEP],
        "example_distance": distance,
        "app_links": {s: (links.get(s) if isinstance(links.get(s), str) and links[s].startswith(p) else None) for s, p in STORES.items()},
    }
