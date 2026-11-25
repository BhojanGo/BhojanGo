"""R43 (brief item 5): one full US customer path on real Stripe test mode, with every amount checked against Stripe.

menu -> cart (quote) -> checkout (the order, waiting for payment) -> Stripe's Payment Element in a browser with the test
card 4242 4242 4242 4242 -> the payment_intent.succeeded webhook places the order -> tracking (the restaurant accepts,
cooks, marks it ready; a delivery partner is assigned, picks it up and hands it over with the PIN) -> the receipt ->
a refund of one dish. Checked against Stripe's API: the PaymentIntent (amount = the order's total, captured), the
charge, and the Refund (amount = the stored refund), and the stored payment row (refunded amount).

The rider is assigned the way realtime does it (POST /internal/orders/{id}/assign-rider, signed with this run's own
INTERNAL_SERVICE_SECRET, tools/stripe_e2e/run.sh): the throwaway stack runs core-api only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from decimal import Decimal

from harness import H, Skip
from test_payments import ADMIN, CUSTOMER, _pay_in_browser

PARTNER, RIDER = "partner.boi@example.com", "rider1.boi@example.com"


def _cents(v: object) -> int:
    return int((Decimal(str(v)) * 100).to_integral_value())


def _assign(h: H, order_id: str, rider_id: str) -> None:
    secret = os.environ.get("INTERNAL_SERVICE_SECRET")
    if not secret:
        raise Skip("no INTERNAL_SERVICE_SECRET for this run (tools/stripe_e2e/run.sh sets one)")
    path = f"/api/v1/internal/orders/{order_id}/assign-rider"
    body = json.dumps({"rider_id": rider_id}).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}\nPOST\n{path}\n".encode() + body, hashlib.sha256).hexdigest()
    r = h.api(PARTNER).client.post(f"{h.core}{path}", content=body, headers={
        "Content-Type": "application/json", "X-Internal-Timestamp": str(ts), "X-Internal-Signature": sig})
    assert r.status_code == 200, f"assign rider: {r.status_code} {r.text[:200]}"


def case_r43_full_us_path_on_stripe(h: H) -> None:
    customer, partner, rider, admin = h.api(CUSTOMER), h.api(PARTNER), h.api(RIDER), h.api(ADMIN)

    # menu -> cart -> checkout -> Stripe test card in the Payment Element (the website's checkout component)
    order, out = _pay_in_browser(h, "4242424242424242")
    assert out == "done succeeded", out
    h.wait_payment(customer, order["id"], "succeeded")
    o = customer.call("GET", f"/orders/{order['id']}", 200)
    assert o["status"] == "placed", o["status"]
    total = _cents(o["total"])

    pi_id = h.sql(f"SELECT provider_payment_id FROM payment_intents WHERE order_id = '{order['id']}' AND status = 'succeeded'")[0][0]
    pi = h.stripe.PaymentIntent.retrieve(pi_id, expand=["latest_charge"])
    assert pi.status == "succeeded" and pi.currency == "usd", (pi.status, pi.currency)
    assert pi.amount == total and pi.amount_received == total, f"Stripe {pi.amount}/{pi.amount_received} != order {total}"
    charge = pi.latest_charge
    assert charge.captured and charge.paid and charge.amount == total, (charge.captured, charge.amount)
    assert charge.payment_method_details.card.last4 == "4242", charge.payment_method_details.card.last4
    stored = h.sql(f"SELECT amount, currency FROM payment_intents WHERE id IS NOT NULL AND provider_payment_id = '{pi_id}'")[0]
    assert int(stored[0]) == total and stored[1].lower() == "usd", stored

    # tracking: the restaurant, then a delivery partner, to delivered (the customer sees each status)
    seen = []
    for st in ("accepted", "preparing", "ready"):
        partner.call("PUT", f"/orders/{order['id']}/status", 200, json={"status": st})
        seen.append(customer.call("GET", f"/orders/{order['id']}", 200)["status"])
    _assign(h, order["id"], rider.user["id"])
    rider.call("PUT", f"/orders/{order['id']}/status", 200, json={"status": "picked_up"})
    seen.append(customer.call("GET", f"/orders/{order['id']}", 200)["status"])
    pin = customer.call("GET", f"/orders/{order['id']}", 200)["pin"]
    rider.call("PUT", f"/orders/{order['id']}/status", 200, json={"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    done = customer.call("GET", f"/orders/{order['id']}", 200)
    seen.append(done["status"])
    assert seen == ["accepted", "preparing", "ready", "picked_up", "delivered"], seen

    # the receipt: the delivered order's total = Stripe's amount; its PDF receipt is there
    paid = done["total"]
    assert _cents(paid) == total == pi.amount, f"receipt total {paid} != Stripe {pi.amount / 100}"
    pdf = customer.client.get(f"{h.core}/api/v1/orders/{order['id']}/receipt.pdf", headers=customer.headers)
    assert pdf.status_code == 200 and pdf.headers.get("content-type", "").startswith("application/pdf") and len(pdf.content) > 1000,         f"receipt.pdf: {pdf.status_code} {pdf.headers.get('content-type')}"

    # a refund of one dish: Stripe's Refund = the stored refund; the payment row says partially refunded
    item = order["items"][0]["menu_item_id"] if order.get("items") else done["items"][0]["menu_item_id"]
    r = admin.call("POST", f"/payments/orders/{order['id']}/refunds", 201, json={
        "items": [{"menu_item_id": item, "quantity": 1}], "reason": "goodwill", "note": "R43 full path"})
    refund = h.stripe.Refund.retrieve(r["provider_refund_id"])
    assert refund.payment_intent == pi_id and refund.amount == r["amount"] and refund.currency == "usd", (refund.amount, r["amount"])
    h.wait(lambda: any(x["id"] == r["id"] and x["status"] == "succeeded"
                       for x in admin.call("GET", f"/payments/orders/{order['id']}/refunds", 200)), 60, 2, "the refund's webhook")
    row = h.sql(f"SELECT status, refunded_amount FROM payment_intents WHERE provider_payment_id = '{pi_id}'")[0]
    assert row[0] == "partially_refunded" and int(row[1]) == refund.amount, row
    assert h.stripe.PaymentIntent.retrieve(pi_id, expand=["latest_charge"]).latest_charge.amount_refunded == refund.amount
    print(f"R43 full path: order {order['id'][:8]} total {total / 100:.2f} USD = Stripe {pi.amount / 100:.2f}; "
          f"statuses {' > '.join(seen)}; receipt {Decimal(str(paid)):.2f}; refund {refund.amount / 100:.2f} = Stripe", flush=True)
