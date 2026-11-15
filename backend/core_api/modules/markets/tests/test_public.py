"""Web v2 public markets helpers that need no database."""
from types import SimpleNamespace

from core_api.modules.markets.api.v1.public import public_status, slugify
from shared import geoip


def chain(country: str, region: str, city: str):  # type: ignore[no-untyped-def]
    return SimpleNamespace(status=country), SimpleNamespace(status=region), SimpleNamespace(status=city)


def test_slugify() -> None:
    assert slugify("Visakhapatnam") == "visakhapatnam"
    assert slugify("Coeur d'Alene") == "coeur-d-alene"
    assert slugify("São Paulo") == "sao-paulo"


def test_public_status() -> None:
    assert public_status(*chain("live", "live", "live")) == "live"
    assert public_status(*chain("live", "live", "beta")) == "live"
    assert public_status(*chain("live", "draft", "soon")) == "soon"  # a state opens with its first city
    assert public_status(*chain("draft", "draft", "soon")) is None  # but not inside a draft country
    assert public_status(*chain("live", "live", "draft")) is None
    assert public_status(*chain("live", "live", "paused")) is None


def test_geoip_parse() -> None:
    rec = {"country": {"iso_code": "us"}, "city": {"names": {"en": "Meridian"}},
           "subdivisions": [{"names": {"en": "Idaho"}}], "location": {"latitude": 43.61, "longitude": -116.39}}
    assert geoip.parse(rec) == geoip.Place("US", "Meridian", "Idaho", 43.61, -116.39)
    assert geoip.parse({"country": {"iso_code": "IN"}}) == geoip.Place("IN")
    assert geoip.parse(None) is None and geoip.parse({"country": {}}) is None


def test_geoip_private_and_missing() -> None:
    assert geoip.lookup("10.0.0.1") is None and geoip.lookup("127.0.0.1") is None and geoip.lookup("bad") is None
    assert geoip.lookup("8.8.8.8") is None  # no database configured
