"""US payments through Stripe test mode (R10 items 1, 2, 4), against the
throwaway stack tools/stripe_e2e/run.sh starts. Cases run in this order; the
refund case refunds the order the first card case paid.

Test cards: https://docs.stripe.com/testing
"""
from __future__ import annotations

import functools
import http.server
import re
import threading
from decimal import Decimal
from pathlib import Path

from harness import H, Skip

CUSTOMER = "customer1.boi@example.com"
ADMIN = "admin@example.com"  # super admin (the seed's), two-step sign-in with the seed's key


def _tax_lines(q: dict) -> list[dict]:
    return [ln for ln in q["lines"] if ln["code"] == "tax"]


def case_stripe_tax_on_the_quote(h: H) -> None:
    """The bill's tax lines are Stripe Tax's answer for the cart lines and the Boise address."""
    customer = h.api(CUSTOMER)
    _, _, q, _ = h.boise_quote(customer)
    taxes = _tax_lines(q)
    assert taxes, f"no tax line on a US quote: {[ln['code'] for ln in q['lines']]}"
    for t in taxes:
        d = t["detail"] or {}
        assert d.get("provider") == "stripe_tax", f"tax not from Stripe Tax: {d}"
        assert str(d.get("calculation_id", "")).startswith("taxcalc_"), d
    total = sum(Decimal(t["amount"]) for t in taxes)
    if total == 0:
        reasons = {t["detail"].get("reason") for t in taxes}
        raise AssertionError(f"Stripe Tax returned zero tax ({reasons}): add an Idaho registration in the test account")
    print(f"  tax lines: {[(t['label'], t['amount'], t['detail'].get('rate_percent')) for t in taxes]}")


def case_card_succeeds_and_places_the_order(h: H) -> None:
    """4242 (pm_card_visa): Stripe's payment_intent.succeeded webhook places the order; the
    tax calculation becomes a Stripe Tax transaction."""
    customer = h.api(CUSTOMER)
    rest, address, q, cart = h.boise_quote(customer)
    order = h.place(customer, rest, address, q, cart)
    assert order["status"] == "pending_payment", order["status"]
    # The payment deadline comes from the business rule unpaid_auto_cancel (the seed: 10 minutes).
    rule = h.sql("SELECT params->>'minutes' FROM rules WHERE template = 'unpaid_auto_cancel' AND status = 'published' "
                 "ORDER BY version DESC LIMIT 1")
    held = h.sql(f"SELECT round(extract(epoch FROM payment_due_at - created_at) / 60) FROM orders WHERE id = '{order['id']}'")[0][0]
    assert rule and int(float(held)) == int(rule[0][0]) == 10, f"payment deadline {held} min, rule {rule}"
    init = h.initiate(customer, order["id"])
    again = h.initiate(customer, order["id"])
    assert again["payment_intent_id"] == init["payment_intent_id"], "initiating twice must reuse the open payment"
    c = init["checkout"]
    assert c["publishable_key"].startswith("pk_test_") and c["payment_intent_client_secret"].startswith("pi_")
    pi_id = c["payment_intent_client_secret"].split("_secret_")[0]
    pi = h.stripe.PaymentIntent.retrieve(pi_id)
    assert pi.amount == round(Decimal(q["total"]) * 100) and pi.currency == "usd", (pi.amount, q["total"])
    assert pi.metadata["order_id"] == order["id"]
    h.stripe.PaymentIntent.confirm(pi_id, payment_method="pm_card_visa", return_url="https://example.com/return")
    h.wait_payment(customer, order["id"], "succeeded")
    assert customer.call("GET", f"/orders/{order['id']}", 200)["status"] == "placed"
    meta = h.wait(lambda: (rows := h.sql(
        f"SELECT metadata->'tax_transaction'->>'transaction_id' FROM payment_intents WHERE order_id = '{order['id']}' "
        "AND status = 'succeeded'")) and rows[0][0] and rows[0][0], 30, 2, "the Stripe Tax transaction")
    assert meta.startswith("tax_"), meta
    h.state["paid"] = {"order": order, "quote": q, "cart": cart, "pi": pi_id}


def case_declined_card_keeps_the_order_payable(h: H) -> None:
    """4000 0000 0000 0002 (pm_card_chargeDeclined): payment_intent.payment_failed; the order
    stays pending_payment with its price held; a second attempt with a good card places it."""
    customer = h.api(CUSTOMER)
    rest, address, q, cart = h.boise_quote(customer)
    order = h.place(customer, rest, address, q, cart)
    pi_id = h.initiate(customer, order["id"])["checkout"]["payment_intent_client_secret"].split("_secret_")[0]
    try:
        h.stripe.PaymentIntent.confirm(pi_id, payment_method="pm_card_chargeDeclined", return_url="https://example.com/return")
        raise AssertionError("the declined test card was accepted")
    except h.stripe.CardError:
        pass
    s = h.wait_payment(customer, order["id"], "failed")
    assert s["order_status"] == "pending_payment" and s["can_retry"], s
    assert "declined" in (s["failure_reason"] or "").lower(), s["failure_reason"]
    second = h.initiate(customer, order["id"])
    pi2 = second["checkout"]["payment_intent_client_secret"].split("_secret_")[0]
    assert pi2 != pi_id, "a retry after a failure starts a new PaymentIntent"
    h.stripe.PaymentIntent.confirm(pi2, payment_method="pm_card_visa", return_url="https://example.com/return")
    h.wait_payment(customer, order["id"], "succeeded")
    assert customer.call("GET", f"/orders/{order['id']}", 200)["status"] == "placed"


def case_refund_by_item_through_stripe(h: H) -> None:
    """An admin refunds one item: a Stripe Refund of exactly the item's amount (its food,
    discount share and tax), confirmed by the refund webhook; the tax transaction is reversed."""
    paid = h.state.get("paid")
    if not paid:
        raise Skip("needs the paid order from card_succeeds_and_places_the_order")
    admin = h.api(ADMIN)
    item = paid["cart"][0]["menu_item_id"]
    r = admin.call("POST", f"/payments/orders/{paid['order']['id']}/refunds", 201, json={
        "items": [{"menu_item_id": item, "quantity": 1}], "reason": "goodwill", "note": "stripe e2e"})
    assert r["provider_refund_id"].startswith("re_"), r
    refund = h.stripe.Refund.retrieve(r["provider_refund_id"])
    assert refund.amount == r["amount"] and refund.payment_intent == paid["pi"], (refund.amount, r["amount"])
    line = r["lines"][0]
    assert Decimal(line["tax"]) > 0, f"the item's refund carries its tax: {line}"
    h.wait(lambda: any(x["id"] == r["id"] and x["status"] == "succeeded"
                       for x in admin.call("GET", f"/payments/orders/{paid['order']['id']}/refunds", 200)),
           60, 2, "the refund's status from the webhook")
    rows = h.sql(f"SELECT status, refunded_amount, metadata->'tax_reversals'->0->>'reversal_id' FROM payment_intents "
                 f"WHERE order_id = '{paid['order']['id']}' AND status <> 'failed'")
    assert rows and rows[0][0] == "partially_refunded" and int(rows[0][1]) == r["amount"], rows
    assert (rows[0][2] or "").startswith("tax_"), f"no Stripe Tax reversal: {rows}"


# ── the Payment Element in a real browser (headless Chromium) ────────────────
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a) -> None:  # type: ignore[no-untyped-def]
        pass


def _serve() -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_Quiet, directory=str(Path(__file__).resolve().parent))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _card_frame(page):  # type: ignore[no-untyped-def]
    for _ in range(240):  # up to 2 minutes: the challenge frame loads its content late in headless Chromium
        for f in page.frames:
            try:
                if f.locator('input[name="number"]').count():
                    return f
            except Exception:  # noqa: BLE001 (a frame navigating away)
                pass
        page.wait_for_timeout(500)
    raise AssertionError("the Payment Element's card form didn't appear")


def _complete_3ds(page) -> bool:  # type: ignore[no-untyped-def]
    """Stripe's test 3-D Secure page: press "Complete" (it sits in nested frames)."""
    for _ in range(240):  # up to 2 minutes: the challenge frame loads its content late in headless Chromium
        for f in page.frames:
            try:
                b = f.locator("#test-source-authorize-3ds")
                if not b.count():
                    b = f.get_by_role("button", name=re.compile(r"^complete", re.I))
                if b.count():
                    b.first.click()
                    return True
            except Exception:  # noqa: BLE001
                pass
        page.wait_for_timeout(500)
    return False


def _pay_in_browser(h: H, card: str, three_ds: bool = False) -> tuple[dict, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise AssertionError("Playwright isn't installed in the runner")
    customer = h.api(CUSTOMER)
    # The API cases' basket (2 bowls, $29): one bowl ($14.50) is under the zone's $15 minimum.
    rest, address, q, cart = h.boise_quote(customer)
    order = h.place(customer, rest, address, q, cart)
    c = h.initiate(customer, order["id"])["checkout"]
    srv, port = _serve()
    try:
        with sync_playwright() as p:
            # Chromium's full headless mode: in the older "headless shell" Stripe's 3-D Secure
            # challenge frame never loaded its content on the runner (R10).
            browser = p.chromium.launch(channel="chromium")
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/pay.html?pk={c['publishable_key']}&cs={c['payment_intent_client_secret']}")
            page.wait_for_function("document.getElementById('out').textContent !== 'loading'", timeout=30000)
            assert page.inner_text("#out") == "ready", page.inner_text("#out")
            f = _card_frame(page)
            f.locator('input[name="number"]').fill(card)
            f.locator('input[name="expiry"]').fill("12 / 34")
            f.locator('input[name="cvc"]').fill("123")
            if f.locator('input[name="postalCode"]').count():
                f.locator('input[name="postalCode"]').fill("83702")
            page.click("#pay")
            if three_ds and not _complete_3ds(page):
                frames = [f.url[:90] for f in page.frames]
                buttons = []
                for f in page.frames:
                    try:
                        buttons += [t.strip()[:30] for t in f.locator("button").all_inner_texts()]
                    except Exception:  # noqa: BLE001
                        pass
                raise AssertionError(f"the 3-D Secure challenge didn't appear; out={page.inner_text('#out')!r} "
                                     f"frames={frames} buttons={buttons}")
            page.wait_for_function("/^(done|error)/.test(document.getElementById('out').textContent)", timeout=60000)
            out = page.inner_text("#out")
            browser.close()
    finally:
        srv.shutdown()
    return order, out


def case_payment_element_card_4242(h: H) -> None:
    order, out = _pay_in_browser(h, "4242424242424242")
    assert out == "done succeeded", out
    h.wait_payment(h.api(CUSTOMER), order["id"], "succeeded")


def case_payment_element_3d_secure_4000002760003184(h: H) -> None:
    """A card that always asks for 3-D Secure: the challenge is completed in Stripe's test frame."""
    order, out = _pay_in_browser(h, "4000002760003184", three_ds=True)
    assert out == "done succeeded", out
    h.wait_payment(h.api(CUSTOMER), order["id"], "succeeded")
    assert h.api(CUSTOMER).call("GET", f"/orders/{order['id']}", 200)["status"] == "placed"


def case_payment_element_declined_4000000000000002(h: H) -> None:
    order, out = _pay_in_browser(h, "4000000000000002")
    assert out.startswith("error") and "declined" in out.lower(), out
    s = h.wait_payment(h.api(CUSTOMER), order["id"], "failed")
    assert s["order_status"] == "pending_payment", s
