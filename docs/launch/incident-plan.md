# Incident plan (draft)

For Boise's launch. What to do when orders can't be placed, paid, cooked or delivered, or when money or data is
at risk. Draft for Srini to approve; names and phone numbers are filled in before launch.

The tools are in admin → **Incidents** (round 17). Every action there needs the right role, a reason and a
confirmation step, and is written to the audit log (the **Log** at the bottom of the page).

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
3. Look at what was already caught: orders placed but not accepted, paid but not delivered (Operations).
4. Tell the people affected (Incidents → Message customers; the templates below).
5. Fix or roll back (Railway: redeploy the last good build); then resume, watching the first orders.
6. Refund what went wrong (Incidents → Bulk refund), and tell those customers.
7. Within two days: a short write-up (what happened, the cause, the fix) and a PLAYBOOK lesson if it cost more than an hour.

## Pausing

New orders stop; **orders already placed carry on** (they can still be paid, cooked and delivered).

| What | Where in admin | Who |
|---|---|---|
| **Everywhere** | Incidents → Pause ordering → Where: Everywhere | Super admin |
| **A country** | Incidents → Pause ordering → Where: This country (country in the scope bar) | Country manager |
| **A city** | Incidents → Pause ordering → Where: This city (city in the scope bar) | Country manager, city ops |
| **A zone** | Markets → country → city → the zone → "Pause this zone…" (a reason and an end time) | Country manager, city ops |
| **A kitchen** | Incidents → Pause a kitchen: find it, optional "Back at" time | Country manager, city ops |
| **An offer or fee rule** | Pricing & Rules → the rule → Pause (kitchen offers) or End now | Rule editors |

- An ordering pause has an optional **note for customers** ("Back by 9 pm") and an optional end time. The website
  and the customer app show "Ordering in {area} is paused for now while we fix a problem. Orders already on their
  way will still arrive." in the customer's language, plus the note as written. The reason stays with admins.
- While ordering is paused, the bag on the website and in the app says "Ordering is paused" (or "This kitchen is
  closed for now") and its checkout button is disabled with the same words.
- A paused kitchen shows **"Closed for now"** to customers (and "Back around {time}" when a time is set); its menu
  can be read but not ordered from. The kitchen can't undo it from its tablet; it reopens at the "Back at" time
  or when an admin resumes it.
- Resume from the same place: "Resume ordering" / "Resume", with a reason.

## Refunds

| What | Where | Who |
|---|---|---|
| One order, by item or in full | Operations → the order → Refund (reason, who is at fault) | Support (up to its limit), city ops, country manager, finance |
| Orders that fail in a pause | Orders not accepted in time are cancelled and refunded in full automatically | Automatic |
| **Many orders at once** | Incidents → Bulk refund: a kitchen, a zone or the whole city, a time window (7 days at most), in full or a percentage → Preview (each order, the count and the total) → reason → confirm | City ops, country manager, finance |

- A bulk refund goes through the payment provider order by order (Stripe in test mode on QA); one failure doesn't
  stop the others, and the list shows how many failed.
- **Above the city's automatic refund limit** (business rule "Automatic refunds for problem reports", per order) a
  **second admin** (country manager or finance, not the one who asked) approves it from the same list first.
- BhojanGo pays bulk refunds: kitchens' payouts don't change (a kitchen's own mistake is refunded by item instead).

## Customer messages (templates)

Incidents → **Message customers**: to the customers of a bulk refund (one message per refunded order, with its
kitchen and amount) or to everyone who ordered in a city in the last day, 7 or 30 days (the city is picked from
the cities you look after; {area} in a message is that city's name from Markets, never typed). Push and email, each
customer in their own language (8 languages; texts in `backend/shared/texts.py` `INCIDENT_MESSAGES`). Preview first:
how many people, and the message in English. **Outside production only test accounts get it** (the seed's
`@example.com` addresses and test phone numbers); the preview says how many others were left out.

| Message | Placeholders | Audience |
|---|---|---|
| **Order can't be completed:** "We're sorry: {restaurant} can't finish your order {code}. We've cancelled it and refunded {amount} to how you paid; it usually shows in 3–5 working days." | from each order | A bulk refund's customers |
| **Refund sent:** "We're sorry about your order {code} from {restaurant}. We've refunded {amount} to how you paid; it usually shows in 3–5 working days." | from each order | A bulk refund's customers |
| **Delay:** "Your order is running late because of a problem on our side. It should arrive by {time}. We're sorry for the wait." | {time}: typed by the admin | Either |
| **Ordering paused:** "Ordering in {area} is paused for now while we fix a problem. Orders already on their way will still arrive. We'll let you know when we're back." | {area}: the recipients' city | Either |
| **We're back:** "Ordering in {area} is open again. Thank you for waiting." | {area}: the recipients' city | Either |
| **Payment problem:** "Your payment didn't go through because of a problem with our payment provider, not your card. You haven't been charged. Please try again in a few minutes." | none | Either |

Kitchens and delivery partners (support line or the partner apps, one at a time for now):

- **Kitchen partners:** "Ordering is paused in {area} from {time} because of {reason}. Orders already accepted still count and will be paid in your weekly payout."
- **Delivery partners:** "Offers are paused in {area} from {time}. Trips already accepted will be paid as usual, including the minimum pay for your time online."

## Still to build (not in round 17)

1. Messages to kitchens and delivery partners in bulk (customers only today).
2. A credit to customers' BhojanGo balance in bulk (refunds go back to how they paid).
3. A text message (SMS) channel for bulk messages (push and email today).
