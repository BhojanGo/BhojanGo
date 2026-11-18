# Boise launch readiness

Everything between today and the first real Boise order. Boise is the first live city; the US is operated by
DeepTrics LLC; commission is 15%. Nothing here has been bought or done for production yet.

**Owner:** Srini (accounts, money, legal, people) or Claude Code (code, config, tests, runbooks).
**Status:** Not started, In progress, Ready (built and tested on QA, waiting for an account), Done.
**Cost:** whether it costs money.

| # | Item | Owner | Status | Cost |
|---|---|---|---|---|
| 1 | **Production environment** on Railway from the same config as QA: no demo seed (it refuses production), sealed variables, its own database and bucket | Claude Code (after 2–4) | Ready | Yes (Railway usage) |
| 2 | **Domain** for the website, admin and API, with DNS and TLS | Srini buys; Claude Code wires it | Not started | Yes |
| 3 | **Email sender** (SendGrid or similar) on the domain, with SPF, DKIM and DMARC; the "from" address | Srini opens the account; Claude Code sets DNS and keys | Not started | Free tier, then paid |
| 4 | **App Store and Play Console** accounts (DeepTrics LLC), listings, privacy labels, production builds of the three apps | Srini opens the accounts; Claude Code builds and submits | Not started | Yes (Apple yearly, Google once) |
| 5 | **Stripe live mode:** DeepTrics LLC's business details and bank account, statement descriptor "BHOJANGO", the cards-only payment method configuration, live webhooks, Connect payouts | Srini activates the account; Claude Code configures it and runs the live checks | Ready (test mode passes 9/9) | Stripe fees per payment |
| 6 | **Idaho sales tax:** register as a marketplace facilitator, then turn on Stripe Tax registrations for Idaho | Srini | Not started | Possibly a filing fee; Stripe Tax per transaction |
| 7 | **Legal terms review:** a lawyer fills the Terms and Privacy placeholders for the US; DeepTrics LLC's registered address and support contacts entered in admin (Markets → United States → Legal entity) | Srini (lawyer); Claude Code publishes in admin | In progress (structure and versioning done) | Yes (lawyer) |
| 8 | **Real kitchens:** sign up, documents, menus and photos, Stripe Express onboarding, a tablet each, a test order per kitchen | Srini recruits; Claude Code supports onboarding | Not started | No (tablets: yes) |
| 9 | **Real delivery partners:** sign-up with documents, Stripe Express onboarding, minimum pay rule for Boise, a test delivery each | Srini recruits; Claude Code supports onboarding | Not started | No |
| 10 | **Support:** who answers in-app chat and call-backs and when, the support email and phone in admin, refund rules | Srini | Not started | Maybe (a phone number) |
| 11 | **Monitoring:** error tracking (Sentry) and alerts to a paging channel; uptime checks on the website, API and webhooks | Srini opens accounts; Claude Code wires them | Ready (alert rules written) | Free tiers, then paid |
| 12 | **Backups:** daily database backups with a restore test, bucket versioning | Claude Code | Ready on QA (to repeat in production) | Small (storage) |
| 13 | **Incident plan:** who is called, how to pause a city or a kitchen, how to refund in bulk, how to talk to customers | Claude Code drafts; Srini approves | Not started | No |
| 14 | **Launch rehearsal:** a dinner rush on production with internal orders, then refunds; then the first real order | Srini and Claude Code | Not started | Small (real payments, refunded) |

Order: 2–4 and 5–7 can start in parallel. 1 follows 2–4. 8–10 need 5 and 7. 14 comes last.
