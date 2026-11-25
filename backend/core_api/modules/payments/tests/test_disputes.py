"""R39 item 4: chargebacks without a database: who bears a lost dispute, what the next payout run does,
and the Stripe event shape (charge.dispute.*)."""
import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest

from core_api.modules.payments.service import disputes as D
from core_api.modules.payments.service import stripe_svc


def dispute(**kw):  # type: ignore[no-untyped-def]
    base = {"id": uuid.uuid4(), "order_id": uuid.uuid4(), "reason": "fraudulent", "held": 1500, "outcome": None,
            "hold_statement_id": None, "settle_statement_id": None, "restaurant_loss": 0}
    return SimpleNamespace(**{**base, **kw})


@pytest.mark.parametrize("status,outcome", [("needs_response", None), ("under_review", None), ("warning_needs_response", None),
                                            ("won", "won"), ("lost", "lost"), ("warning_closed", "won"), ("charge_refunded", "won")])
def test_outcome(status: str, outcome: str | None) -> None:
    assert D.outcome_of(status) == outcome


def test_loss_per_the_agreement() -> None:
    # food quality: the restaurant bears the food (never more than the dispute); BhojanGo the rest
    assert D.split_loss("product_unacceptable", 2599, 2200) == ("restaurant", 2200, 399)
    assert D.split_loss("product_unacceptable", 1000, 2200) == ("restaurant", 1000, 0)
    # R40: not received is the restaurant's too
    assert D.split_loss("product_not_received", 2599, 2200) == ("restaurant", 2200, 399)
    # fraud and everything else: BhojanGo
    for reason in ("fraudulent", "duplicate", "general", "unrecognized", "credit_not_processed", "subscription_canceled"):
        assert D.split_loss(reason, 2599, 2200) == ("platform", 0, 2599)
    # a country may name its own restaurant reasons (Markets setting dispute_restaurant_reasons)
    assert D.split_loss("product_not_received", 2599, 2200, ("product_unacceptable",)) == ("platform", 0, 2599)


@pytest.mark.parametrize("reason,held", [
    ("product_unacceptable", 1500), ("product_not_received", 1500),  # the restaurant would bear it: its share is held
    ("fraudulent", 0), ("duplicate", 0), ("general", 0), ("unrecognized", 0), ("credit_not_processed", 0),
    ("subscription_canceled", 0), ("incorrect_account_details", 0), ("insufficient_funds", 0)])
def test_r40_hold_only_when_the_restaurant_would_bear_it(reason: str, held: int) -> None:
    assert D.hold_for(reason, 1500, 2599) == held
    assert D.hold_for(reason, 3000, 2599) == (2599 if held else 0)  # never more than the disputed amount


def test_the_next_payout_run() -> None:
    st = uuid.uuid4()
    assert (a := D.adjustment(dispute())) and (a.kind, a.amount) == ("dispute_hold", -1500)  # open: hold
    assert D.adjustment(dispute(hold_statement_id=st)) is None  # held already
    assert D.adjustment(dispute(held=0)) is None  # nothing of the restaurant's to hold
    won = dispute(outcome="won", hold_statement_id=st)
    assert (a := D.adjustment(won)) and (a.kind, a.amount) == ("dispute_released", 1500)
    assert D.adjustment(dispute(outcome="won")) is None  # won before any run held it: nothing to do
    lost_food = dispute(outcome="lost", hold_statement_id=st, restaurant_loss=2200)
    assert (a := D.adjustment(lost_food)) and (a.kind, a.amount) == ("dispute_loss", -700)  # 1500 held, 2200 owed
    lost_fraud = dispute(outcome="lost", hold_statement_id=st, restaurant_loss=0)
    assert (a := D.adjustment(lost_fraud)) and (a.kind, a.amount) == ("dispute_released", 1500)  # BhojanGo bears it
    never_held = dispute(outcome="lost", restaurant_loss=2200)
    assert (a := D.adjustment(never_held)) and (a.kind, a.amount) == ("dispute_loss", -2200)
    D.mark_applied([a], st)
    assert never_held.settle_statement_id == st and never_held.hold_statement_id == st and D.adjustment(never_held) is None
    assert D.adjustment(dispute(outcome="lost", hold_statement_id=st, settle_statement_id=st, restaurant_loss=5)) is None


def test_stripe_dispute_events_are_read(monkeypatch) -> None:
    monkeypatch.setattr(stripe_svc.stripe.Webhook, "construct_event", lambda *a, **k: None)
    for kind in ("created", "updated", "closed"):
        body = json.dumps({"id": f"evt_{kind}", "type": f"charge.dispute.{kind}", "data": {"object": {
            "id": "dp_1", "object": "dispute", "amount": 2599, "currency": "usd", "reason": "fraudulent", "status": "needs_response",
            "payment_intent": "pi_1", "charge": "ch_1", "created": 1700000000,
            "evidence_details": {"due_by": 1700900000}}}}).encode()
        ev = asyncio.run(stripe_svc.process_webhook(body, "sig"))
        assert ev["kind"] == "dispute" and ev["event_id"] == f"evt_{kind}"
        assert ev["dispute"] == {"id": "dp_1", "amount": 2599, "currency": "usd", "reason": "fraudulent", "status": "needs_response",
                                 "payment_intent": "pi_1", "charge": "ch_1", "created": 1700000000, "due_by": 1700900000}
    assert {"charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed"} <= set(stripe_svc.WEBHOOK_EVENTS)
