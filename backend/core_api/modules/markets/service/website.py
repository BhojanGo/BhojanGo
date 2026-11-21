"""What the website shows for a city (R27): the one place both the website and the admin
console read a city's public status from.

R26: admin Markets showed Boise as "beta" (the city's own status) while the website
listed it live (its public status, which folds beta into live). The directory, discover
and the city pages use ``public_status``; admin Markets shows ``website_status`` next to
the city's own status, from the same rules, so the two can't tell different stories.
"""
from typing import Literal

from core_api.modules.markets.service import review, rules

WebsiteStatus = Literal["live", "beta", "soon", "hidden"]


def public_status(country, region, city, *, show_review: bool = False) -> str | None:  # type: ignore[no-untyped-def]
    """What a visitor sees for a city: "live" (orders open), "soon" (announced), or
    None (hidden: still a draft, or closed). A soon city needs its country to be past
    draft; its state may still be a draft (the state opens with its first city).
    A review-only city (R19, markets.service.review) is hidden too, unless
    ``show_review`` (discover, for one of its review accounts)."""
    if not show_review and review.is_review_only(getattr(city, "settings", None)):
        return None
    if rules.chain_open(country.status, region.status, city.status):
        return "live"
    if city.status == "soon" and country.status != "draft":
        return "soon"
    return None


def is_beta(country, region, city) -> bool:  # type: ignore[no-untyped-def]
    """Open to customers, but the country, state or city is still in beta (soft launch)."""
    return "beta" in (country.status, region.status, city.status)


def website_status(country, region, city) -> WebsiteStatus:  # type: ignore[no-untyped-def]
    """The city as the website lists it: live, live in beta, coming soon, or not shown."""
    st = public_status(country, region, city)
    if st == "live":
        return "beta" if is_beta(country, region, city) else "live"
    return "soon" if st == "soon" else "hidden"
