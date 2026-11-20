"""R19: review-only cities (markets.service.review) and the command that makes the
store review accounts (tools/review_accounts.py): the parts without a database.
The whole flow on Postgres: core_api/integration/test_review_accounts.py."""
import importlib.util
import uuid
from pathlib import Path

import pytest

from core_api.modules.markets.service import review

ME, SOMEONE = uuid.uuid4(), uuid.uuid4()
REVIEW = {"review_only": True, "review_accounts": [str(ME)]}


def command():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[4] / "tools" / "review_accounts.py"
    spec = importlib.util.spec_from_file_location("review_accounts", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_only_the_listed_accounts_see_a_review_only_city() -> None:
    assert review.may_see({}, None) and review.may_see(None, SOMEONE)  # every other city: everyone
    assert review.may_see(REVIEW, ME) and review.may_see(REVIEW, str(ME))
    assert not review.may_see(REVIEW, SOMEONE) and not review.may_see(REVIEW, None)
    assert not review.may_see({"review_only": True}, ME)  # nobody listed: nobody
    assert not review.is_review_only({"review_only": False}) and review.is_review_only(REVIEW)


def test_review_accounts_are_only_those_of_a_review_only_city() -> None:
    """R20: only a review account in its review-only city orders for free."""
    assert review.is_review_account(REVIEW, ME) and review.is_review_account(REVIEW, str(ME))
    assert not review.is_review_account(REVIEW, SOMEONE) and not review.is_review_account(REVIEW, None)
    assert not review.is_review_account({"review_accounts": [str(ME)]}, ME)  # listed, but not a review city
    assert not review.is_review_account({"review_only": False, "review_accounts": [str(ME)]}, ME)
    assert not review.is_review_account({}, ME) and not review.is_review_account(None, ME)


def test_hidden_cities_and_kitchens_per_viewer() -> None:
    cities = [("US-ID-BOI", "Boise", "US", {}), ("US-ID-REV", "App Review", "US", REVIEW)]
    anyone = review.hidden_from(cities, None)
    assert anyone.codes == {"US-ID-REV"} and not anyone.sees_review
    assert anyone.city("US-ID-REV") and not anyone.city("US-ID-BOI") and not anyone.city(None)
    assert anyone.kitchen("us", " app review ") and not anyone.kitchen("US", "Boise") and not anyone.kitchen("IN", "App Review")
    assert review.hidden_from(cities, SOMEONE) == anyone
    mine = review.hidden_from(cities, ME)
    assert not mine.codes and not mine.names and mine.sees_review


def test_public_status_hides_a_review_city_unless_asked() -> None:
    from types import SimpleNamespace as NS

    from core_api.modules.markets.api.v1.public import public_status

    country, region = NS(status="live"), NS(status="live")
    city = NS(status="live", settings=REVIEW)
    assert public_status(country, region, city) is None  # type: ignore[arg-type]
    assert public_status(country, region, city, show_review=True) == "live"  # type: ignore[arg-type]
    assert public_status(country, region, NS(status="live", settings={})) == "live"  # type: ignore[arg-type]


# ── the command ──────────────────────────────────────────────────────────────

def test_it_never_runs_on_qa() -> None:
    cmd = command()
    assert cmd.environment_problem({"APP_ENV": "qa"})
    assert cmd.environment_problem({"APP_ENV": "production", "RAILWAY_ENVIRONMENT_NAME": "QA"})
    assert cmd.environment_problem({"APP_ENV": "production"}) is None
    assert cmd.environment_problem({"APP_ENV": "development"}) is None
    assert cmd.main(["--email-domain", "example.com"], env={"APP_ENV": "qa"}) == 1  # before any database


def test_arguments() -> None:
    cmd = command()
    a = cmd.parse_args(["--email-domain", " Example.COM ", "--country", "us", "--centre", "29.5,-141"])
    assert (a.email_domain, a.country, a.centre, a.region, a.code) == ("example.com", "US", (29.5, -141.0), None, None)
    assert cmd.emails("example.com") == {"customer": "review.customer@example.com", "kitchen": "review.kitchen@example.com",
                                         "delivery": "review.delivery@example.com"}
    for bad in (["--email-domain", "not a domain"], ["--email-domain", "x.com", "--centre", "95,0"],
                ["--email-domain", "x.com", "--centre", "nowhere"], []):
        with pytest.raises(SystemExit):
            cmd.parse_args(bad)


def test_city_code_and_zone() -> None:
    cmd = command()
    assert cmd.city_code("US-ID", None) == "US-ID-REV"
    assert cmd.city_code("US-ID", "US-ID-APP") == "US-ID-APP"
    for bad in ("US-WA-REV", "US-ID-TOOLONG", "us-id-rev"):
        with pytest.raises(cmd.Refused):
            cmd.city_code("US-ID", bad)
    assert cmd.centre_for("US", None) == (30.0, -140.0)  # open sea: the North Pacific
    assert cmd.centre_for("IN", (1.0, 2.0)) == (1.0, 2.0)
    with pytest.raises(cmd.Refused):
        cmd.centre_for("IN", None)  # no default spot: the operator picks the open sea
    zone = cmd.square(30.0, -140.0)
    ring = zone["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) == 5
    assert cmd.inside(zone, 30.0, -140.0) and cmd.inside(zone, 30.01, -140.0) and not cmd.inside(zone, 30.2, -140.0)


async def test_the_viewer_of_a_public_route_is_optional() -> None:
    from starlette.requests import Request

    from shared.auth import encode_jwt, optional_viewer

    def asking(header: str | None) -> Request:
        headers = [(b"authorization", header.encode())] if header else []
        return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})

    assert await optional_viewer(asking(None)) is None
    assert await optional_viewer(asking("Bearer not-a-token")) is None  # a bad token: anyone, never a 401
    assert await optional_viewer(asking("Basic abc")) is None
    access = encode_jwt({"sub": str(ME), "type": "access", "exp": 4102444800})
    assert await optional_viewer(asking(f"Bearer {access}")) == ME
    refresh = encode_jwt({"sub": str(ME), "type": "refresh", "exp": 4102444800})
    assert await optional_viewer(asking(f"Bearer {refresh}")) is None



def test_a_review_city_named_like_another_never_hides_the_viewers_own_kitchens() -> None:  # R20
    from core_api.modules.markets.service.review import hidden_from

    me, someone = uuid.uuid4(), uuid.uuid4()
    mine = {"review_only": True, "review_accounts": [str(me)]}
    theirs = {"review_only": True, "review_accounts": [str(someone)]}
    h = hidden_from([("US-ID-REV", "BhojanGo Review", "US", mine), ("US-ID-RV2", "BhojanGo Review", "US", theirs)], me)
    assert not h.kitchen("US", "BhojanGo Review")  # my review city's kitchens stay visible to me
    assert h.city("US-ID-RV2") and not h.city("US-ID-REV")  # the other city itself stays hidden
    assert hidden_from([("US-ID-RV2", "BhojanGo Review", "US", theirs)], me).kitchen("US", "BhojanGo Review")
