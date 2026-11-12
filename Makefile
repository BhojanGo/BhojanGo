# BhojanGo local development. Needs Docker (Desktop or Engine with Compose v2)
# and GNU make. Works on macOS/Linux, WSL2, and Windows Git Bash (install make
# with `winget install ezwinports.make`). See README, "Run it locally".
#
#   make dev     build and start everything (profile "all"), run migrations, seed
#   make observe make dev + Grafana, Prometheus, Alertmanager, Loki, Tempo (P23)
#   make seed    (re)load the Hyderabad + Boise seed data; safe to run again
#   make test    backend pytest + JS lint/typecheck/test, inside Docker
#   make ci      everything GitHub CI runs (the merge gate), inside Docker
#   make down    stop everything (keeps data)
#   make reset   wipe all data volumes, then `make dev` again
#
# Ports in use? Override them, e.g.  POSTGRES_PORT=15432 REDIS_PORT=16379 make dev

COMPOSE := docker compose
PROFILE ?= all
# Git Bash on Windows rewrites /srv/... arguments into Windows paths; stop it.
export MSYS_NO_PATHCONV := 1

.PHONY: help dev observe up seed test test-backend test-js ci ci-migrations ci-docker ci-e2e ci-terraform apk down reset logs ps

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
	@echo "  mailpit    http://localhost:$${MAILPIT_PORT:-8025}  (every email the backend sends)"
	@echo "OTP codes, SMS and push: printed in the worker log (make logs). Seed phones use OTP 123456."
	@echo "Payments are faked: they succeed after 2 s; test card pm_card_chargeDeclined fails."
	@echo "Stop with 'make down'; wipe data with 'make reset'."

# --wait blocks until every service is healthy (core-api only turns healthy
# after `alembic upgrade head` has run in its container).
up:
	$(COMPOSE) --profile $(PROFILE) up -d --build --wait

# P23: `make dev` plus local monitoring (OpenTelemetry to Tempo, Prometheus and
# Alertmanager to the admin console, Loki, Grafana). Zero spend; see
# docs/runbooks/observe.md.
OBSERVE := $(COMPOSE) -f infra/docker/compose.yaml -f infra/docker/observe.compose.yaml
observe:
	$(OBSERVE) --profile all --profile observe up -d --build --wait
	$(OBSERVE) exec -T core-api python /srv/tools/seed/seed.py >/dev/null
	@echo ""
	@echo "Monitoring is running (on top of make dev):"
	@echo "  grafana       http://localhost:$${GRAFANA_PORT:-3300}  (Pilot KPIs, Service health; admin/admin)"
	@echo "  prometheus    http://localhost:$${PROMETHEUS_PORT:-9090}/alerts"
	@echo "  alertmanager  http://localhost:$${ALERTMANAGER_PORT:-9093}"
	@echo "Firing alerts also show in the admin console (Operations) and in the logs."

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
# tests, the three service images, the Phase 1 gate (G1) end to end on a
# throwaway stack, and terraform fmt/validate. Passing `make ci` is the merge gate.
ci: test-backend test-js ci-migrations ci-docker ci-e2e ci-terraform
	@echo ""
	@echo "make ci: all checks passed"

CI_COMPOSE := $(COMPOSE) -f infra/docker/ci.compose.yaml
ci-migrations:
	$(CI_COMPOSE) build migrations
	$(CI_COMPOSE) run --rm migrations; status=$$?; $(CI_COMPOSE) down -v --remove-orphans; exit $$status

# G1: the whole backend as its own compose project (no host ports), seeded; the
# runner orders, pays, dispatches, delivers and checks payouts and messages
# over HTTP (backend/e2e). Always torn down with its volumes.
E2E_COMPOSE := $(COMPOSE) -p bhojango-g1 -f infra/docker/compose.yaml -f infra/docker/e2e.compose.yaml
ci-e2e:
	$(E2E_COMPOSE) --profile backend up -d --build --wait || { $(E2E_COMPOSE) --profile backend logs --tail 50; $(E2E_COMPOSE) --profile e2e --profile backend down -v --remove-orphans; exit 1; }
	$(E2E_COMPOSE) exec -T core-api python /srv/tools/seed/seed.py >/dev/null && 	$(E2E_COMPOSE) --profile e2e run --rm --build g1; status=$$?; 	[ $$status -eq 0 ] || $(E2E_COMPOSE) --profile backend logs --tail 80 realtime worker; 	$(E2E_COMPOSE) --profile e2e --profile backend down -v --remove-orphans; exit $$status

# Android debug APK for an Expo app, built in Linux (Windows path limits and
# OneDrive locks break React Native's CMake builds). Output: .apk/<app>-debug.apk
#   make apk APP=customer   then: adb -s emulator-5554 install -r .apk/customer-debug.apk
APP ?= customer
apk:
	docker run --rm -v "$(CURDIR):/src:ro" -v "$(CURDIR)/.apk:/out" -v bhojango-gradle:/root/.gradle 	  -v bhojango-pnpm-store:/pnpm-store reactnativecommunity/react-native-android:v22.0 sh /src/tools/android/build-apk.sh $(APP)

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
