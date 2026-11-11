# BhojanGo local development. Needs Docker (Desktop or Engine with Compose v2)
# and GNU make. Works on macOS/Linux, WSL2, and Windows Git Bash (install make
# with `winget install ezwinports.make`). See README, "Run it locally".
#
#   make dev     build and start everything (profile "all"), run migrations, seed
#   make seed    (re)load the Hyderabad + Boise seed data; safe to run again
#   make test    backend pytest + JS lint/typecheck/test, inside Docker
#   make ci      everything GitHub CI runs (the merge gate), inside Docker
#   make down    stop everything (keeps data)
#   make reset   wipe all data volumes, then `make dev` again
#
# Ports in use? Override them, e.g.  POSTGRES_PORT=15432 REDIS_PORT=16379 make dev

COMPOSE := docker compose
PROFILE ?= all

.PHONY: help dev up seed test test-backend test-js ci ci-migrations ci-docker ci-terraform down reset logs ps

help:
	@sed -n '1,15p' Makefile

dev: up seed
	@echo ""
	@echo "BhojanGo is running:"
	@echo "  core_api   http://localhost:$${CORE_API_PORT:-8001}/docs"
	@echo "  realtime   http://localhost:$${REALTIME_PORT:-8004}/docs"
	@echo "  worker     http://localhost:$${WORKER_PORT:-8006}/docs"
	@echo "  web        http://localhost:$${WEB_PORT:-3000}"
	@echo "  admin      http://localhost:$${ADMIN_PORT:-3001}"
	@echo "Stop with 'make down'; wipe data with 'make reset'."

# --wait blocks until every service is healthy (core-api only turns healthy
# after `alembic upgrade head` has run in its container).
up:
	$(COMPOSE) --profile $(PROFILE) up -d --build --wait

seed:
	$(COMPOSE) --profile backend up -d --wait core-api
	$(COMPOSE) exec -T core-api python /srv/tools/seed/seed.py

test: test-backend test-js

test-backend:
	docker build -f infra/docker/test.Dockerfile --target backend-test --no-cache-filter backend-test --progress=plain .

test-js:
	docker build -f infra/docker/test.Dockerfile --target js-test --no-cache-filter js-test --progress=plain .

# Everything .github/workflows runs on a PR and on dev: JS lint/typecheck/test,
# backend pytest, migrations up/down/up + alembic check + seed + integration
# tests, the three service images, and terraform fmt/validate. Passing
# `make ci` is the merge gate.
ci: test-backend test-js ci-migrations ci-docker ci-terraform
	@echo ""
	@echo "make ci: all checks passed"

CI_COMPOSE := $(COMPOSE) -f infra/docker/ci.compose.yaml
ci-migrations:
	$(CI_COMPOSE) build migrations
	$(CI_COMPOSE) run --rm migrations; status=$$?; $(CI_COMPOSE) down -v --remove-orphans; exit $$status

ci-docker:
	for svc in core_api realtime worker; do docker build -q -f backend/$$svc/Dockerfile -t bhojango-$$svc:ci backend || exit 1; done

# Providers go to a cache inside the container, not the bind mount (which
# fails on OneDrive/Windows paths) and never into the repo.
TF := docker run --rm -v "$(CURDIR)/infra/terraform:/tf" -w /tf -e TF_DATA_DIR=/tmp/tfdata --entrypoint sh hashicorp/terraform:1.17.2 -c
ci-terraform:
	MSYS_NO_PATHCONV=1 $(TF) 'terraform fmt -recursive -check -diff && for d in envs/staging envs/prod bootstrap; do echo "validate $$d"; (cd $$d && rm -rf /tmp/tfdata && terraform init -backend=false -input=false -lockfile=readonly >/dev/null && terraform validate) || exit 1; done'

down:
	$(COMPOSE) --profile all down

reset:
	$(COMPOSE) --profile all down -v
	$(MAKE) dev

logs:
	$(COMPOSE) --profile all logs -f --tail=100

ps:
	$(COMPOSE) --profile all ps
