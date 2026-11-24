"""R36: the restaurant list's order: open and deliverable, then pickup only, then closed, then too far
without pickup; nearest first within each group."""
from types import SimpleNamespace

from core_api.modules.catalog.api.v1.discover import list_order


def card(name: str, *, open_now: bool = True, deliverable: bool = True, pickup_only: bool = False, distance: float = 1.0):
    return SimpleNamespace(name=name, open_now=open_now, deliverable=deliverable, pickup_only=pickup_only, distance=distance)


def test_groups_then_distance() -> None:
    cards = [
        card("closed near", open_now=False, distance=0.2),
        card("too far, no pickup", deliverable=False, distance=9),
        card("pickup only", deliverable=False, pickup_only=True, distance=8),
        card("open far", distance=5),
        card("open near", distance=0.5),
        card("closed and too far, pickup", open_now=False, deliverable=False, pickup_only=True, distance=7),
    ]
    assert [c.name for c in sorted(cards, key=list_order)] == [
        "open near", "open far", "pickup only", "closed near", "closed and too far, pickup", "too far, no pickup"]


def test_city_page_without_an_address_is_open_first() -> None:
    cards = [card("b closed", open_now=False, distance=None), card("a open", distance=None), card("c open", distance=None)]
    assert [c.name for c in sorted(cards, key=list_order)] == ["a open", "c open", "b closed"]
