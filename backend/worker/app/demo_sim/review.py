"""The review simulator (R20): the app store review order's kitchen and delivery partner.

Apple and Google reviewers sign in with the review customer (tools/review_accounts.py)
and order from the review kitchen in the hidden review-only city. The order costs
nothing and is placed at once (core_api pricing ``review``). Nobody works that kitchen
or rides there, so with REVIEW_SIM=1 this loop plays them: every few seconds it reads
the open review orders and moves each one step on, through core_api's signed
POST /internal/review/orders/{id}/step (accept, cook, assign the review delivery
partner, ready, pick up, deliver), so the reviewer sees the whole order in the
customer app within about seven minutes.

Unlike the demo rider simulator (rules.py, refused in production), it may run in
production, because it touches nothing else, twice over:

- it reads only orders whose city's settings say ``review_only`` and whose customer
  and kitchen owner are both that city's ``review_accounts`` (ORDERS_SQL);
- core_api moves only such orders and answers 404 for any other
  (core_api orders/service/review_sim.py), whatever this loop asks.
"""
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text

logger = structlog.get_logger(__name__)

TICK_SECONDS = 4.0
# The pace (a believable kitchen and ride, short enough for a reviewer to watch it all):
ACCEPT_AFTER = timedelta(seconds=20)      # from placed (the accept timeout is 3 minutes)
READY_AFTER = timedelta(minutes=2)        # from accepted
PICK_UP_AFTER = timedelta(seconds=45)     # from ready
DELIVER_AFTER = timedelta(minutes=3)      # from picked up
OPEN = ("placed", "accepted", "preparing", "almost_ready", "ready", "picked_up")
STEP_PATH = "/api/v1/internal/review/orders/{order_id}/step"

# Review orders only: a review-only city, and both the customer and the kitchen's owner are
# its review accounts (the settings tools/review_accounts.py writes; markets.service.review).
ORDERS_SQL = text("""
SELECT o.id, o.status, o.driver_id, o.created_at, o.placed_at, o.restaurant_accepted_at, o.actual_ready_at,
       o.picked_up_at
FROM orders o
JOIN cities ci ON ci.code = o.market_city
JOIN restaurants r ON r.id = o.restaurant_id
WHERE ci.settings->>'review_only' = 'true'
  AND ci.settings->'review_accounts' @> jsonb_build_array(o.customer_id::text)
  AND ci.settings->'review_accounts' @> jsonb_build_array(r.owner_id::text)
  AND o.status IN ('placed', 'accepted', 'preparing', 'almost_ready', 'ready', 'picked_up')
ORDER BY o.created_at
""")

_running = False


def enabled(flag: str | bool | None) -> tuple[bool, str]:
    """(on, why): REVIEW_SIM must say yes. Allowed in every environment, production too."""
    on = flag if isinstance(flag, bool) else str(flag or "").strip().lower() in ("1", "true", "yes", "on")
    return (True, "on") if on else (False, "off (REVIEW_SIM is not set)")


@dataclass(frozen=True)
class ReviewOrder:
    id: str
    status: str
    driver_id: str | None
    created_at: datetime
    placed_at: datetime | None = None
    accepted_at: datetime | None = None
    ready_at: datetime | None = None
    picked_up_at: datetime | None = None


def _past(since: datetime | None, fallback: datetime, now: datetime, wait: timedelta) -> bool:
    return now - (since or fallback) >= wait


def next_step(o: ReviewOrder, now: datetime) -> str:
    """What happens next, from the order as it is now (a restart carries on):
    accept, prepare, assign, ready, pick_up, deliver or wait."""
    if o.status == "placed":
        return "accept" if _past(o.placed_at, o.created_at, now, ACCEPT_AFTER) else "wait"
    if o.status == "accepted":
        return "prepare"
    if o.status in ("preparing", "almost_ready", "ready") and o.driver_id is None:
        return "assign"  # before the food is ready, so dispatch never looks for anyone else
    if o.status in ("preparing", "almost_ready"):
        return "ready" if _past(o.accepted_at, o.created_at, now, READY_AFTER) else "wait"
    if o.status == "ready":
        return "pick_up" if _past(o.ready_at, o.created_at, now, PICK_UP_AFTER) else "wait"
    if o.status == "picked_up":
        return "deliver" if _past(o.picked_up_at, o.created_at, now, DELIVER_AFTER) else "wait"
    return "wait"


def _order(row) -> ReviewOrder:  # type: ignore[no-untyped-def]
    return ReviewOrder(id=str(row.id), status=row.status, driver_id=str(row.driver_id) if row.driver_id else None,
                       created_at=row.created_at, placed_at=row.placed_at, accepted_at=row.restaurant_accepted_at,
                       ready_at=row.actual_ready_at, picked_up_at=row.picked_up_at)


async def review_orders() -> list[ReviewOrder]:
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return [_order(r) for r in (await db.execute(ORDERS_SQL)).all()]


async def send(core, order_id: str, step: str) -> dict:  # type: ignore[no-untyped-def]
    """One step through core_api (signed; core_api refuses anything but a review order)."""
    from shared import internal_auth

    path = STEP_PATH.format(order_id=order_id)
    body = json.dumps({"step": step}).encode()
    r = await core.post(path, content=body, headers={"content-type": "application/json",
                                                      **internal_auth.sign("POST", path, body)})
    if r.status_code >= 400:
        raise RuntimeError(f"{step} {order_id}: {r.status_code} {r.text[:300]}")
    return r.json()


async def tick(core, now: datetime) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Each open review order one step on. Returns (order id, step) for the steps taken."""
    done = []
    for o in await review_orders():
        step = next_step(o, now)
        if step == "wait":
            continue
        try:
            out = await send(core, o.id, step)
        except Exception as e:  # noqa: BLE001 - one order's trouble never stops the others
            logger.warning("review_sim_step_failed", order_id=o.id, step=step, error=str(e))
            continue
        logger.info("review_order_step", order_id=o.id, step=step, status=out.get("status"))
        done.append((o.id, step))
    return done


def settings_enabled() -> tuple[bool, str]:
    from shared.config import get_settings

    return enabled(get_settings().worker.REVIEW_SIM)


async def run() -> None:
    """The loop: every TICK_SECONDS, each open review order one step on."""
    global _running
    import httpx

    from shared.config import get_settings

    on, why = settings_enabled()
    logger.info("review_sim", status=why)
    if not on:
        return
    _running = True
    async with httpx.AsyncClient(base_url=get_settings().CORE_API_URL, timeout=15) as core:
        while _running:
            try:
                await tick(core, datetime.now(UTC))
            except Exception as e:  # noqa: BLE001 - the database may not be there yet
                logger.warning("review_sim_tick_failed", error=str(e))
            await asyncio.sleep(TICK_SECONDS)


def stop() -> None:
    global _running
    _running = False
