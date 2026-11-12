"""Quotes: gather the inputs, run the engine, sign the result.

A quote is valid for 10 minutes. The customer's app shows its lines (the fair
bill) and sends the token when placing the order; checkout charges exactly the
quoted total, and the order keeps a pricing snapshot (lines, rule versions,
split) that never changes afterwards.
"""
import json
import uuid
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.service.cart import CartError, price_cart
from core_api.modules.markets.models import City, Country, Region
from core_api.modules.markets.service.markets import MarketService
from core_api.modules.orders.service.lookup import has_previous_orders
from core_api.modules.pricing.models import OrderPricingSnapshot, PromotionSpend
from core_api.modules.pricing.schemas import BillLineOut, QuoteOut, QuoteRequest, SimSide, SimulateOut, SimulateRequest, SplitOut
from core_api.modules.payments.service.tax import TaxAddress, TaxableLine, TaxError, get_tax_provider
from core_api.modules.pricing.service.engine import (
    CartLine,
    ExternalTax,
    NotDeliverable,
    QuoteInputs,
    QuoteResult,
    compute,
    money,
    taxable_amounts,
)
from core_api.modules.rules.service.resolver import Context
from core_api.modules.rules.service.rules import RuleService
from shared.auth import InvalidTokenError, decode_jwt, encode_jwt
from shared.providers.routing import get_routing_provider
from shared.redis import get_redis

QUOTE_TTL = timedelta(minutes=10)
KM_PER_MILE = Decimal("1.609344")


class QuoteError(ValueError):
    """Can't quote or redeem; the message is shown to the customer."""


def _key(quote_id: str) -> str:
    return f"quote:{quote_id}"


def _cart_signature(restaurant_id: str, items: list[dict]) -> list:
    norm = [
        [str(i["menu_item_id"]), int(i["quantity"]), sorted((o["group"], o["option"]) for o in i.get("options", []))]
        for i in items
    ]
    return [restaurant_id, sorted(norm)]


def lines_out(q: QuoteResult) -> list[BillLineOut]:
    return [BillLineOut(code=ln.code, label=ln.label, amount=ln.amount, funded_by=ln.funded_by, detail=ln.detail)
            for ln in q.lines]


def split_out(q: QuoteResult) -> SplitOut:
    s = q.split
    return SplitOut(restaurant=s.restaurant, rider=s.rider, tax=s.tax, platform=s.platform, detail=s.detail)


async def city_chain(db: AsyncSession, code: str) -> tuple[City, Region, Country, ZoneInfo]:
    city = await MarketService(db).repo.city(code)
    if city is None:
        raise QuoteError("City not found")
    region = await db.get(Region, city.region_id)
    country = await db.get(Country, city.country_id)
    assert region is not None and country is not None
    tz = ZoneInfo(city.timezone or region.timezone or country.timezone)
    return city, region, country, tz


class QuoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _promo_spent(self) -> dict[str, Decimal]:
        rows = (await self.db.execute(select(PromotionSpend))).scalars()
        return {str(r.rule_key): Decimal(r.spent) for r in rows}

    async def _deliver_to(self, user_id: uuid.UUID, req: QuoteRequest) -> tuple[float, float, dict]:
        """(lat, lng, postal details) of where the order goes."""
        w = req.deliver_to
        if w.address_id is None:
            return w.lat, w.lng, {"postal_code": w.postal_code}  # type: ignore[return-value]
        from core_api.modules.identity.service.addresses import address_details

        a = await address_details(self.db, user_id, w.address_id)
        if a is None or a["lat"] is None:
            raise QuoteError("We couldn't find that address on the map; drop a pin instead")
        return a["lat"], a["lng"], a

    async def _with_tax(self, inputs: QuoteInputs, rules, result: QuoteResult, region_code: str,  # type: ignore[no-untyped-def]
                        city_name: str, postal: dict) -> tuple[QuoteInputs, QuoteResult]:
        """US: send the taxable lines and the address to the tax provider, then
        price again with the tax it returns. Never quote without tax."""
        if not result.tax_pending:
            return inputs, result
        lines = [TaxableLine(ref, amount) for ref, amount in taxable_amounts(result).items()]
        address = TaxAddress(country=region_code[:2], state=region_code[3:], city=postal.get("city") or city_name,
                             postal_code=postal.get("postal_code"), line1=postal.get("street"))
        try:
            calc = await get_tax_provider().calculate(inputs.currency, lines, address)
        except TaxError as e:
            raise QuoteError(str(e))
        ext = [ExternalTax(b.label, b.rate_percent, b.taxable_amount, b.amount, b.jurisdiction, calc.provider,
                           calc.calculation_id) for b in calc.breakdown]
        inputs = replace(inputs, external_tax=ext)
        return inputs, compute(inputs, rules)

    # ── customer quotes ──────────────────────────────────────────────────────
    async def quote(self, user_id: uuid.UUID, req: QuoteRequest, now: datetime | None = None) -> QuoteOut:
        now = now or datetime.now(UTC)
        items = [i.model_dump(mode="json") for i in req.items]
        try:
            rest, priced = await price_cart(self.db, req.restaurant_id, items, now=now)
        except CartError as e:
            raise QuoteError(str(e))
        lat, lng, postal = await self._deliver_to(user_id, req)

        where = await MarketService(self.db).locate(lat, lng)
        if not where.serviceable:
            raise QuoteError(where.reason or "We don't deliver here yet")
        city, region, country, tz = await city_chain(self.db, where.city_code)  # type: ignore[arg-type]
        if rest.country != country.code:
            raise QuoteError("This restaurant doesn't deliver to that address")
        if rest.lat is None or rest.lng is None:
            raise QuoteError("This restaurant isn't on the map yet")

        km = Decimal(str(get_routing_provider().leg((rest.lat, rest.lng), (lat, lng)).distance_km))
        distance = money(km / KM_PER_MILE if country.distance_unit == "mi" else km)
        food = sum((ln.unit_price * ln.quantity for ln in priced), Decimal(0))
        if where.min_order is not None and food < where.min_order:
            raise QuoteError(f"The minimum order in {where.zone_name} is {country.currency} {where.min_order:.0f}")

        ctx = Context(country=country.code, region=region.code, city=city.code, zone_id=str(where.zone_id),
                      restaurant_id=rest.id)
        rules = await RuleService(self.db).resolve(ctx, now)
        inputs = QuoteInputs(
            currency=country.currency,
            lines=[CartLine(_label(ln), ln.quantity, ln.unit_price, ln.item_id, ln.options) for ln in priced],
            distance=distance, local_time=now.astimezone(tz), tip=req.tip, restaurant_tier=rest.tier,
            first_order=not await has_previous_orders(self.db, user_id),
            promo_code=req.promo_code, promo_spent=await self._promo_spent(),
        )
        try:
            result = compute(inputs, rules)
        except NotDeliverable as e:
            raise QuoteError(str(e))
        inputs, result = await self._with_tax(inputs, rules, result, region.code, city.name, postal)

        quote_id = uuid.uuid4()
        expires = now + QUOTE_TTL
        stored = {
            "quote_id": str(quote_id), "user_id": str(user_id), "restaurant_id": rest.id,
            "restaurant_name": rest.name, "cart": _cart_signature(rest.id, items),
            "items": [{"menu_item_id": ln.item_id, "name": ln.name, "quantity": ln.quantity,
                       "unit_price": str(ln.unit_price), "options": list(ln.options)} for ln in priced],
            "currency": result.currency, "total": str(result.total), "food_subtotal": str(result.food_subtotal),
            "lines": [{**asdict(ln), "amount": str(ln.amount)} for ln in result.lines],
            "tax_calculation": next(({"provider": e.provider, "calculation_id": e.calculation_id}
                                     for e in (inputs.external_tax or [])), None),
            "split": {k: str(v) for k, v in asdict(result.split).items() if k != "detail"}
            | {"detail": {k: str(v) for k, v in result.split.detail.items()}},
            "rules_used": result.rules_used, "tax_pending": result.tax_pending,
            "context": {"country": country.code, "region": region.code, "city": city.code, "zone_id": str(where.zone_id),
                        "zone": where.zone_name, "distance": str(distance), "distance_unit": country.distance_unit,
                        "local_time": inputs.local_time.isoformat(), "deliver_to": {"lat": lat, "lng": lng}},
            "expires_at": expires.isoformat(),
        }
        redis = await get_redis()
        await redis.setex(_key(str(quote_id)), int(QUOTE_TTL.total_seconds()) + 300, json.dumps(stored))
        token = encode_jwt({
            "type": "quote", "sub": str(user_id), "qid": str(quote_id), "total": str(result.total),
            "cur": result.currency, "iat": datetime.now(UTC), "exp": expires,  # iat = when issued; `now` = pricing time
        })
        return QuoteOut(
            quote_id=quote_id, token=token, expires_at=expires, currency=result.currency, lines=lines_out(result),
            total=result.total, tax_pending=result.tax_pending, zone=where.zone_name or "", city=city.name,
            distance=distance, distance_unit=country.distance_unit,
        )

    async def get(self, user_id: uuid.UUID, quote_id: uuid.UUID) -> dict:
        raw = await (await get_redis()).get(_key(str(quote_id)))
        if raw is None:
            raise QuoteError("This quote has expired; we'll price your bag again")
        q = json.loads(raw)
        if q["user_id"] != str(user_id):
            raise QuoteError("This quote has expired; we'll price your bag again")
        return q

    async def redeem(self, token: str, user_id: uuid.UUID, restaurant_id: uuid.UUID, items: list[dict]) -> dict:
        """Check a quote for checkout: signed by us, for this customer, not
        expired, same bag. Returns the stored quote; ``attach`` uses it once."""
        try:
            claims = decode_jwt(token)
        except InvalidTokenError:
            raise QuoteError("Prices have changed since you opened your bag; please review the new total")
        if claims.get("type") != "quote" or claims.get("sub") != str(user_id):
            raise QuoteError("This quote isn't yours")
        q = await self.get(user_id, uuid.UUID(claims["qid"]))
        if q["cart"] != json.loads(json.dumps(_cart_signature(str(restaurant_id), items))):
            raise QuoteError("Your bag changed after it was priced; please review the new total")
        if q["total"] != claims["total"]:
            raise QuoteError("This quote has been tampered with")
        return q

    async def attach(self, q: dict, order_id: uuid.UUID) -> OrderPricingSnapshot:
        """Store the order's pricing snapshot and count promotion spend. Single
        use: the quote is deleted, so it can't price a second order."""
        redis = await get_redis()
        if not await redis.delete(_key(q["quote_id"])):
            raise QuoteError("This quote was already used")
        snap = OrderPricingSnapshot(
            order_id=order_id, quote_id=uuid.UUID(q["quote_id"]), currency=q["currency"], total=Decimal(q["total"]),
            lines=q["lines"], rule_versions=q["rules_used"], split=q["split"],
            context={**q["context"], "tax_calculation": q.get("tax_calculation")},
        )
        self.db.add(snap)
        for ln in q["lines"]:
            if ln["code"] != "promotion" or not ln.get("rule_id"):
                continue
            key = next((r["rule_key"] for r in q["rules_used"] if r["rule_id"] == ln["rule_id"]), None)
            if key is None:
                continue
            row = await self.db.get(PromotionSpend, uuid.UUID(key), with_for_update=True)
            if row is None:
                row = PromotionSpend(rule_key=uuid.UUID(key), currency=q["currency"], spent=Decimal(0), orders=0)
                self.db.add(row)
            row.spent = Decimal(row.spent) - Decimal(ln["amount"])
            row.orders += 1
        await self.db.flush()
        return snap

    async def snapshot(self, order_id: uuid.UUID) -> OrderPricingSnapshot | None:
        q = select(OrderPricingSnapshot).where(OrderPricingSnapshot.order_id == order_id)
        return (await self.db.execute(q)).scalar_one_or_none()

    # ── admin price simulator ────────────────────────────────────────────────
    async def simulate(self, req: SimulateRequest) -> SimulateOut:
        """The same cart priced with live rules and with live + drafts."""
        city, region, country, tz = await city_chain(self.db, req.city)
        if req.cart.items:
            if req.restaurant_id is None:
                raise QuoteError("Pick a restaurant to price menu items")
            try:
                _, priced = await price_cart(self.db, req.restaurant_id, [i.model_dump(mode="json") for i in req.cart.items],
                                             check_open=False)
            except CartError as e:
                raise QuoteError(str(e))
            lines = [CartLine(_label(ln), ln.quantity, ln.unit_price) for ln in priced]
        elif req.cart.food_subtotal is not None:
            lines = [CartLine("Cart", 1, req.cart.food_subtotal)]
        else:
            raise QuoteError("Give menu items or a food subtotal")
        local = req.local_time.replace(tzinfo=tz)
        ctx = Context(country=country.code, region=region.code, city=city.code,
                      zone_id=str(req.zone_id) if req.zone_id else None,
                      restaurant_id=str(req.restaurant_id) if req.restaurant_id else None)
        inputs = QuoteInputs(currency=country.currency, lines=lines, distance=req.distance, local_time=local, tip=req.tip,
                             restaurant_tier=req.restaurant_tier, first_order=req.first_order, promo_code=req.promo_code,
                             promo_spent=await self._promo_spent())
        svc = RuleService(self.db)
        at = local.astimezone(UTC)

        async def side(rules) -> SimSide:  # type: ignore[no-untyped-def]
            try:
                result = compute(inputs, rules)
                _, result = await self._with_tax(inputs, rules, result, region.code, city.name, {})
            except NotDeliverable as e:
                return SimSide(ok=False, message=str(e))
            return SimSide(ok=True, lines=lines_out(result), total=result.total, split=split_out(result), rules=result.rules_used)

        live = await side(await svc.resolve(ctx, at))
        draft = await side(await svc.resolve(ctx, at, overlay_ids=req.draft_rule_ids)) if req.draft_rule_ids else live
        return SimulateOut(currency=country.currency, live=live, draft=draft, changes=_changes(live, draft))


def _label(ln) -> str:  # type: ignore[no-untyped-def]
    return ln.name + (" · " + " · ".join(ln.options) if ln.options else "")


def _changes(live: SimSide, draft: SimSide) -> list[dict]:
    if not (live.ok and draft.ok):
        return [{"label": "Can deliver", "live": live.ok, "draft": draft.ok}] if live.ok != draft.ok else []
    out = []
    labels = list(dict.fromkeys([ln.label for ln in live.lines] + [ln.label for ln in draft.lines]))
    for label in labels:
        a = sum((ln.amount for ln in live.lines if ln.label == label), Decimal(0))
        b = sum((ln.amount for ln in draft.lines if ln.label == label), Decimal(0))
        if a != b:
            out.append({"label": label, "live": a, "draft": b})
    for label, key in (("Customer pays", None), ("Restaurant gets", "restaurant"), ("Rider gets", "rider"),
                       ("Tax", "tax"), ("Platform keeps", "platform")):
        a = live.total if key is None else getattr(live.split, key)
        b = draft.total if key is None else getattr(draft.split, key)
        if a != b:
            out.append({"label": label, "live": a, "draft": b})
    return out
