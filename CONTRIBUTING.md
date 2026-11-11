# Contributing to BhojanGo

Thank you for contributing to BhojanGo! This guide helps you get set up and follow our development practices.

## Prerequisites

- **Node.js** 20+ and **pnpm** 9+
- **Python** 3.11+ and **Poetry**
- **Docker** and **Docker Compose**
- **Git** with conventional commit support

## Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/deeptricsllc/BhojanGo.git
cd BhojanGo

# 2. Start infrastructure
docker compose up -d

# 3. Install frontend dependencies
pnpm install

# 4. Install backend dependencies (one uv project for all of backend/)
cd backend && uv sync && cd ..

# 5. Run database migrations (one history)
cd backend && uv run alembic upgrade head && cd ..

# 6. Seed test data
bash tools/seed/run_all.sh --env local

# 7. Start development servers
pnpm dev           # Frontend apps (web:3000, admin:3001)
# In separate terminals:
cd backend && uv run uvicorn core_api.main:app --reload --port 8001
cd backend && uv run uvicorn app.main:app --app-dir realtime --reload --port 8004
cd backend && uv run uvicorn app.main:app --app-dir worker --reload --port 8006
pnpm --filter @bhojango/customer start   # or @bhojango/rider
```

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
3. Ensure all tests pass: `uv run pytest core_api|realtime|worker` in `backend/`, `pnpm turbo test lint typecheck`
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
- [ ] Add a Kong route in `infra/docker/kong/kong.yml` (until P4 removes Kong)

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
