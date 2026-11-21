"""R27: "Order again" against today's menu, without a database (catalog/service/cart.py plan_line).

R26: tapping "Order again" on a delivered order failed with "We couldn't add this order to your bag".
Available items go back in the bag with the same options and quantities; an item sold out or gone,
and an option no longer offered, are named, and the rest is still added."""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

from core_api.modules.catalog.service.cart import ReorderProblem, plan_line

KITCHEN = uuid.uuid4()
NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)


def opt(name: str, default: bool = False, available: bool = True) -> NS:
    return NS(id=uuid.uuid4(), name=name, is_default=default, is_available=available)


def group(name: str, options: list, min_picks: int = 0, max_picks: int = 1) -> NS:
    return NS(id=uuid.uuid4(), name=name, options=options, min_picks=min_picks, max_picks=max_picks)


def item(name: str, available: bool = True, sold_out_until=None, deleted=False, kitchen=KITCHEN) -> NS:  # type: ignore[no-untyped-def]
    return NS(id=uuid.uuid4(), name=name, is_available=available, sold_out_until=sold_out_until,
              deleted_at=NOW if deleted else None, restaurant_id=kitchen)


def latte_groups(oat_available: bool = True, with_oat: bool = True) -> list:
    milk = [opt("Whole", default=True), *([opt("Oat", available=oat_available)] if with_oat else []), opt("Almond")]
    return [group("Size", [opt("12 oz", default=True), opt("16 oz")], 1, 1), group("Milk", milk, 1, 1),
            group("Add-ons", [opt("Vanilla"), opt("Extra shot")], 0, 2)]


def names(picks: list[dict] | None) -> list[str]:
    return [p["name"] for p in picks or []]


def test_the_same_options_come_back_as_picks_the_quote_accepts() -> None:
    groups = latte_groups()
    latte = item("Latte")
    picks, problems = plan_line({"menu_item_id": str(latte.id), "name": "Latte", "quantity": 2,
                                 "options": ["16 oz", "Oat", "Vanilla", "Extra shot"]}, latte, groups, KITCHEN, NOW)
    assert problems == []
    assert names(picks) == ["16 oz", "Oat", "Vanilla", "Extra shot"]
    by_id = {str(o.id): (str(g.id), o.name) for g in groups for o in g.options}
    assert all(by_id[p["option"]] == (p["group"], p["name"]) for p in picks or [])  # ids of today's menu


def test_an_item_without_options() -> None:
    croissant = item("Butter Croissant")
    assert plan_line({"name": "Butter Croissant", "options": []}, croissant, [], KITCHEN, NOW) == ([], [])


def test_a_sold_out_item_is_named_and_left_out() -> None:
    croissant = item("Butter Croissant", sold_out_until=NOW + timedelta(hours=3))
    assert plan_line({"name": "Butter Croissant"}, croissant, [], KITCHEN, NOW) == (None, [ReorderProblem("Butter Croissant", "sold_out")])
    off = item("Butter Croissant", available=False)
    assert plan_line({"name": "Butter Croissant"}, off, [], KITCHEN, NOW)[1] == [ReorderProblem("Butter Croissant", "sold_out")]
    # Sold out until earlier today: back on.
    back = item("Butter Croissant", sold_out_until=NOW - timedelta(minutes=1))
    assert plan_line({"name": "Butter Croissant"}, back, [], KITCHEN, NOW) == ([], [])


def test_an_item_gone_from_the_menu() -> None:
    assert plan_line({"name": "Pumpkin Loaf"}, None, [], KITCHEN, NOW) == (None, [ReorderProblem("Pumpkin Loaf", "removed")])
    gone = item("Pumpkin Loaf", deleted=True)
    assert plan_line({"name": "Pumpkin Loaf"}, gone, [], KITCHEN, NOW)[1] == [ReorderProblem("Pumpkin Loaf", "removed")]
    elsewhere = item("Pumpkin Loaf", kitchen=uuid.uuid4())
    assert plan_line({"name": "Pumpkin Loaf"}, elsewhere, [], KITCHEN, NOW)[0] is None


def test_an_option_no_longer_offered_is_named_and_the_item_still_added_with_the_default() -> None:
    latte = item("Latte")
    for groups in (latte_groups(oat_available=False), latte_groups(with_oat=False)):
        picks, problems = plan_line({"name": "Latte", "options": ["16 oz", "Oat"]}, latte, groups, KITCHEN, NOW)
        assert problems == [ReorderProblem("Latte", "option_gone", option="Oat")]
        assert names(picks) == ["16 oz", "Whole"]  # Milk is required: its default


def test_an_optional_add_on_no_longer_offered_is_just_dropped() -> None:
    latte = item("Latte")
    groups = latte_groups()
    groups[2].options = [opt("Vanilla")]  # "Extra shot" removed
    picks, problems = plan_line({"name": "Latte", "options": ["12 oz", "Whole", "Extra shot"]}, latte, groups, KITCHEN, NOW)
    assert problems == [ReorderProblem("Latte", "option_gone", option="Extra shot")]
    assert names(picks) == ["12 oz", "Whole"]


def test_a_required_choice_with_nothing_left_leaves_the_item_out() -> None:
    latte = item("Latte")
    groups = latte_groups()
    groups[1].options = [opt("Whole", default=True, available=False)]
    picks, problems = plan_line({"name": "Latte", "options": ["12 oz", "Whole"]}, latte, groups, KITCHEN, NOW)
    assert picks is None
    assert problems == [ReorderProblem("Latte", "option_gone", option="Whole"), ReorderProblem("Latte", "unavailable")]


def test_options_saved_in_other_shapes_and_cases() -> None:
    latte = item("Latte")
    picks, problems = plan_line({"name": "Latte", "options": [{"group": "Size", "option": "16 OZ"}, {"name": " oat "}, ""]},
                                latte, latte_groups(), KITCHEN, NOW)
    assert problems == [] and names(picks) == ["16 oz", "Oat"]


def test_the_same_option_name_in_two_groups_goes_where_there_is_room() -> None:
    plain = item("Bagel")
    groups = [group("Spread", [opt("None", default=True), opt("Butter")], 1, 1), group("Side", [opt("None"), opt("Fruit")], 0, 1)]
    picks, problems = plan_line({"name": "Bagel", "options": ["Butter", "None"]}, plain, groups, KITCHEN, NOW)
    assert problems == []
    assert [(p["group"], p["name"]) for p in picks or []] == [(str(groups[0].id), "Butter"), (str(groups[1].id), "None")]
