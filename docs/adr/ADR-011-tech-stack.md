# ADR-011: Tech stack and pinned versions

## Status
Accepted (Nov 11, 2026). Amends ADR-002 and ADR-006; supersedes ADR-007, ADR-008 and ADR-009.

## Context
Before go-live, the stack had drifted from the decisions in `docs/specs/01-structure.md`
(Nov 4, 2026): seven services behind Kong, Cognito in the auth story, OpenSearch for
search, and versions chosen per service. P1 restructured the repo into three backend
deployables and three Expo apps. This ADR locks what we build on from here, so P3–P24
don't each re-decide it.

## Decision

### Shape
| Deployable | Code | Port (local) | Role |
| --- | --- | --- | --- |
| core_api | `backend/core_api` | **8001** | identity, catalog, orders, payments; later markets, rules, pricing, promotions, finance, audit |
| realtime | `backend/realtime` | **8004** | rider GPS, tracking WebSocket (`/ws/track/{order_id}`), dispatch, ETA |
| worker | `backend/worker` | **8006** | outbox relay, notifications, payouts, batching |

Apps: `apps/customer`, `apps/rider`, `apps/partner` (Expo); `apps/web`, `apps/admin` (Next.js).
Locally, apps and tests call the three ports directly; Kong leaves the local setup in P3.
In AWS, an Application Load Balancer with WAF routes by path to the three ECS services (P4).

### Pinned versions
Checked against npm, PyPI, nodejs.org and Docker Hub on Nov 11, 2026. "Today" is what
`dev` runs after P1; "Moves in" is the prompt that brings each component to the pinned
version.

| Area | Choice | Pinned | Today | Moves in |
| --- | --- | --- | --- | --- |
| Language | Python | **3.12** (3.12.16) | 3.12 | — (done) |
| API framework | FastAPI | **0.162.4** | 0.111 | P3 |
| ORM | SQLAlchemy 2 (async) | **2.1.8** | 2.1.8 | — (done) |
| Validation | Pydantic 2 | **2.14.3** | 2.14.3 | — (done) |
| Migrations | Alembic | **1.20.1** (one history, `alembic check` in CI) | 1.20.1 | — (done) |
| ASGI server | uvicorn | **0.54.0** | 0.30.6 | P3 |
| DB driver | asyncpg | **0.32.0** | 0.29.0 | P3 |
| Python tooling | uv | **0.13.7** (one `uv.lock`) | 0.13.7 | — (done) |
| Database | PostgreSQL + PostGIS | **16 + PostGIS 3.7** (`postgis/postgis:16-3.7`) | 16 + 3.4 | P3 (local), P4 (RDS) |
| Cache / geo | Redis | **7.4** (`redis:7.4-alpine`; ElastiCache Redis OSS 7) | 7 | P3 (local), P4 (AWS) |
| Search | PostgreSQL full-text + `pg_trgm` | Postgres 16 (no extra service) | OpenSearch | P4 removes OpenSearch; catalog search moves to Postgres |
| Auth | Custom, RS256 JWTs + JWKS | — | HS256 shared secret | P5 |
| Node.js | Node **24 LTS** | **24.22.3** | 20 in CI | P3/P4 |
| JS package manager | pnpm | **12.18.0** | 9 | P3/P4 |
| Monorepo tasks | Turborepo | **2.11.11** | 2.x | P3/P4 |
| Web + admin | Next.js (latest stable) + React 19 | **16.4.6** | 14.2 | P20 (web), P21 (admin) |
| Mobile | Expo (latest SDK) + EAS | **SDK 58** (expo 58.0.24, React Native 0.88.1, React 19.3), **EAS CLI 27.7.2** | SDK 51 | P16–P19 |
| Compute | AWS ECS Fargate | 3 services (core-api, realtime, worker) | 6 in Terraform | P4 |
| Database (AWS) | RDS for PostgreSQL 16 + PostGIS | — | RDS 16.3 | P4 |
| Cache (AWS) | ElastiCache (Redis OSS 7) | — | ElastiCache 7.1 | P4 |
| Messaging | SQS (+ SNS fan-out where needed) | — | SQS/SNS | — |
| Storage | S3 (+ CloudFront for assets) | — | S3 | — |
| Edge | ALB + AWS WAF | — | Kong | P3 (local), P4 (AWS) |
| Payments (US) | Stripe, incl. Stripe Tax and Connect | **stripe-python 16.1.0** | 9.12 | P9, P12, P13 |
| Payments (India) | Razorpay, incl. Route | **razorpay 2.0.1** | 1.4.2 | P12, P13 |
| Errors | Sentry | **sentry-sdk 2.74.0** (+ Sentry SDKs for Next.js and Expo) | none | P23 |
| Tracing | OpenTelemetry | **opentelemetry-sdk 1.45.2** | none | P23 |

### Version policy
- The versions above are the floor. Patch and minor updates within the same major go
  through normal PRs (lockfiles: `backend/uv.lock`, `pnpm-lock.yaml`).
- A **major** upgrade (e.g. Expo SDK, Next.js, Node, PostgreSQL) needs an amendment to
  this ADR first.
- Expo apps take native package versions from the SDK (`npx expo install --fix`), never
  hand-picked; P1 showed that drifting past the SDK crashes Expo Go.
- Production images build from the lockfiles only (`uv sync --frozen`,
  `pnpm install --frozen-lockfile`).

## Consequences
- One way to run, test and deploy each piece; later prompts don't re-litigate the stack.
- Fewer moving parts in AWS: no Kong, OpenSearch, DynamoDB or Cognito. P4 removes them
  from Terraform. Search quality relies on Postgres FTS + trigram + PostGIS distance,
  which covers city-scale catalogs.
- We own auth (P5): key rotation, JWKS and revocation are our job, but there is no
  per-user vendor cost and no lock-in.
- Several components are behind their pins today; the "Moves in" column is the plan,
  not a promise that `dev` already matches.

## Alternatives considered
- **Keep Kong**: an extra service to run and secure; its JWT plugin already rejected our
  tokens. ALB + WAF covers routing, TLS and rate limits at the edge.
- **Keep OpenSearch**: better fuzzy search at very large scale, but it means a cluster,
  index sync and a second source of truth for a pilot with two cities.
- **Cognito / Auth0 / Clerk**: less code, but phone OTP with Indian DLT templates, admin
  scopes per market and RS256/JWKS for three apps fit poorly or cost more at scale.
- **Node 26** (the newer active LTS since Oct 2026): revisit at Phase 5 (see decisions above).
- **EKS instead of ECS Fargate**: rejected in ADR-010; still holds.

## Decisions on the open questions (Nov 11, 2026)
1. **Node 24 stays.** The specs pin Node 24 LTS; Node 26 became the active LTS in Oct 2026
   and Node 24 is in maintenance until Apr 2028. Keep 24 for now and **revisit at Phase 5**.
2. **Backend libraries move in P3.** FastAPI, uvicorn, asyncpg and the other backend
   libraries are upgraded to the pins above in P3 (with `make dev`), so P5 builds the new
   auth on the pinned versions.

## References
- `docs/specs/01-structure.md` §1 (layout) and §7 (decisions, Nov 4, 2026)
- `docs/specs/02-restructure-map.md` (P1)
- ADR-002, ADR-006, ADR-007, ADR-008, ADR-009, ADR-010
