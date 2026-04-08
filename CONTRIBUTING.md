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

# 4. Install backend dependencies (per service)
cd services/user-svc && poetry install
cd services/restaurant-svc && poetry install
cd services/order-svc && poetry install

# 5. Run database migrations
cd services/user-svc && alembic upgrade head
cd services/restaurant-svc && alembic upgrade head
cd services/order-svc && alembic upgrade head

# 6. Seed test data
bash scripts/seed/run_all.sh --env local

# 7. Start development servers
pnpm dev           # Frontend apps (web:3000, admin:3001)
# In separate terminals:
cd services/user-svc && uvicorn app.main:app --reload --port 8001
cd services/restaurant-svc && uvicorn app.main:app --reload --port 8002
cd services/order-svc && uvicorn app.main:app --reload --port 8003
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
feat(order-svc): add idempotency key support for order creation
fix(user-svc): prevent timing attack in login endpoint
chore: update Python dependencies across all services
docs: add operations runbook
```

**Types:** `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`, `perf`, `ci`

## Pull Request Process

1. Create a feature branch from `dev`
2. Make your changes with clear, atomic commits
3. Ensure all tests pass: `pytest` (backend), `pnpm test` (frontend)
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

## Adding a New Microservice

- [ ] Create `services/<name>/` with standard structure
- [ ] Add FastAPI app with health check, CORS, rate limiting
- [ ] Add SQLAlchemy models and Alembic migration
- [ ] Add Dockerfile and .dockerignore
- [ ] Add pyproject.toml with dependencies
- [ ] Add route in `infra/kong/kong.yml`
- [ ] Add to `docker-compose.yml`
- [ ] Add CI job in `.github/workflows/ci.yml`
- [ ] Add Terraform ECS task definition

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
