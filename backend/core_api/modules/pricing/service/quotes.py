"""Quotes: gather the inputs, run the engine, sign the result.

A quote is valid for 10 minutes. The customer's app shows its lines (the fair
bill) and sends the token when placing the order; checkout charges exactly the
quoted total, and the order keeps a pricing snapshot (lines, rule versions,
split) that never changes afterwards.
"""
import json
import uuid
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.service.cart import CartError, price_cart
from core_api.modules.markets.models import City, Country, Region
from core_api.modules.markets.service import review
from core_api.modules.markets.service.markets import MarketService
from core_api.modules.orders.service.lookup import has_previous_orders
from core_api.modules.pricing.models import OrderPricingSnapshot, PromotionSpend, PromotionSpendWeek
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
from core_api.modules.pricing.service import offer_budget
from core_api.modules.pricing.service.fees import snapshot as fee_snapshot
from core_api.modules.pricing.service.summary import tip_presets
from core_api.modules.rules.service.resolver import Context
from core_api.modules.rules.service.rules import RuleService
from shared.auth import InvalidTokenError, decode_jwt, encode_jwt
from shared.money import format_money
from shared.providers.routing import get_routing_provider
from core_api.modules.pricing.service.routing_stats import record_routing
from shared.redis import get_redis

QUOTE_TTL = timedelta(minutes=10)
KM_PER_MILE = Decimal("1.609344")


class QuoteError(ValueError):
    """Can't quote or redeem; the message is shown to the customer.

    ``code`` says why for clients that word it themselves (MIN_ORDER: the bag is
    under the zone's minimum); ``details`` go into the API's error detail next to
    the English message: the amount and currency to format on the client, and the
    city's tip buttons (``tip_presets``) once the rules are known, so a bag under
    the minimum still shows the right tips."""

    def __init__(self, message: str, *, code: str = "CANNOT_QUOTE", details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def taxable_set(rules) -> set[str] | None:  # type: ignore[no-untyped-def]
    """R33: the bill lines the state's tax rule (tax:external taxable_lines) taxes; None when it doesn't say."""
    ext = rules.get("tax:external") if rules else None
    listed = ext.params.get("taxable_lines") if ext is not None else None
    return set(listed) if listed is not None else None


def tax_lines(inputs: QuoteInputs, result: QuoteResult, taxable: set[str] | None = None) -> list[TaxableLine]:
    """What the tax provider is sent: each cart line (its share of the food
    after food discounts, so the lines add up to the bill's food line) and each
    fee, marked taxable or not by the state's rule (R33; ``taxable`` None: the
    provider decides)."""
    def says(kind: str) -> bool | None:
        return None if taxable is None else kind in taxable

    amounts = taxable_amounts(result)
    food = amounts.pop("food", Decimal(0))
    out: list[TaxableLine] = []
    gross = [ln.unit_price * ln.quantity for ln in inputs.lines]
    total = sum(gross, Decimal(0))
    if food > 0 and total > 0:
        left = food
        for i, (ln, g) in enumerate(zip(inputs.lines, gross)):
            share = left if i == len(gross) - 1 else money(food * g / total)
            left -= share
            if share > 0:
                out.append(TaxableLine(f"food-{i + 1}-{ln.item_id or 'item'}", share, kind="food", taxable=says("food")))
    elif food > 0:
        out.append(TaxableLine("food", food, kind="food", taxable=says("food")))
    out += [TaxableLine(ref, amount, kind=ref, taxable=says(ref)) for ref, amount in amounts.items()]
    return out


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
    # R37: with the card fee (R29: the kitchen's cost), or "Who gets your money" counted it as tax
    return SplitOut(restaurant=s.restaurant, rider=s.rider, tax=s.tax, platform=s.platform, detail=s.detail,
                    card_fee=getattr(s, "card_fee", Decimal(0)))


async def city_chain(db: AsyncSession, code: str) -> tuple[City, Region, Country, ZoneInfo]:
    city = await MarketService(db).repo.city(code)
    if city is None:
        raise QuoteError("City not found")
    region = await db.get(Region, city.region_id)
    country = await db.get(Country, city.country_id)
    assert region is not None and country is not None
    tz = ZoneInfo(city.timezone or region.timezone or country.timezone)
    return city, region, country, tz


def week_of(local: datetime) -> date:
    """The Monday that starts the week (market time): weekly caps and payouts."""
    return local.date() - timedelta(days=local.weekday())


class QuoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _promo_spent(self) -> dict[str, Decimal]:
        rows = (await self.db.execute(select(PromotionSpend))).scalars()
        return {str(r.rule_key): Decimal(r.spent) for r in rows}

    async def _promo_spent_week(self, week_start: date) -> dict[str, Decimal]:
        rows = (await self.db.execute(select(PromotionSpendWeek).where(PromotionSpendWeek.week_start == week_start))).scalars()
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
                        city_name: str, postal: dict, quote_id: uuid.UUID) -> tuple[QuoteInputs, QuoteResult]:
        """US: send the taxable lines (each cart line, each fee) and the address
        to the tax provider, then price again with the tax it returns. Never
        quote without tax. One calculation per quote (idempotency key)."""
        if not result.tax_pending:
            return inputs, result
        address = TaxAddress(country=region_code[:2], state=region_code[3:], city=postal.get("city") or city_name,
                             postal_code=postal.get("postal_code"), line1=postal.get("street"))
        try:
            calc = await get_tax_provider().calculate(inputs.currency, tax_lines(inputs, result, taxable_set(rules)), address,
                                                      idempotency_key=f"taxcalc:{quote_id}")
        except TaxError as e:
            raise QuoteError(str(e))
        ext = [ExternalTax(b.label, b.rate_percent, b.taxable_amount, b.amount, b.jurisdiction, calc.provider,
                           calc.calculation_id, b.reason) for b in calc.breakdown]
        inputs = replace(inputs, external_tax=ext)
        return inputs, compute(inputs, rules)

    # ── customer quotes ──────────────────────────────────────────────────────
    async def quote(self, user_id: uuid.UUID, req: QuoteRequest, now: datetime | None = None) -> QuoteOut:
        now = now or datetime.now(UTC)
        items = [i.model_dump(mode="json") for i in req.items]
        if req.fulfillment == "pickup":  # R32: said first, whatever is in the bag
            from core_api.modules.catalog.models.restaurant import Restaurant

            found = await self.db.get(Restaurant, req.restaurant_id)
            if found is not None and not found.pickup_enabled:
                raise QuoteError(f"{found.name} doesn't take pickup orders", code="PICKUP_OFF")
        try:
            # R27: a closed kitchen is refused below, once the city's tip buttons are known (the bag still shows them).
            rest, priced = await price_cart(self.db, req.restaurant_id, items, check_open=False, now=now)
        except CartError as e:
            raise QuoteError(str(e))
        from core_api.modules.catalog.service.menu import availability

        avail = await availability(self.db, uuid.UUID(rest.id), now)
        if avail.reason_code in ("inactive", "unavailable"):
            raise QuoteError(f"{rest.name}: {avail.reason}")
        pickup = req.fulfillment == "pickup"
        pickup_address = None
        if pickup:  # R32: priced (and taxed) where the customer collects it: the restaurant
            from core_api.modules.catalog.models.restaurant import Restaurant

            model = await self.db.get(Restaurant, uuid.UUID(rest.id))
            if model is None or not model.pickup_enabled:
                raise QuoteError(f"{rest.name} doesn't take pickup orders", code="PICKUP_OFF")
            if rest.lat is None or rest.lng is None:
                raise QuoteError("This restaurant isn't on the map yet")
            a = model.address or {}
            lat, lng = rest.lat, rest.lng
            postal = {"street": a.get("street"), "city": a.get("city"), "postal_code": a.get("zip")}
            pickup_address = {"street": a.get("street"), "city": a.get("city"), "state": a.get("state"),
                              "zip": a.get("zip"), "lat": lat, "lng": lng}
        elif req.deliver_to is None:
            raise QuoteError("Choose where to deliver")
        else:
            lat, lng, postal = await self._deliver_to(user_id, req)

        where = await MarketService(self.db).locate(lat, lng)
        if not where.serviceable:
            raise QuoteError(where.reason or "We don't deliver here yet")
        from core_api.modules.incidents.service import pause_for, pause_message

        paused = await pause_for(self.db, where.city_code)  # R17: an admin paused ordering here (an incident)
        if paused is not None:
            raise QuoteError(pause_message(paused))
        city, region, country, tz = await city_chain(self.db, where.city_code)  # type: ignore[arg-type]
        # R20: a review-only city prices for its review accounts only, and their orders cost nothing.
        review_order = review.is_review_account(city.settings, user_id)
        if review.is_review_only(city.settings) and not review_order:
            raise QuoteError("We don't deliver here yet")
        if rest.country != country.code:
            raise QuoteError("This restaurant doesn't deliver to that address")
        if rest.lat is None or rest.lng is None:
            raise QuoteError("This restaurant isn't on the map yet")

        routing = "none"
        if pickup:
            km = Decimal(0)  # R32: nothing to drive
        else:
            leg = get_routing_provider().leg((rest.lat, rest.lng), (lat, lng))
            km, routing = Decimal(str(leg.distance_km)), leg.source
            await record_routing(self.db, routing)  # R32: road vs fallback, for the admin tile and the alert
        distance = money(km / KM_PER_MILE if country.distance_unit == "mi" else km)
        food = sum((ln.unit_price * ln.quantity for ln in priced), Decimal(0))

        ctx = Context(country=country.code, region=region.code, city=city.code, zone_id=str(where.zone_id),
                      restaurant_id=rest.id)
        rules = await RuleService(self.db).resolve(ctx, now)
        presets = tip_presets(rules)
        # From here on a refusal still tells the client the city's tip buttons.
        tips = {"tip_presets": presets.model_dump(mode="json") if presets else None}
        if not avail.open_now:
            # R27: closed by its hours, the city's delivery hours, or paused: the bag says why and when it opens.
            # Open by its hours but its tablet isn't live: KITCHEN_OFFLINE ("Not taking orders right now").
            offline = avail.reason_code == "not_taking_orders"
            raise QuoteError(f"{rest.name}: {avail.reason}", code="KITCHEN_OFFLINE" if offline else "KITCHEN_CLOSED", details={
                "reason_code": avail.reason_code, "closed_note": avail.closed_note,
                "opens_at": avail.next_open_at.isoformat() if avail.next_open_at else None,
                "time_zone": avail.timezone, "delivery_hours": avail.delivery_hours, **tips})
        # R36: the restaurant's own minimum never blocks the bill: the quote says how much is missing
        # (``short_by``) and the order can't be placed until it's met (redeem). Zones have no minimum
        # in the seeds any more; a zone minimum, if set, still refuses (MIN_ORDER).
        minimum = Decimal(rest.minimum_order_amount or 0)
        short_by = max(minimum - food, Decimal(0)).quantize(Decimal("0.01"))
        if where.min_order is not None and food < where.min_order:
            shown = format_money(where.min_order, country.currency, (country.locales or [None])[0], whole=True)
            raise QuoteError(f"The minimum order in {where.zone_name} is {shown}", code="MIN_ORDER", details={
                "zone": where.zone_name, "amount": str(where.min_order), "currency": country.currency, **tips})
        # R37: BhojanGo-funded offers spend from this place's monthly budget (offer_budget.py)
        pool = offer_budget.pool_for([("country", country.code, country.name, country.settings),
                                      ("region", region.code, region.name, region.settings),
                                      ("city", city.code, city.name, city.settings)], country.currency)
        offer_month = offer_budget.month_of(now.astimezone(tz))
        inputs = QuoteInputs(
            currency=country.currency,
            lines=[CartLine(_label(ln), ln.quantity, ln.unit_price, ln.item_id, ln.options) for ln in priced],
            distance=distance, local_time=now.astimezone(tz), tip=Decimal(0) if pickup else req.tip, restaurant_tier=rest.tier,
            fulfillment=req.fulfillment,
            first_order=not await has_previous_orders(self.db, user_id),
            promo_code=req.promo_code, promo_spent=await self._promo_spent(),
            promo_spent_week=await self._promo_spent_week(week_of(now.astimezone(tz))),
            platform_offer_left=await offer_budget.left(self.db, pool, offer_month),
            # A review order charges nothing, so no tax is due and the tax provider is never asked.
            review=review_order, external_tax=[] if review_order else None,
        )
        quote_id = uuid.uuid4()
        try:
            result = compute(inputs, rules)
            inputs, result = await self._with_tax(inputs, rules, result, region.code, city.name, postal, quote_id)
        except NotDeliverable as e:
            raise QuoteError(str(e), details=tips)
        except QuoteError as e:
            raise QuoteError(str(e), code=e.code, details={**tips, **e.details})

        expires = now + QUOTE_TTL
        stored = {
            "quote_id": str(quote_id), "user_id": str(user_id), "restaurant_id": rest.id,
            "restaurant_name": rest.name, "cart": _cart_signature(rest.id, items),
            "items": [{"menu_item_id": ln.item_id, "name": ln.name, "quantity": ln.quantity,
                       "unit_price": str(ln.unit_price), "options": list(ln.options)} for ln in priced],
            "currency": result.currency, "total": str(result.total), "food_subtotal": str(result.food_subtotal),
            "restaurant_minimum": str(minimum) if minimum > 0 else None, "short_by": str(short_by),
            "lines": [{**asdict(ln), "amount": str(ln.amount)} for ln in result.lines],
            "tax_calculation": next(({"provider": e.provider, "calculation_id": e.calculation_id}
                                     for e in (inputs.external_tax or [])), None),
            "split": {k: str(v) for k, v in asdict(result.split).items() if k != "detail"}
            | {"detail": {k: str(v) for k, v in result.split.detail.items()}},
            "rules_used": result.rules_used, "tax_pending": result.tax_pending,
            # R29: the fee settings that priced it, each with the rule (level, scope, version) it came from
            "fee_settings": fee_snapshot(rules, rest.tier),
            "context": {"country": country.code, "region": region.code, "city": city.code, "zone_id": str(where.zone_id),
                        "week_start": week_of(now.astimezone(tz)).isoformat(),
                        "offer_pool": {"level": pool.level, "code": pool.code, "month": offer_month.isoformat()},
                        "zone": where.zone_name, "distance": str(distance), "distance_unit": country.distance_unit,
                        "local_time": inputs.local_time.isoformat(), "deliver_to": {"lat": lat, "lng": lng},
                        "fulfillment": req.fulfillment, "routing": routing,
                        **({"pickup_address": pickup_address} if pickup_address else {}),
                        **({"review": True} if review_order else {})},
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
            distance=distance, distance_unit=country.distance_unit, tip_presets=presets,
            fulfillment=req.fulfillment, pickup_address=pickup_address,
            restaurant_minimum=minimum if minimum > 0 else None, short_by=short_by,
        )

    async def get(self, user_id: uuid.UUID, quote_id: uuid.UUID) -> dict:
        raw = await (await get_redis()).get(_key(str(quote_id)))
        if raw is None:
            raise QuoteError("This quote has expired; we'll price your cart again")
        q = json.loads(raw)
        if q["user_id"] != str(user_id):
            raise QuoteError("This quote has expired; we'll price your cart again")
        return q

    async def redeem(self, token: str, user_id: uuid.UUID, restaurant_id: uuid.UUID, items: list[dict]) -> dict:
        """Check a quote for checkout: signed by us, for this customer, not
        expired, same bag. Returns the stored quote; ``attach`` uses it once."""
        try:
            claims = decode_jwt(token)
        except InvalidTokenError:
            raise QuoteError("Prices have changed since you opened your cart; please review the new total")
        if claims.get("type") != "quote" or claims.get("sub") != str(user_id):
            raise QuoteError("This quote isn't yours")
        q = await self.get(user_id, uuid.UUID(claims["qid"]))
        if q["cart"] != json.loads(json.dumps(_cart_signature(str(restaurant_id), items))):
            raise QuoteError("Your cart changed after it was priced; please review the new total")
        if q["total"] != claims["total"]:
            raise QuoteError("This quote has been tampered with")
        if Decimal(q.get("short_by") or 0) > 0:  # R36: under the restaurant's own minimum
            from shared.money import customer_money

            more = customer_money(q["short_by"], q["currency"])
            raise QuoteError(f"Add {more} more to order from {q['restaurant_name']}",
                             code="BELOW_MINIMUM", details={"amount": q["restaurant_minimum"], "short_by": q["short_by"],
                                                            "currency": q["currency"], "restaurant": q["restaurant_name"]})
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
            fee_settings=q.get("fee_settings"),
        )
        self.db.add(snap)
        await self._spend_platform_budget(q)
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
            week = q["context"].get("week_start")
            if week:
                wk = await self.db.get(PromotionSpendWeek, (uuid.UUID(key), date.fromisoformat(week)), with_for_update=True)
                if wk is None:
                    wk = PromotionSpendWeek(rule_key=uuid.UUID(key), week_start=date.fromisoformat(week), currency=q["currency"],
                                            spent=Decimal(0), orders=0)
                    self.db.add(wk)
                wk.spent = Decimal(wk.spent) - Decimal(ln["amount"])
                wk.orders += 1
        await self.db.flush()
        return snap

    async def _spend_platform_budget(self, q: dict) -> None:
        """R37: count the order's BhojanGo-funded offers against the month's budget, checked again
        under a lock (another order may have used it up since the quote): OFFER_ENDED when it can't."""
        cost = -sum((Decimal(ln["amount"]) for ln in q["lines"]
                     if ln["code"] == "promotion" and ln.get("funded_by") == "platform"
                     and not (ln.get("detail") or {}).get("review")), Decimal(0))
        where = q["context"].get("offer_pool")
        if cost <= 0 or not where:
            return
        ctx = q["context"]
        pool = await offer_budget.pool_at(self.db, ctx["country"], ctx.get("region"), ctx.get("city"))
        try:
            await offer_budget.record(self.db, pool, date.fromisoformat(where["month"]), cost, datetime.now(UTC))
        except offer_budget.OfferEnded:
            raise QuoteError("This offer has just ended; we'll price your cart again", code="OFFER_ENDED")

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
                             payment_method=req.payment_method,
                             promo_spent=await self._promo_spent(),
                             platform_offer_left=await offer_budget.left(self.db, offer_budget.pool_for(
                                 [("country", country.code, country.name, country.settings),
                                  ("region", region.code, region.name, region.settings),
                                  ("city", city.code, city.name, city.settings)], country.currency), offer_budget.month_of(local)))
        svc = RuleService(self.db)
        at = local.astimezone(UTC)

        async def side(rules) -> SimSide:  # type: ignore[no-untyped-def]
            try:
                result = compute(inputs, rules)
                postal = {"postal_code": req.postal_code} if req.postal_code else {}  # R15: US simulations need a ZIP
                _, result = await self._with_tax(inputs, rules, result, region.code, city.name, postal, uuid.uuid4())
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
    for label, key in (("Customer pays", None), ("Restaurant gets", "restaurant"), ("Delivery partner gets", "rider"),
                       ("Tax", "tax"), ("Platform keeps", "platform")):
        a = live.total if key is None else getattr(live.split, key)
        b = draft.total if key is None else getattr(draft.split, key)
        if a != b:
            out.append({"label": label, "live": a, "draft": b})
    return out
