# Go-live status

**As of 2026-11-14**, against the 44 tasks in [BhojanGo_GoLive_Tracker.docx](BhojanGo_GoLive_Tracker.docx). Pull
request numbers (#nn) are on `BhojanGo/BhojanGo`; what each one did and how it was tested is in
[PROGRESS.md](PROGRESS.md). Tracker tasks are "task nn".

| Status | Count | Meaning |
|---|---|---|
| ✅ Done | **21** | The tracker's "done when" can be shown on `make dev` today |
| ⛔ Blocked on Srini | **15** | Needs money, an account or a decision only Srini can make. Where code is involved, it is written and waiting (noted) |
| ⬜ Not started | **8** | Pilot and launch work that starts once the blocked items clear |

The engineering in Phases 0–3 is done. Everything between here and the closed beta waits on the blocked items,
mostly the accounts (task 4) and the domain (task 3). Two things that cost nothing are also ready:

- **Railway config.** Going live is a short list of steps ([railway-deploy.md](runbooks/railway-deploy.md), #49).
- **Pilot dress rehearsal.** A two-hour Boise dinner rush has been run, first with 8 riders and then with 25 ([load/soak-report.md](load/soak-report.md), #50, #55).

## What Srini needs to do, in order

1. **Task 1, decisions:** the pilot city order and the team model. The commission % is set as a rule (15% in the worked
   example) and can be changed in admin without a developer.
2. **Task 3, domain and handles**, then **task 4, accounts**. Each account replaces a local fake that's already wired; only
   keys need to be added ([11_Integration_Setup_Guide.md](11_Integration_Setup_Guide.md)). Railway (or AWS) is the
   account that unblocks task 10.
3. **Tasks 2, 22, 35 and 33** (trademark, logo artwork, legal pack, outside pen test) need outside vendors, which
   are paid.
4. **Task 5, the team.** It also sets the on-call rota (task 34).
   Plan for 25 riders in Boise: the dress rehearsal (#55) shows they carry the dinner rush, and 8 can't.
5. **Task 36, app store accounts** (Apple $99 a year, Google $25 once).
6. **Task 43, batching:** when to switch it on, per city. It's ready, and it's one checkbox in admin. The
   recommendation is off at launch, and on for nights when riders are short (#55).

## Phase 0 · Set up

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 1 | Make the open decisions | ⛔ Blocked on Srini | #27 | Phase 1 money decisions were made and coded (#27: who pays for a refund, rider floor over engaged time). Still open: the pilot city order and the team model. The commission % is a rule, 15% in the seed |
| 2 | Trademark search: name + logo C | ⛔ Blocked on Srini | — | Lawyer (money) |
| 3 | Buy domain and social handles | ⛔ Blocked on Srini | — | Money. Needed for web indexing (task 27), email sending and app store listings |
| 4 | Open vendor accounts | ⛔ Blocked on Srini | #14 | Accounts. Every provider (Stripe, Razorpay, Twilio, MSG91, SendGrid, Maps, Apple/Google sign-in, push, S3) runs as a local fake with no account (#14). Sentry has an adapter that is off (#44) |
| 5 | Line up the team | ⛔ Blocked on Srini | — | Hiring |
| 6 | Put the plan and specs in the repo | ✅ Done | #8 | `docs/specs/01-structure.md`, `02-restructure-map.md` |
| 7 | Repo restructure | ✅ Done | #8, #10 | core_api / realtime / worker; customer and rider apps |
| 8 | Lock the tech stack | ✅ Done | #11, #29 | ADR-011; ADRs 002, 006–009 updated; platform upgrade in #29 |
| 9 | One-command local setup | ✅ Done | #12 | `make dev` with Hyderabad and Boise seed data |
| 10 | CI/CD and staging | ⛔ Blocked on Srini | #13, #43, #49 | CI runs on every PR (#43). Staging needs a hosting account: the AWS Terraform and deploy workflow are written (#13), and Railway config-as-code is ready ([railway-deploy.md](runbooks/railway-deploy.md)). Nothing is deployed (zero spend) |

## Phase 1 · Foundation

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 11 | Sign-in and admin roles | ✅ Done | #15 | Phone OTP, Apple, Google (against local fakes), roles scoped to country / state / city |
| 12 | Markets | ✅ Done | #16 | India ▸ Telangana ▸ Hyderabad set up in admin, PostGIS zones |
| 13 | Rule engine | ✅ Done | #17 | Versioned rules with maker-checker; pause added in #40 |
| 14 | Quote engine + price simulator | ✅ Done | #18, #36 | The Hyderabad example matches ₹638.22 to the paisa |
| 15 | Tax | ✅ Done | #19 | Stripe Tax for the US (fake locally), GST rules for India |
| 16 | Menu modifiers and store hours | ✅ Done | #20 | |
| 17 | Order flow with payments | ✅ Done | #21 | Payment first, timeouts, outbox |
| 18 | Payments and refunds | ⛔ Blocked on Srini | #22, #41 | Refund by item is done. "Stripe + Razorpay live in test mode" needs the two accounts (free test mode); the code runs against fakes with the providers' real flows |
| 19 | Payouts | ✅ Done | #23, #27, #42 | Weekly only (#42) |
| 20 | Dispatch and live tracking | ✅ Done | #24, #45, #50, #53 | Nearest rider, 30 s offer, re-offer; holds 10× pilot load (#45); waiting orders served oldest first (#50); pair offers when batching is on (#53) |
| 21 | Notifications | ✅ Done | #25, #38 | Push, SMS, email in en / hi / te (fakes). India DLT template registration comes with the MSG91 account (task 4) |

## Phase 2 · Apps

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 22 | Final logo artwork and icons | ⛔ Blocked on Srini | #30 | Icons, splash and favicons are generated from the current logo (#30). The final vector from a designer, and its approval, are paid work |
| 23 | Design tokens and shared components | ✅ Done | #30 | |
| 24 | Customer app | ✅ Done | #31, #36, #38, #41 | Every board screen built; tested on Android emulators. Do a pass on real phones before task 36 |
| 25 | Rider app | ✅ Done | #32, #37, #38, #42 | Offer to payout with background GPS (emulator) |
| 26 | Partner tablet app | ✅ Done | #33, #37, #39, #40 | |
| 27 | Customer website | ⛔ Blocked on Srini | #34, #37, #41 | Ordering on the web works, and city and kitchen pages are server-rendered with sitemaps and structured data. "Indexed" needs the domain (task 3) and a deployment |
| 28 | Admin console | ✅ Done | #35, #36 | Country tabs, state chips and the city picker on every page |
| 29 | Usability tests | ⬜ Not started | — | 5 customers, 3 riders and 3 kitchens per city: real people, so after staging is up |

## Phase 3 · Harden

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 30 | Automated tests | ✅ Done | #43, #52 | Playwright and G1 on every PR. Maestro runs locally on emulators, not on GitHub. Every scanner proves itself first: gitleaks, semgrep and the access-control sweep must catch planted findings (#52) |
| 31 | Monitoring and alerts | ⛔ Blocked on Srini | #44, #50 | Dashboards and alerts work locally (`make observe`); alerts reach the admin console and the logs. "Sentry" and "reach on-call phone" need a Sentry account and a paging channel |
| 32 | Load test | ✅ Done | #45, #50, #55 | 10× pilot peak, 0 failures, every p95 under 100 ms (#45). Two-hour Boise dinner rush: with 25 riders, 100% completion, max wait for a rider 0.5 min, no alerts, 0 errors (#55; the first run with 8 riders found and fixed three problems, #50) |
| 33 | Security test | ⛔ Blocked on Srini | #46, #48, #52 | The automated pass is done and every High has been fixed (#46). An outside pen test is paid |
| 34 | Backup drill and runbook | ⛔ Blocked on Srini | #47 | Database restored in the drill. The on-call rota needs the team (task 5) |
| 35 | Legal pack | ⛔ Blocked on Srini | — | Lawyer (money) |
| 36 | App store submission | ⛔ Blocked on Srini | — | Apple and Google developer accounts (money), and the domain for privacy URLs |

## Phase 4 · Pilot and Phase 5 · Go live

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 37 | Sign launch restaurants | ⬜ Not started | #37 | Self sign-up and the admin approval queue are ready (#37) |
| 38 | Onboard riders | ⬜ Not started | #37 | Rider sign-up and the document checklist are ready. Background checks are a paid vendor. Plan for 25 in Boise: they carry the dinner rush with a third free at the peak; 8 can't (#50, #55) |
| 39 | Closed beta | ⬜ Not started | — | Needs staging or production, and the apps in the stores |
| 40 | Paid pilot | ⬜ Not started | #44 | KPI dashboards are ready (#44) |
| 41 | Go / no-go review | ⬜ Not started | — | Srini's decision, after task 40 |
| 42 | Grow the city | ⬜ Not started | — | Referrals and offers exist as rules (#17) |
| 43 | Turn on batching | ⛔ Blocked on Srini | #24, #53, #54 | Ready (#53, #54): the engine is ported to Python and runs in shadow everywhere, and live pairs from one kitchen are a per-city switch in admin (off). Turning it on is a decision. In the rehearsal it paired 60% of orders and saved a third of rider trips, at about +1 min median delivery; the recommendation is off at launch, on when riders are short (#55) |
| 44 | Public launch | ⬜ Not started | — | |
