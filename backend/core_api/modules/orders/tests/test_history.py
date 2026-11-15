"""Order history filters and summaries, and what account deletion leaves on an order."""
from core_api.modules.orders.service.history import items_summary, statuses_for
from core_api.modules.orders.service.lookup import scrub_delivery_address
from core_api.modules.orders.service.state_machine import ACTIVE_STATES


def test_status_filters() -> None:
    assert statuses_for(None) is None and statuses_for([]) is None
    assert statuses_for(["delivered"]) == {"delivered"}
    assert statuses_for(["delivered", "cancelled"]) == {"delivered", "cancelled"}
    active = statuses_for(["active"])
    assert active == set(ACTIVE_STATES) and "placed" in active and "delivered" not in active


def test_items_summary() -> None:
    assert items_summary([]) == ""
    assert items_summary([{"name": "Veg Dum Biryani", "quantity": 2}, {"name": "Raita", "quantity": 1}]) == \
        "2 × Veg Dum Biryani, Raita"
    many = [{"name": n, "quantity": 1} for n in ("A", "B", "C", "D", "E")]
    assert items_summary(many) == "A, B, C +2 more"


def test_deleted_accounts_keep_only_the_tax_jurisdiction_on_orders() -> None:
    before = {"street": "Flat 302, Road 36", "landmark": "Opp. temple", "city": "Hyderabad", "state": "Telangana",
              "zip": "500081", "country": "IN", "lat": 17.44, "lng": 78.39}
    after = scrub_delivery_address(before)
    assert after == {"city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN",
                     "street": "", "landmark": None}
    assert scrub_delivery_address(None) == {"street": "", "landmark": None}
