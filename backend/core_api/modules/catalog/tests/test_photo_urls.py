"""R22 security review (S13): dish, cover and logo photos are only our own uploads,
the website's food library or our photo host (catalog/service/photo_urls.py).

Imports are inside the tests so the file still collects with the fix reverted
(each test then fails, which is how the fix was proven)."""
import uuid

import pytest
from pydantic import ValidationError

OWNER = uuid.UUID("11111111-2222-3333-4444-555555555555")
FILE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg"
UPLOAD = f"/api/v1/uploads/menu-photo/{OWNER}/{FILE}"

REFUSED = [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(document.cookie)",
    "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
    "https://evil.example.com/pixel.gif",
    "http://evil.example.com" + UPLOAD,  # our path on another host
    "//evil.example.com" + UPLOAD,
    "/api/v1/uploads/view?key=partner_document/x",
    "/api/v1/uploads/menu-photo/../../etc/passwd",
    "/food/../../secret.webp",
    "https://user:pw@localhost:8001" + UPLOAD,
    "/food/" + "a" * 600 + "-800.webp",  # too long
    UPLOAD + " onerror=alert(1)",
]
ACCEPTED = [None, "", UPLOAD, "http://localhost:8001" + UPLOAD, "/food/hyderabadi-chicken-biryani-800.webp"]


@pytest.mark.parametrize("value", REFUSED)
def test_a_menu_item_refuses_a_photo_that_isnt_ours(value: str) -> None:
    from core_api.modules.catalog.schemas.restaurant import MenuItemUpdateRequest

    with pytest.raises(ValidationError):
        MenuItemUpdateRequest(image_url=value)


@pytest.mark.parametrize("value", REFUSED)
def test_a_kitchen_refuses_a_cover_or_logo_that_isnt_ours(value: str) -> None:
    from core_api.modules.catalog.schemas.restaurant import RestaurantUpdateRequest

    with pytest.raises(ValidationError):
        RestaurantUpdateRequest(cover_url=value)
    with pytest.raises(ValidationError):
        RestaurantUpdateRequest(logo_url=value)


@pytest.mark.parametrize("value", ACCEPTED)
def test_our_own_photos_are_accepted(value: str | None) -> None:
    from core_api.modules.catalog.schemas.restaurant import MenuItemUpdateRequest, RestaurantUpdateRequest

    assert MenuItemUpdateRequest(image_url=value).image_url == value
    assert RestaurantUpdateRequest(cover_url=value).cover_url == value


def test_another_accounts_upload_is_refused() -> None:
    from core_api.modules.catalog.service.photo_urls import PhotoUrlError, check

    assert check(UPLOAD, {OWNER}) == UPLOAD
    with pytest.raises(PhotoUrlError):
        check(UPLOAD, {uuid.uuid4()})


def test_a_configured_photo_host_over_https_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from core_api.modules.catalog.service.photo_urls import PhotoUrlError, check
    from shared.config import get_settings

    monkeypatch.setattr(get_settings().catalog, "PHOTO_HOSTS", ["photos.example.com"])
    assert check("https://photos.example.com/dish/1.webp")
    for v in ("http://photos.example.com/dish/1.webp", "https://photos.example.com:8443/1.webp",
              "https://photos.example.com.evil.com/1.webp"):
        with pytest.raises(PhotoUrlError):
            check(v)


def test_production_takes_only_its_own_api_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    from core_api.modules.catalog.service.photo_urls import PhotoUrlError, check
    from shared.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "APP_ENV", "production")
    monkeypatch.setattr(s.payments, "PUBLIC_API_URL", "https://api.example.com")
    assert check("https://api.example.com" + UPLOAD)
    with pytest.raises(PhotoUrlError):
        check("http://localhost:8001" + UPLOAD)


def test_the_cleanup_script_finds_what_the_api_refuses() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "tools" / "clean_photo_urls.py"
    spec = importlib.util.spec_from_file_location("clean_photo_urls", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert all(mod.bad(v) for v in REFUSED)
    assert not any(mod.bad(v) for v in ACCEPTED)
    assert mod.environment_problem({"APP_ENV": "production"}, forced=False)
    assert mod.environment_problem({"RAILWAY_ENVIRONMENT_NAME": "qa"}, forced=False)
    assert mod.environment_problem({"APP_ENV": "development"}, forced=False) is None
