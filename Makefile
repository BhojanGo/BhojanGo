# BhojanGo local development. Needs Docker (Desktop or Engine with Compose v2)
# and GNU make. Works on macOS/Linux, WSL2, and Windows Git Bash (install make
# with `winget install ezwinports.make`). See README, "Run it locally".
#
#   make dev     build and start everything (profile "all"), run migrations, seed
#   make seed    (re)load the Hyderabad + Boise seed data; safe to run again
#   make test    backend pytest + JS lint/typecheck/test, inside Docker
#   make down    stop everything (keeps data)
#   make reset   wipe all data volumes, then `make dev` again
#
# Ports in use? Override them, e.g.  POSTGRES_PORT=15432 REDIS_PORT=16379 make dev

COMPOSE := docker compose
PROFILE ?= all

.PHONY: help dev up seed test test-backend test-js down reset logs ps

help:
	@sed -n '1,14p' Makefile

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

down:
	$(COMPOSE) --profile all down

reset:
	$(COMPOSE) --profile all down -v
	$(MAKE) dev

logs:
	$(COMPOSE) --profile all logs -f --tail=100

ps:
	$(COMPOSE) --profile all ps
