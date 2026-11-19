# Incident plan (draft)

For Boise's launch. What to do when orders can't be placed, paid, cooked or delivered, or when money or data is
at risk. Draft for Srini to approve; names and phone numbers are filled in before launch.

## Who is called

| Role | Who | When |
|---|---|---|
| Incident lead (decides, talks to customers and partners) | Srini | Every incident |
| Engineering (finds the cause, pauses, fixes, refunds) | Claude Code session started by Srini; later an on-call engineer | Every incident |
| Payments (Stripe disputes, payouts) | Srini, with Stripe support | Anything with money |
| Kitchens and delivery partners | Srini (support line) | When they are affected |

Alerts (PaymentFailures, API errors, webhooks failing, no orders in a dinner hour) page the incident lead once
monitoring is set up (readiness item 14). Severity: **1** nobody can order or pay → act at once; **2** one zone, kitchen
or payment method broken → within 30 minutes; **3** degraded (slow, a feature missing) → same day.

## First 15 minutes

1. Say it out loud: post in the incident channel what is broken, since when, and who leads.
2. Stop new damage: pause what is failing (below), so customers can't place orders that will fail.
3. Look at what was already caught: orders placed but not accepted, paid but not delivered.
4. Tell the people affected (templates below).
5. Fix or roll back (Railway: redeploy the last good build); then reopen, watching the first orders.
6. Within two days: a short write-up (what happened, the cause, the fix) and a PLAYBOOK lesson if it cost more than an hour.

## Pausing, from admin

| What | Where in admin | Status |
|---|---|---|
| **A zone** | Markets → country → city → the zone → "Pause this zone…" (a reason and an end time; customers see it's paused) | Works |
| **A city** | Markets → country → city → status **Paused** (no new orders in the city) | Works |
| **An offer or fee rule** | Pricing & Rules → the rule → Pause (kitchen offers) or End now | Works |
| **A kitchen** | Partners → kitchens shows "Paused" only when the kitchen paused itself in the Kitchen app | **Gap:** admin can't pause a kitchen |
| **All of BhojanGo** | No single switch: pause each live city | **Gap:** no platform-wide pause |

## Refunds

| What | Where | Status |
|---|---|---|
| One order, by item or in full | Operations → the order → Refund (reason, who is at fault; a second admin above the support limit) | Works |
| Orders that fail in a pause | Orders not accepted in time are cancelled and refunded in full automatically | Works |
| **Many orders at once** (a kitchen's orders in a time window, a zone's orders during an outage) | — | **Gap:** no bulk refund; today each order is refunded one by one |

## Customer messages (templates)

Send in the customer's language. Short, plain, no blame, and say what happens to their money.

- **Order can't be completed:** "We're sorry: {kitchen} can't finish your order tonight. We've cancelled it and refunded {amount} to your {method}; it usually shows in 3–5 working days."
- **Delay:** "Your order from {kitchen} is running late because of a problem on our side. It should arrive by {time}. We've added {credit} to your account for the wait."
- **Zone or city paused:** "Ordering in {area} is paused for now while we fix a problem. Orders already on their way will still arrive. We'll let you know when we're back."
- **Payment problem:** "Your payment didn't go through because of a problem with our payment provider, not your card. You haven't been charged. Please try again in a few minutes."
- **Kitchen partners:** "Ordering is paused in {area} from {time} because of {reason}. Orders already accepted still count and will be paid in your weekly payout."
- **Delivery partners:** "Offers are paused in {area} from {time}. Trips already accepted will be paid as usual, including the minimum pay for your time online."

**Gap:** there's no way to message many customers at once (all customers of a kitchen, or in a zone); today it's
one support reply at a time.

## Gaps to build before launch (not built yet)

1. Pause a kitchen from admin (with a reason and an end time, as zones have).
2. Bulk refunds: pick a kitchen or zone and a time window, see the orders and the total, a second admin approves.
3. A platform-wide pause.
4. Message many customers at once (push and email) for an incident.
