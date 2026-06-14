# IP.PR.01 — Broken Shell

## 1. Target Score Level

Score 1 / 10. App opens but core flow is broken.

---

## 2. Score Meaning

The app technically starts, compiles, and shows a homepage. However, the primary food-ordering loop — browse → menu → cart → checkout → track — is either broken, disconnected, or missing. Users land on a homepage and get stuck.

---

## 3. Current → Target Transition

**Current:** App shows homepage. Auth works at API layer but frontend forgets session. Menu endpoint returns 500. Cart requires login and has no guest support. Users cannot browse a menu, add items, or place an order. Bcrypt/passlib dependency conflict prevents fresh clones from installing. Batch-engine migration SQL has ordering bug preventing fresh DB creation. OpenSearch not wired into docker-compose.

**Target at score 1:** Acknowledge the broken state. Diagnose top blockers. Prepare foundation for PR.02.

---

## 4. Implementation Objective

Establish baseline capability: identify exactly why the app is unusable, document root causes, and prepare the minimal foundation so that PR.02 can begin making screens navigable.

---

## 5. Scope

- Document current broken state precisely.
- Identify which services start, which fail, and why.
- List frontend pages that render blank or crash.
- Catalog API endpoints that return 4xx/5xx on core flows.
- Verify that PostgreSQL schema exists and seeded data is present.
- Ensure the comprehensive seed script can be re-run.
- Document environment/dependency blockers (bcrypt/passlib, greenlet, alembic).

---

## 6. Out of Scope

- Do NOT build new features.
- Do NOT redesign UI.
- Do NOT add production infrastructure.
- Do NOT implement auth persistence, menu fallback, or cart logic. Those belong in PR.02–PR.04.
- Do NOT add tests.

---

## 7. Required Capabilities

- Ability to start all 8 services with one script.
- Ability to see homepage at localhost:3000.
- Ability to see seeded restaurants in DB.
- Knowledge of exactly which endpoints fail.
- No manual dependency fixes required per fresh clone.

---

## 8. Key User Journeys

N/A at this level. The user cannot complete any journey.

---

## 9. Technical Coverage

- All 7 backend services boot successfully.
- Frontend dev server starts.
- PostgreSQL accessible.
- Seeded data verified.

---

## 10. UI / UX Coverage

- Homepage renders without errors.
- No blank white pages on initial load.

---

## 11. Data / Model Coverage

- Restaurants table seeded (96 records).
- Menu categories seeded.
- Menu items seeded.

---

## 12. Role / Permission Coverage

N/A.

---

## 13. Performance / Reliability / Security Coverage

N/A at this level.

---

## 14. Novelty / Differentiation Coverage

N/A at this level.

---

## 15. Implementation Work Items

### IP.PR.01.001 — Infrastructure Diagnosis (Service Boot Matrix)
- **Category:** DevEx
- **Implementation Scope:** Run `start-all.sh` and document which of the 8 services (user-svc, restaurant-svc, order-svc, delivery-svc, payment-svc, notification-svc, batch-engine, web app) boot successfully vs fail. Capture stderr and log outputs per service. Document port conflicts, DB connection failures, missing env vars.
- **Acceptance Criteria:** Service-by-service boot status matrix exists with port and status for each of the 8 services.
- **Evidence Required:** Service boot matrix table (service name, port, boot status, first error if failed).
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.002 — Pin bcrypt Dependency Across All Python Services
- **Category:** DevEx
- **Implementation Scope:** Update `pyproject.toml` or `requirements.txt` in all 6 Python backend services to pin `bcrypt<5.0.0` and remove conflicting passlib references that cause install failures. Ensure `poetry install` or `pip install` completes on a fresh Python 3.12 virtual environment without manual overrides.
- **Acceptance Criteria:** Each Python service installs cleanly from a fresh `.venv` without manual `pip` fixes. No import errors on startup.
- **Evidence Required:** Terminal output of `poetry install` or `pip install -r requirements.txt` completing successfully in each of the 6 Python services.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.003 — Fix Batch-Engine Migration SQL Ordering
- **Category:** Data
- **Implementation Scope:** In `batch-engine/migrations/001_create_batch_tables.sql` (or equivalent), locate the SQL that defines `order_pool` with a foreign key referencing `batches(id)`. Reorder the script so `batches` table is created before `order_pool` and any other table referencing it.
- **Acceptance Criteria:** Fresh database initialization runs `batch-engine` migrations without SQL errors. No manual migration reordering needed on new clone.
- **Evidence Required:** Migration execution log on fresh DB showing success.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.004 — Verify PostgreSQL Seeded Data Presence
- **Category:** Data
- **Implementation Scope:** Connect to the project PostgreSQL instance (port 5432 or docker-compose service). Run row-count queries against `restaurants`, `menu_categories`, `menu_items`, `users`, `orders`, `reviews` tables. Document counts. Verify 96 restaurant records exist per the seed script.
- **Acceptance Criteria:** Row counts are documented. Restaurants table shows ≥90 records. Menu categories and items are non-empty.
- **Evidence Required:** Screenshot or terminal output of `SELECT COUNT(*) FROM ...` results for restaurants, menu_categories, menu_items, users, orders.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.005 — API Health Check Catalog (Per-Service)
- **Category:** Backend
- **Implementation Scope:** For each backend service, run its `GET /health` endpoint and document response (HTTP status, latency). Then test the core food-ordering endpoints that are expected to fail and document exact HTTP status and response: `GET /api/v1/restaurants` (list), `GET /api/v1/restaurants/{id}/menu` (menu 500), `POST /api/v1/orders` (order creation), `GET /api/v1/me` (missing endpoint). Use `curl` or a simple HTTP client script.
- **Acceptance Criteria:** Health check matrix exists with per-service port, /health status, and a list of core endpoints with their actual HTTP status codes.
- **Evidence Required:** Health check matrix table. Screenshot or terminal output of failing endpoint responses.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.01.001 (services must be running to test)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.006 — Document Environment and Dependency Blockers
- **Category:** DevEx
- **Implementation Scope:** Create a concise `BLOCKERS.md` (or add section to this doc) listing every blocker a developer hits on a fresh clone: (a) bcrypt/passlib version conflict, (b) greenlet missing/architecture mismatch, (c) Alembic migration stamp collisions across services (if observed), (d) OpenSearch not in docker-compose, (e) missing `GET /api/v1/me` endpoint causing frontend auth failure, (f) frontend session persistence gap. Include reproduction commands.
- **Acceptance Criteria:** A developer reading the doc can reproduce every blocker from a clean clone in under 10 minutes.
- **Evidence Required:** Doc file exists with reproduction steps and observed error messages.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.01.001, IP.PR.01.005
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.007 — Add OpenSearch to docker-compose
- **Category:** Infra
- **Implementation Scope:** Add an `opensearch` service to the project's `docker-compose.yml` (or equivalent local dev file) using the official OpenSearch 2.14 Docker image. Configure single-node mode for local development. Update the `restart` logic or environment variable to point the restaurant service at it. Ensure it starts cleanly alongside PostgreSQL and Redis.
- **Acceptance Criteria:** `docker-compose up opensearch` starts without error. Restaurant service can connect to it on localhost:9200. Menu endpoint no longer fails solely due to missing OpenSearch container.
- **Evidence Required:** `docker ps` output showing opensearch container running. `curl localhost:9200` returns cluster info.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.01.001
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.008 — Frontend Blank-Page Audit
- **Category:** Frontend
- **Implementation Scope:** With the web dev server running, navigate to every page listed in the frontend route table and record which ones render content vs show blank/white screen or crash: `/`, `/restaurants`, `/restaurants/[id]`, `/cart`, `/checkout`, `/orders`, `/profile`, `/wallet`, `/login`, `/signup`. Note any console errors.
- **Acceptance Criteria:** Page-by-page rendering matrix exists with status (OK, blank, error) and any console error summary.
- **Evidence Required:** Table or screenshots of each page with console errors noted.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.01.001
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.009 — Verify `start-all.sh` Runs End-to-End
- **Category:** DevEx
- **Implementation Scope:** Execute `start-all.sh` from a fully clean state (no running containers, no active .venv). Document every step that requires manual intervention or fails. If the script does not exist, file this as a blocker.
- **Acceptance Criteria:** Script execution log exists showing each step and any failures. If script is missing, that fact is documented.
- **Evidence Required:** Terminal log of `start-all.sh` execution.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.01.002, IP.PR.01.003
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.PR.01.010 — Document Menu Endpoint Failure Root Cause
- **Category:** Backend
- **Implementation Scope:** Investigate the exact stack trace and root cause of `GET /api/v1/restaurants/{id}/menu` returning 500. Determine whether it is (a) OpenSearch connection failure, (b) missing DB fallback to `menu_categories` + `menu_items`, (c) bad SQL join, or (d) unhandled exception in the route handler. Log findings.
- **Acceptance Criteria:** Root cause identified and documented in this plan's blockers section.
- **Evidence Required:** Exact stack trace or error message from the endpoint. Evidence source (log, test, manual curl).
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.01.005
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

---

## 16. Acceptance Criteria

- All services can be started with `start-all.sh`.
- `curl localhost:3000` returns HTML.
- `curl localhost:8005/health` (payment-svc) returns 200.
- `psql` shows >90 restaurants.
- Document of failing endpoints exists.

---

## 17. Evidence Required

- Screenshots of homepage.
- API health check matrix (service, port, status).
- DB row counts per table.
- List of 500/404 errors on core endpoints.

---

## 18. Dependencies

- Docker (or local PostgreSQL) running.
- Node.js and pnpm installed.
- Python per-service `.venv` configured.

---

## 19. Risks / Blockers

- **Bcrypt conflict persists across fresh installs.** If pinning does not resolve the issue (e.g. passlib still pulls incompatible version), a more aggressive dependency swap may be needed.
- **Alembic migration stamps collide across services.** Multiple services may share the same `alembic_version` table if using a single PostgreSQL database with schemas. This can cause migration stamp conflicts on fresh setup.
- **OpenSearch optional but menu-svc may silently depend on it.** Even after adding the container, the service may still crash if index creation is required before first query.
- **Frontend auth session loss may be caused by missing `/api/v1/me` endpoint.** The frontend may not be broken per se, but is starved of user data. This is documented as a blocker, not fixed here.
- **Batch-engine migration ordering bug may mask other SQL issues.** Fixing the FK ordering may reveal subsequent migration failures.
- **Mobile app not covered in this IP.** PR.01 focuses on the web path; mobile gaps are noted but not the primary diagnostic target.

---

## 20. Exit Criteria

- All services start without manual intervention.
- Seeded data present.
- Documented list of broken endpoints.
- PR.01 declared complete.

---

## 21. Connected Previous-Level Requirements

N/A (this is the lowest level).

---

## 22. Connected Next-Level Requirements

PR.02 (Browsable Prototype) requires PR.01's fixed startup sequence and dependency resolution. PR.02 will be blocked if:
- `start-all.sh` still fails, or
- the menu endpoint 500 root cause is not clearly documented, or
- bcrypt conflict is not resolved.

---

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (1/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state is described (what is broken) | Planner | ✅ |
| 4 | Target state is described (what "done" looks like) | Planner | ✅ |
| 5 | Scope section lists exactly what PR.01 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.01 does NOT cover | Planner | ✅ |
| 7 | No new features or UI redesign in scope | Planner | ✅ |
| 8 | Key user journeys explicitly marked N/A | Planner | ✅ |
| 9 | Technical coverage lists service-level targets | Planner | ✅ |
| 10 | UI/UX coverage limited to homepage + no blank pages | Planner | ✅ |
| 11 | Data/model coverage mentions restaurants, categories, items | Planner | ✅ |
| 12 | Role/permission coverage marked N/A | Planner | ✅ |
| 13 | Perf/reliability/security marked N/A | Planner | ✅ |
| 14 | Novelty/differentiation marked N/A | Planner | ✅ |
| 15 | Work items use the exact required format | Planner | ✅ |
| 16 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 17 | At least 8 work items present | Planner | ✅ |
| 18 | Work items include: infra diagnosis, dependency resolution, migration fix, seed verification, API health catalog | Planner | ✅ |
| 19 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 20 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 21 | Dependencies list external tools (Docker, Node, Python) | Planner | ✅ |
| 22 | Risks / Blockers mention bcrypt, alembic stamps, OpenSearch | Planner | ✅ |
| 23 | Exit criteria are clear and minimal | Planner | ✅ |
| 24 | Connected next-level requirement (PR.02) is referenced | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

---

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required categories (infra, deps, migrations, seed data, API health).
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in known issues from the audits (bcrypt, alembic stamps, OpenSearch).
- The plan strictly avoids building new features, redesigning UI, or adding production infrastructure — consistent with the "Broken Shell" level objective.
- **One point deducted** because some specific file paths (e.g. exact `pyproject.toml` locations, exact migration filename) are not yet known from the plan stage. The build phase will need to discover these. This is expected for a planning document.

The document is ready for execution.
