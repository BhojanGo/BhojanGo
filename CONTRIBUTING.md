# Contributing to BhojanGo

Thank you for contributing to BhojanGo! This guide helps you get set up and follow our development practices.

## Prerequisites

- **Node.js** 20+ and **pnpm** 9+
- **Python** 3.11+ and **Poetry**
- **Docker** and **Docker Compose**
- **Git** with conventional commit support

## Local Setup

Everything in Docker (only Docker + make needed): see README, **Run it locally**.

```bash
git clone https://github.com/BhojanGo/BhojanGo.git
cd BhojanGo
make dev      # all services, migrations, Hyderabad + Boise seed data
make test     # backend pytest + JS lint/typecheck/test, inside Docker
make ci       # everything GitHub CI runs; must pass before merging
make down     # stop (make reset wipes the data and starts again)
```

To work on code with hot reload, keep the databases in Docker and run the piece
you're changing on the host (needs uv, Node 24 and pnpm):

```bash
docker compose --profile infra up -d --wait     # Postgres, Redis, LocalStack
cd backend && uv sync
uv run alembic upgrade head && uv run python ../tools/seed/seed.py
uv run uvicorn core_api.main:app --reload --port 8001
uv run uvicorn app.main:app --app-dir realtime --reload --port 8004
uv run uvicorn app.main:app --app-dir worker --reload --port 8006
cd .. && pnpm install && pnpm dev                 # web :3000, admin :3001
pnpm --filter @bhojango/customer start             # or @bhojango/rider; see apps/*/.env.example
```

The host-run backend reads `backend/.env` (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`); see
`.env.example`. Apps and tests call core_api :8001, realtime :8004 and worker :8006
directly: there is no gateway.

## Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<description>` | `feature/driver-earnings-page` |
| Bug fix | `fix/<description>` | `fix/order-pricing-bug` |
| Hotfix | `hotfix/<description>` | `hotfix/payment-webhook-crash` |
| Chore | `chore/<description>` | `chore/update-dependencies` |
| Docs | `docs/<description>` | `docs/api-reference` |

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(orders): add idempotency key support for order creation
fix(identity): prevent timing attack in login endpoint
chore: update Python dependencies across all services
docs: add operations runbook
```

**Types:** `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`, `perf`, `ci`

## Pull Request Process

1. Create a feature branch from `dev`
2. Make your changes with clear, atomic commits
3. Run `make ci` (only Docker needed). **`make ci` passing locally is the merge gate**; GitHub Actions runs the same checks when minutes are available
4. Open PR to `dev` branch
5. Fill out the PR template completely
6. Request review — response expected within 24 hours
7. One approver required for merge
8. Squash merge into `dev`

## Code Review Expectations

- Reviewers respond within 24 hours
- Focus on correctness, security, and maintainability
- Approve if the code meets standards — don't block on style preferences
- Use "Request Changes" only for issues that must be fixed

## Adding a New Backend Module

New business areas are core_api modules, not new services (see
[docs/specs/01-structure.md](docs/specs/01-structure.md)).

- [ ] Create `backend/core_api/modules/<name>/` with `api/`, `service/`, `repository/`, `models/`, `schemas/` and `tests/`
- [ ] Add a `main.py` with `register(app)` and add it to `MODULES` in `backend/core_api/main.py`
- [ ] Models use `shared.db.Base`; import them in `backend/migrations/env.py` and add an Alembic revision
- [ ] Settings go in a section of `backend/shared/config.py`
- [ ] Read other modules only through their `service/`, never their tables
- [ ] Add its route prefix to the ALB rules in Terraform (P4) if it isn't under `/api/v1` on core_api

## Adding a New API Endpoint

- [ ] Define Pydantic request/response schemas
- [ ] Implement repository method
- [ ] Implement service method
- [ ] Add FastAPI route with proper auth dependency
- [ ] Write unit tests (>80% coverage)
- [ ] Update `.env.example` if new config needed
- [ ] Update API documentation

## Test Requirements

- **Unit tests required** for all new code
- **Integration test required** for database schema changes
- **API test required** for new endpoints
- Minimum 80% coverage per service

## Definition of Done

- [ ] Code compiles and passes all tests
- [ ] No new linting errors
- [ ] API documentation updated (if applicable)
- [ ] Database migration included (if schema changed)
- [ ] `.env.example` updated (if new env vars)
- [ ] No hardcoded secrets or credentials
- [ ] PR reviewed and approved
