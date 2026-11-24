"""R39 item 5: the food permit rules without a database."""
from datetime import date
from types import SimpleNamespace

from core_api.modules.catalog.service import permits as P

TODAY = date(2026, 11, 24)


def r(**kw):  # type: ignore[no-untyped-def]
    base = {"food_permit_number": "CDH-12345", "food_permit_expires_on": date(2027, 6, 30), "food_permit_document_key": "k",
            "food_permit_status": "approved"}
    return SimpleNamespace(**{**base, **kw})


def test_going_live_needs_an_approved_unexpired_permit_where_required() -> None:
    assert P.problem(r(), TODAY, True) is None
    assert P.problem(r(food_permit_number=None), TODAY, True) == "Food permit missing"
    assert P.problem(r(food_permit_document_key=None), TODAY, True) == "Food permit missing"
    assert P.problem(r(food_permit_expires_on=date(2026, 11, 23)), TODAY, True) == "Food permit expired"
    assert P.problem(r(food_permit_status="pending"), TODAY, True) == "Food permit not approved yet"
    assert P.problem(r(food_permit_status="rejected"), TODAY, True) == "Food permit not approved yet"
    assert P.problem(r(food_permit_number=None), TODAY, False) is None  # not required (India has FSSAI instead)


def test_expiry() -> None:
    assert not P.expired(r(food_permit_expires_on=TODAY), TODAY)  # valid through its last day
    assert P.expired(r(food_permit_expires_on=date(2026, 11, 23)), TODAY)
    assert not P.expired(r(food_permit_expires_on=None), TODAY)
