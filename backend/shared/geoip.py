"""Where an IP address seems to be: a hint for the website ("Looks like you're near
..."), never a decision (an address or the visitor's choice always wins).

Zero spend: an optional MaxMind-format database file (for example DB-IP's free
"IP to City Lite", CC BY 4.0, refreshed monthly; credited on the website's
/credits page) at GEOIP_DB_PATH, fetched by tools/geoip/fetch.sh. With no file,
every lookup returns None and the website falls back to the browser's language.
"""
import ipaddress
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from shared.config import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Place:
    country: str  # ISO 3166-1 alpha-2
    city: str | None = None
    region: str | None = None
    lat: float | None = None
    lng: float | None = None


@lru_cache(maxsize=1)
def _reader() -> Any:
    path = get_settings().GEOIP_DB_PATH
    if not path:
        return None
    try:
        import maxminddb

        return maxminddb.open_database(path)
    except (OSError, ValueError) as e:  # missing or unreadable file: no hints, no failure
        log.warning("geoip database not loaded: %s", e)
        return None


def _name(node: Any) -> str | None:
    names = (node or {}).get("names") or {}
    return names.get("en") or next(iter(names.values()), None)


def parse(record: Any) -> Place | None:
    """A database record (MaxMind/DB-IP city or country layout) as a Place."""
    if not isinstance(record, dict):
        return None
    country = ((record.get("country") or {}).get("iso_code") or "").upper()
    if len(country) != 2:
        return None
    loc = record.get("location") or {}
    subdivisions = record.get("subdivisions") or []
    return Place(country=country, city=_name(record.get("city")), region=_name(subdivisions[0]) if subdivisions else None,
                 lat=loc.get("latitude"), lng=loc.get("longitude"))


def lookup(ip: str) -> Place | None:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.is_private or addr.is_loopback or addr.is_reserved:
        return None
    reader = _reader()
    if reader is None:
        return None
    try:
        return parse(reader.get(str(addr)))
    except Exception as e:  # a bad record must never break a page
        log.warning("geoip lookup failed: %s", e)
        return None
