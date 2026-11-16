"""Web v2 public markets helpers that need no database."""
from types import SimpleNamespace

from core_api.modules.markets.api.v1.public import emergency_number, public_status, short_region_code, slugify
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
    # a MaxMind-layout file names the state's ISO code too
    rec["subdivisions"] = [{"iso_code": "ID", "names": {"en": "Idaho"}}]
    assert geoip.parse(rec) == geoip.Place("US", "Meridian", "Idaho", 43.61, -116.39, region_code="ID")


def test_short_region_code() -> None:
    regions = [("US-ID", "Idaho"), ("US-WA", "Washington")]
    assert short_region_code("ID", "Idaho", "US", []) == "ID"  # the file's own code wins
    assert short_region_code("US-OR", None, "US", []) == "OR"
    assert short_region_code(None, " idaho ", "US", regions) == "ID"  # else the Markets state of that name
    assert short_region_code(None, "Ohio", "US", regions) is None  # unknown: the line uses the country code
    assert short_region_code(None, None, "US", regions) is None


def test_geoip_private_and_missing() -> None:
    assert geoip.lookup("10.0.0.1") is None and geoip.lookup("127.0.0.1") is None and geoip.lookup("bad") is None
    assert geoip.lookup("8.8.8.8") is None  # no database configured


def test_emergency_number_from_settings() -> None:
    assert emergency_number({"emergency_number": "112"}) == "112"
    assert emergency_number({"emergency_number": " 911 "}) == "911"
    assert emergency_number({}) is None and emergency_number(None) is None  # not set: the app says "local emergency number"
    assert emergency_number({"emergency_number": "call 112"}) is None  # only digits reach a tel: link
    assert emergency_number({"emergency_number": "1234567"}) is None
