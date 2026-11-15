"""Order history for the web's account area: filters and the one-line summary."""
from core_api.modules.orders.service.state_machine import ACTIVE_STATES

# What the history's status filter means in order states.
HISTORY_STATUSES: dict[str, frozenset[str]] = {
    "delivered": frozenset({"delivered"}),
    "cancelled": frozenset({"cancelled"}),
    "active": ACTIVE_STATES,
}


def statuses_for(filters: list[str] | None) -> set[str] | None:
    if not filters:
        return None
    return set().union(*(HISTORY_STATUSES[f] for f in filters))


def items_summary(items: list[dict] | None, shown: int = 3) -> str:
    """'2 × Veg Dum Biryani, Raita +2 more': quantities above one, the first few names."""
    parts = []
    for it in (items or [])[:shown]:
        qty = int(it.get("quantity", 1) or 1)
        name = str(it.get("name") or "Item")
        parts.append(f"{qty} × {name}" if qty > 1 else name)
    more = len(items or []) - shown
    return ", ".join(parts) + (f" +{more} more" if more > 0 else "")
