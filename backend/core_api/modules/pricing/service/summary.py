"""A city's prices in plain numbers for the website, from the rule engine:
the same rules a quote uses, resolved for the city (no zone or kitchen)."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.pricing.schemas import (
    CityPricing,
    DeliveryFeeSummary,
    FeeSlab,
    ServiceFeeSummary,
    SmallOrderFeeSummary,
    TipPresetsOut,
    ZoneMinOrder,
)
from core_api.modules.rules.service.resolver import Candidate


def _d(v: object) -> Decimal:
    return Decimal(str(v))


def _one(resolved: dict[str, Candidate], slot: str) -> Candidate | None:
    """The rule in a slot (or a keyed slot of the same template, e.g. "customer_fee:service_fee:x")."""
    return resolved.get(slot) or next((c for s, c in sorted(resolved.items()) if s.startswith(slot + ":")), None)


def tip_presets(resolved: dict[str, Candidate]) -> TipPresetsOut | None:
    """The tip buttons from the business tip_presets rule (None: no rule, no buttons)."""
    rule = _one(resolved, "business:tip_presets")
    if rule is None or not rule.params.get("amounts"):
        return None
    amounts = [_d(a) for a in rule.params["amounts"]]
    idx = rule.params.get("default_index")
    return TipPresetsOut(amounts=amounts, default_index=idx if isinstance(idx, int) and 0 <= idx < len(amounts) else None)


def delivery_fee(rule: Candidate | None) -> tuple[DeliveryFeeSummary | None, Decimal | None]:
    """The delivery fee rule as plain numbers, and the lowest fee it charges."""
    if rule is None:
        return None, None
    p = rule.params
    if rule.template == "distance_slabs":
        slabs = [FeeSlab(up_to=_d(s["up_to"]), fee=_d(s["fee"])) for s in p.get("slabs", [])]
        beyond = _d(p["beyond_per_unit"]) if p.get("beyond_per_unit") is not None else None
        return (DeliveryFeeSummary(type="distance_slabs", slabs=slabs, beyond_per_unit=beyond),
                min((s.fee for s in slabs), default=None))
    if rule.template == "flat":
        return DeliveryFeeSummary(type="flat", amount=_d(p["amount"])), _d(p["amount"])
    if rule.template == "free_above":
        return (DeliveryFeeSummary(type="free_above", min_subtotal=_d(p["min_subtotal"]), otherwise=_d(p["otherwise"])),
                _d(p["otherwise"]))
    if rule.template == "tier_base":
        tiers = {k: _d(v) for k, v in (p.get("tiers") or {}).items()}
        return DeliveryFeeSummary(type="tier_base", tiers=tiers), min(tiers.values(), default=None)
    return DeliveryFeeSummary(type=rule.template), None


def summarize(resolved: dict[str, Candidate], *, currency: str, distance_unit: str,
              zone_minimums: list[tuple[str, Decimal | None]]) -> CityPricing:
    fee, fee_from = delivery_fee(resolved.get("delivery_fee"))
    sf = _one(resolved, "customer_fee:service_fee")
    so = _one(resolved, "customer_fee:small_order_fee")
    radius = _one(resolved, "business:max_radius")
    return CityPricing(
        currency=currency, distance_unit=distance_unit, delivery_fee=fee, delivery_from=fee_from,
        service_fee=ServiceFeeSummary(percent=_d(sf.params["percent"]), min=_d(sf.params["min"]), max=_d(sf.params["max"]))
        if sf else None,
        small_order_fee=SmallOrderFeeSummary(below=_d(so.params["below"]), fee=_d(so.params["fee"])) if so else None,
        min_order=[ZoneMinOrder(zone=name, min_order=_d(m)) for name, m in zone_minimums if m is not None],
        max_distance=_d(radius.params["distance"]) if radius else None,
        tip_presets=tip_presets(resolved),
    )


async def city_pricing(db: AsyncSession, *, country: str, region: str, city: str, currency: str, distance_unit: str,
                       zone_minimums: list[tuple[str, Decimal | None]], at: datetime | None = None) -> CityPricing:
    """The city's live rules (city, else state, else country, else platform)."""
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    resolved = await RuleService(db).resolve(Context(country=country, region=region, city=city), at)
    return summarize(resolved, currency=currency, distance_unit=distance_unit, zone_minimums=zone_minimums)
