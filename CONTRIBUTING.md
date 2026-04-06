# Contributing to BhojanGo

## Branch Strategy

We use **trunk-based development** with short-lived feature branches.

```
main                 ← production (auto-deploys to ECS)
  └── feature/xxx    ← your work (1-3 days max)
  └── fix/xxx        ← bug fixes
  └── hotfix/xxx     ← urgent prod fixes (cherry-picked)
```

### Branch Naming

```
feature/BG-123-add-promo-codes
fix/BG-456-cart-total-rounding
hotfix/BG-789-payment-webhook-crash
chore/update-dependencies
```

## Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout main && git pull
   git checkout -b feature/BG-123-description
   ```

2. **Make changes** — keep commits small and focused.

3. **Run checks locally** before pushing:
   ```bash
   # Frontend
   pnpm turbo lint typecheck

   # Backend (per service)
   cd services/user-svc
   pytest tests/ -v --cov=app --cov-fail-under=80
   ```

4. **Push and open a PR** against `main`.

5. **PR checks must pass** — the `pr-checks.yml` workflow runs:
   - Frontend: lint + typecheck
   - Backend: pytest per changed service
   - Terraform: `fmt -check` + `validate` (if infra changed)
   - Docker: build check (no push)

6. **Get at least 1 review** then merge via squash-merge.

## Pull Request Guidelines

### Title Format

```
[BG-123] Add promo code support to checkout
```

### Description Template

```markdown
## Summary
- What changed and why

## Test Plan
- [ ] Unit tests added/updated
- [ ] Manual testing steps
- [ ] Edge cases considered

## Screenshots (if UI changes)
```

### PR Rules

- Keep PRs under 400 lines of diff when possible
- One logical change per PR
- Update tests for any behavior change
- No `TODO` comments in critical paths — open a ticket instead
- All environment variables documented in `.env.example`

## Commit Messages

```
feat: add promo code validation to order-svc
fix: handle null delivery address in checkout
refactor: extract payment gateway interface
test: add wallet transaction edge cases
docs: update API endpoint table in README
chore: bump FastAPI to 0.115
```

## Code Standards

### Python (Backend Services)

- **Formatter**: black (line length 120)
- **Linter**: ruff
- **Type hints**: required on all public functions
- **Models**: Pydantic v2 for request/response schemas
- **ORM**: async SQLAlchemy 2.0 style
- **Logging**: structlog (JSON in production)
- **Tests**: pytest + pytest-asyncio, minimum 80% coverage

### TypeScript (Frontend Apps)

- **Formatter**: Prettier (via `packages/config`)
- **Linter**: ESLint (via `packages/config`)
- **Components**: functional components with TypeScript props
- **Styling**: Tailwind CSS (web), NativeWind (mobile)
- **State**: Zustand for client state, React Query for server state

### General

- No hardcoded secrets — use environment variables
- No `any` types in TypeScript
- No `# type: ignore` without a comment explaining why
- All API endpoints must have Pydantic input validation
- All database operations must be async

## Database Migrations

Each service with PostgreSQL models uses Alembic:

```bash
cd services/user-svc

# Create a new migration
alembic revision --autogenerate -m "add loyalty_tier column"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

**Rules:**
- Never edit a migration that has been merged to `main`
- Always test `upgrade` + `downgrade` locally
- Add data migrations in separate files from schema migrations

## Adding a New Service

1. Copy an existing service as a template (e.g., `user-svc`)
2. Update `docker-compose.yml` with the new service
3. Update `infra/kong/kong.yml` with routing rules
4. Add the service name to `infra/terraform/variables.tf` → `services` list
5. Create Dockerfile, alembic.ini, requirements.txt, tests/
6. Add to `.github/workflows/ci.yml` matrix

## Local Development Tips

```bash
# Start only infrastructure (no services)
docker compose up postgres redis opensearch localstack -d

# Run a single service locally (for debugging)
cd services/user-svc
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Access all APIs via Kong gateway
curl http://localhost:8888/api/v1/auth/login

# Direct access to a service (bypasses Kong)
curl http://localhost:8001/api/v1/auth/login

# View service logs
docker compose logs -f user-svc

# Reset database
docker compose down -v  # removes volumes
docker compose up -d
```

## Questions?

Open a GitHub issue or reach out to the team lead.
