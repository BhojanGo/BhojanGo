"""Review-only cities (R19): where the app store reviewers' accounts live.

A city whose settings say ``{"review_only": true, "review_accounts": ["<user id>", ...]}``
(written by backend/tools/review_accounts.py) is hidden from everyone except the
accounts listed: the public city lists, the website's directory and city pages, the
address search, locate, discover and the public kitchen lists leave it out, and its
kitchens' pages and menus answer 404. The review accounts see it like any live city
(locate, discover, the kitchen's menu), so a reviewer can browse and order.

Only the public, read-side routes honour it. Pricing and order creation don't: they
need a kitchen id and an address inside the hidden zone, which nobody else has.
"""
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.markets.models import City, Country

REVIEW_ONLY = "review_only"
REVIEW_ACCOUNTS = "review_accounts"


def is_review_only(settings: dict | None) -> bool:
    return bool((settings or {}).get(REVIEW_ONLY))


def may_see(settings: dict | None, viewer_id: uuid.UUID | str | None) -> bool:
    """Can this viewer (None: not signed in) see a city with these settings?"""
    if not is_review_only(settings):
        return True
    if viewer_id is None:
        return False
    allowed = (settings or {}).get(REVIEW_ACCOUNTS) or []
    return str(viewer_id) in {str(a) for a in allowed}


@dataclass(frozen=True)
class Hidden:
    """The review-only cities one viewer may not see."""

    codes: frozenset[str] = frozenset()
    names: frozenset[tuple[str, str]] = frozenset()  # (country code, lower-case city name): Restaurant.city is a name
    sees_review: bool = False  # the viewer is a review account (sees at least one review-only city)

    def city(self, code: str | None) -> bool:
        return code is not None and code in self.codes

    def kitchen(self, country: str | None, city_name: str | None) -> bool:
        return ((country or "").upper(), (city_name or "").strip().lower()) in self.names


def hidden_from(cities: Iterable[tuple[str, str, str, dict | None]], viewer_id: uuid.UUID | str | None) -> Hidden:
    """``cities``: (city code, city name, country code, settings) of every city."""
    codes, names, sees = set(), set(), False
    for code, name, country, settings in cities:
        if not is_review_only(settings):
            continue
        if may_see(settings, viewer_id):
            sees = True
            continue
        codes.add(code)
        names.add((country.upper(), name.strip().lower()))
    return Hidden(frozenset(codes), frozenset(names), sees)


async def hidden_for(db: AsyncSession, viewer_id: uuid.UUID | str | None) -> Hidden:
    """The review-only cities this viewer may not see (a handful of cities: read them all)."""
    rows = (await db.execute(select(City.code, City.name, Country.code, City.settings)
                             .join(Country, Country.id == City.country_id))).all()
    return hidden_from(((c, n, k, s) for c, n, k, s in rows), viewer_id)
