# Boise launch readiness

Everything between today and the first real Boise order. Boise is the first live city; the US is operated by
DeepTrics LLC; commission is 15%. Nothing here has been bought or done for production yet.

**Owner:** Srini (accounts, money, legal, people) or Claude Code (code, config, tests, runbooks).
**Status:** Not started, In progress, Ready (built and tested on QA, waiting for an account), Done.
**Cost:** rough figures in US dollars, to check with each vendor before buying; "per use" costs scale with orders.

| # | Item | Owner | Status | One-off | Monthly |
|---|---|---|---|---|---|
| 1 | **Production environment** on Railway from the same config as QA: no demo seed (it refuses production), sealed variables, its own database and bucket | Claude Code (after 2–4) | Ready | — | $20–50 (usage) |
| 2 | **Domain** for the website, admin and API, with DNS and TLS | Srini buys; Claude Code wires it | Not started | $10–20 a year | — |
| 3 | **Email sender** (SendGrid or similar) on the domain, with SPF, DKIM and DMARC; the "from" address | Srini opens the account; Claude Code sets DNS and keys | Not started | — | $0 (free tier), ~$20 at volume |
| 4 | **App Store and Play Console** accounts (DeepTrics LLC), listings, privacy labels, production builds of the three apps | Srini opens the accounts; Claude Code builds and submits | Not started | Apple $99 a year; Google $25 once | — |
| 5 | **Stripe live mode:** DeepTrics LLC's business details and bank account, statement descriptor "BHOJANGO", the cards-only payment method configuration, live webhooks, Connect payouts | Srini activates the account; Claude Code configures it and runs the live checks | Ready (test mode passes 9/9) | — | Per use: cards 2.9% + $0.30; Connect $2 per active account + 0.25% + $0.25 per payout |
| 6 | **Idaho sales tax:** register as a marketplace facilitator (seller's permit), then turn on Stripe Tax registrations for Idaho | Srini | Not started | Permit: free | Stripe Tax 0.5% per transaction |
| 7 | **Legal terms review:** a lawyer fills the Terms and Privacy placeholders for the US; DeepTrics LLC's registered address and support contacts entered in admin (Markets → United States → Legal entity) | Srini (lawyer); Claude Code publishes in admin | In progress (structure, versioning, legal entity done) | $1,500–5,000 | — |
| 8 | **Real kitchens:** sign-up, documents, menus and photos, Stripe Express onboarding, a tablet each, a test order per kitchen | Srini recruits; Claude Code supports onboarding | Not started | Tablets $150–250 each | — |
| 9 | **Real delivery partners:** sign-up with documents, Stripe Express onboarding, minimum pay rule for Boise, a test delivery each | Srini recruits; Claude Code supports onboarding | Not started | — | — |
| 10 | **Delivery partner checks:** background check, driver's licence (MVR) and vehicle insurance verification. Vendor: Checkr (or Certn / Sterling); the app already collects licence and insurance documents for review | Srini picks the vendor; Claude Code wires the check into sign-up | Not started | — | Per check: about $30–40 (background), $5–15 (MVR) |
| 11 | **Business insurance:** general liability for DeepTrics LLC, plus auto cover for deliveries (hired and non-owned auto, or a contingent auto / occupational accident policy for delivery partners) | Srini (broker) | Not started | — | General liability $40–125; delivery auto cover $100–300+ (quotes vary widely) |
| 12 | **1099 forms through Stripe Connect:** 1099-K / 1099-NEC for kitchens and delivery partners over the IRS threshold, filed and delivered by Stripe (needs each payee's tax details in Connect) | Srini turns it on; Claude Code checks payees' tax info is collected | Not started | Per form: about $3 federal + $1.50 state, once a year | — |
| 13 | **Support:** who answers in-app chat and call-backs and when, the support email and phone in admin, refund rules | Srini | Not started | — | Phone number $1–2 + usage |
| 14 | **Monitoring:** error tracking (Sentry) and alerts to a paging channel; uptime checks on the website, API and webhooks | Srini opens accounts; Claude Code wires them | Ready (alert rules written) | — | $0 (free tiers), ~$26 (Sentry Team) |
| 15 | **Backups:** daily database backups with a restore test, bucket versioning | Claude Code | Ready on QA (to repeat in production) | — | $1–5 (storage) |
| 16 | **Incident plan** ([incident-plan.md](incident-plan.md)): who is called, pausing, refunds, customer messages; admin → Incidents pauses a kitchen, a city, a country or everywhere, refunds in bulk (a second admin above the limit) and messages customers in bulk | Claude Code drafts and builds; Srini approves | Ready (tools built and tested in CI, round 17); plan waiting for Srini's approval and phone numbers | — | — |
| 17 | **Launch rehearsal:** a dinner rush on production with internal orders, then refunds; then the first real order | Srini and Claude Code | Not started | Card fees on test orders (not returned on refunds): under $20 | — |

Rough total before the first order: about $2,000–6,000 one-off (mostly the lawyer, tablets and app stores) and
$200–600 a month (insurance is the largest part), plus per-order payment fees.

Order: 2–4 and 5–7 can start in parallel. 1 follows 2–4. 8–13 need 5, 7 and 11. 17 comes last.
