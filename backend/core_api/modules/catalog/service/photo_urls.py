"""Which addresses a dish photo (image_url), a kitchen's cover (cover_url) or logo
(logo_url) may have (R22 security review, S13).

Customers' browsers and apps load these, so before R22 any string went: another
site's image (tracking every visitor), a `javascript:` or `data:` URL, or a very
long string. Now only these are accepted:

- empty (None or ""): no photo;
- our own upload path, /api/v1/uploads/menu-photo/<owner uuid>/<uuid>.<jpg|png|webp>,
  relative or absolute on our API's own origin (PUBLIC_API_URL; the partner app
  saves it absolute), where <owner> is the caller or the kitchen's owner;
- the website's food photo library, /food/<slug>-<width>.webp (the seed's photos);
- https on a configured photo host (AWS_CLOUDFRONT_URL, PHOTO_HOSTS) with no
  user name, password or port.

Outside production, http on localhost, 127.0.0.1 and 10.0.2.2 (the Android
emulator's name for the computer) is also our API's origin, for local runs.
backend/tools/clean_photo_urls.py applies the same check to existing rows.
"""
import re
import uuid
from urllib.parse import urlsplit

MAX_LENGTH = 512
UPLOAD_PATH = re.compile(r"^/api/v1/uploads/menu-photo/(?P<owner>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
                         r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png|webp)$")
LIBRARY_PATH = re.compile(r"^/food/[a-z0-9]+(-[a-z0-9]+)*-\d{2,4}\.webp$")
DEV_HOSTS = ("localhost", "127.0.0.1", "10.0.2.2")


class PhotoUrlError(ValueError):
    """The address isn't one of ours; the message is shown to the kitchen."""


def _origin(url: str) -> tuple[str, str, int | None] | None:
    try:
        p = urlsplit(url)
        return (p.scheme.lower(), (p.hostname or "").lower(), p.port)
    except ValueError:
        return None


def _photo_hosts() -> set[str]:
    from shared.config import get_settings

    c = get_settings().catalog
    hosts = {h.strip().lower() for h in c.PHOTO_HOSTS if h.strip()}
    if c.AWS_CLOUDFRONT_URL:
        o = _origin(c.AWS_CLOUDFRONT_URL if "://" in c.AWS_CLOUDFRONT_URL else f"https://{c.AWS_CLOUDFRONT_URL}")
        if o and o[1]:
            hosts.add(o[1])
    return hosts


def _api_origins() -> set[tuple[str, str, int | None]]:
    from shared.config import get_settings

    s = get_settings()
    out = set()
    api = _origin(s.payments.PUBLIC_API_URL)
    if api and api[1]:
        out.add(api)
    return out


def _is_api_origin(scheme: str, host: str, port: int | None) -> bool:
    from shared.config import get_settings

    if (scheme, host, port) in _api_origins():
        return True
    return not get_settings().production_named and scheme == "http" and host in DEV_HOSTS


def check(value: str | None, owners: set[uuid.UUID] | None = None) -> str | None:
    """The value to store (None or "" unchanged), or PhotoUrlError. ``owners``: whose
    uploads may be used (the caller and the kitchen's owner); None skips that check
    (the shape-only check in the request schema and the cleanup script)."""
    if value is None or value == "":
        return value
    if len(value) > MAX_LENGTH:
        raise PhotoUrlError(f"A photo's address can be up to {MAX_LENGTH} characters")
    if any(ch.isspace() or ord(ch) < 32 for ch in value):
        raise PhotoUrlError("A photo's address can't contain spaces or control characters")
    if value.startswith("/"):
        path = value
        if LIBRARY_PATH.match(path):
            return value
    else:
        try:
            p = urlsplit(value)
            port = p.port
        except ValueError:
            raise PhotoUrlError("That isn't a photo address") from None
        scheme, host = p.scheme.lower(), (p.hostname or "").lower()
        if p.username or p.password or p.query or p.fragment or not host:
            raise PhotoUrlError("That isn't a photo address")
        if scheme == "https" and port is None and host in _photo_hosts():
            return value
        if not _is_api_origin(scheme, host, port):
            raise PhotoUrlError("Upload the photo in the app: photos from other sites can't be used")
        path = p.path
    m = UPLOAD_PATH.match(path)
    if not m:
        raise PhotoUrlError("Upload the photo in the app: photos from other sites can't be used")
    if owners is not None and uuid.UUID(m["owner"]) not in owners:
        raise PhotoUrlError("That photo was uploaded by another account: upload it again")
    return value


def shape_ok(value: str | None) -> bool:
    """True when ``check`` (without the owner check) accepts the value."""
    try:
        check(value)
        return True
    except PhotoUrlError:
        return False
