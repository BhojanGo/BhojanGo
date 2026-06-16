#!/bin/bash
set -e

# ── Colour codes ───────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

# ── Project root ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Log helpers ────────────────────────────────────────────
log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── PIDs file ──────────────────────────────────────────────
PIDS_FILE="$SCRIPT_DIR/.service_pids"

# ── Service list ───────────────────────────────────────────
PYTHON_SVCS=(
  "user-svc:8001"
  "restaurant-svc:8002"
  "order-svc:8003"
  "delivery-svc:8004"
  "payment-svc:8005"
  "notification-svc:8006"
)
BATCH_ENGINE="batch-engine:8007"
WEB_SVC="web:3000"

# Docker-backed optional services (PR.09+ / optional before PR.08)
DOCKER_OPTIONAL_SVCS=("opensearch" "pgbouncer" "localstack" "kong")

# ── Docker detection ───────────────────────────────────────
DOCKER_CMD=""
if command -v docker-compose &>/dev/null; then
  DOCKER_CMD="docker-compose"
elif command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
  DOCKER_CMD="docker compose"
fi

# ── Check port availability ────────────────────────────────
check_port() {
  local port=$1
  if lsof -i ":$port" >/dev/null 2>&1; then
    return 1  # port in use
  fi
  return 0   # port free
}

# ── Health check helper ────────────────────────────────────
health_check() {
  local port=$1
  local path="${2:-/health}"
  local max_wait="${3:-15}"
  local elapsed=0
  while true; do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}${path}" 2>/dev/null | grep -q "^200$"; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
    if (( elapsed >= max_wait )); then
      return 1
    fi
  done
}

# ── Stop all ───────────────────────────────────────────────
stop_all() {
  log_info "Stopping all services..."

  # Kill backend PIDs
  if [[ -f "$PIDS_FILE" ]]; then
    while IFS=: read -r name pid; do
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        log_info "Stopping $name (PID $pid)"
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
      fi
    done < "$PIDS_FILE"
  fi

  # Stop docker-compose services
  if [[ -n "$DOCKER_CMD" ]]; then
    log_info "Stopping docker-compose services..."
    $DOCKER_CMD down 2>/dev/null || true
  fi

  # Clean up PID file
  rm -f "$PIDS_FILE"

  log_ok "All services stopped"
  exit 0
}

# ── Handle stop command ────────────────────────────────────
if [[ "${1:-}" == "stop" || "${1:-}" == "stop-all" ]]; then
  stop_all
fi

# ── Trap for clean shutdown ────────────────────────────────
trap 'stop_all' INT TERM

# ══════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════

log_info "Starting BhojanGo services..."

# ── Ensure logs dir exists ─────────────────────────────────
mkdir -p "$PROJECT_ROOT/logs"

# ── Clear stale PID file before this run ───────────────────
rm -f "$PIDS_FILE"

# ── Trackers ───────────────────────────────────────────────
declare -a STARTED=()
declare -a ALREADY_RUNNING=()
declare -a LAUNCHED_UNVERIFIED=()
declare -a SKIPPED=()
declare -a FAILED=()

# ── 1. Docker Compose services ─────────────────────────────
if [[ -z "$DOCKER_CMD" ]]; then
  log_warn "Docker not available — skipping docker-compose services"
  for svc in "${DOCKER_OPTIONAL_SVCS[@]}"; do
    SKIPPED+=("$svc:docker-missing")
  done
else
  log_info "Docker detected ($DOCKER_CMD) — starting compose services..."
  if $DOCKER_CMD up --detach postgres redis 2>/dev/null; then
    log_ok "postgres and redis compose services started"
    # Only track services we actually attempted; optional ones not validated yet
  else
    log_warn "docker-compose up failed — skipping docker services"
    for svc in "${DOCKER_OPTIONAL_SVCS[@]}"; do
      SKIPPED+=("$svc:docker-start-failed")
    done
  fi
fi

# ── 2. Wait for Postgres ───────────────────────────────────
log_info "Waiting for Postgres..."
max_wait=60
elapsed=0
postgres_ready=false

# Prefer docker check if docker is available and postgres container exists
if [[ -n "$DOCKER_CMD" ]] && $DOCKER_CMD ps -q postgres &>/dev/null; then
  while true; do
    if docker exec "$($DOCKER_CMD ps -q postgres)" pg_isready -U bhojango >/dev/null 2>&1; then
      postgres_ready=true
      break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    if (( elapsed >= max_wait )); then
      log_warn "Postgres container did not become healthy within ${max_wait}s"
      break
    fi
  done
fi

# Fallback: check native postgres
if [[ "$postgres_ready" != "true" ]]; then
  if command -v pg_isready &>/dev/null && pg_isready -h localhost -p 5432 -U bhojango >/dev/null 2>&1; then
    postgres_ready=true
  elif command -v psql &>/dev/null && psql -h localhost -p 5432 -U bhojango -d bhojango -c "SELECT 1" >/dev/null 2>&1; then
    postgres_ready=true
  fi
fi

if [[ "$postgres_ready" == "true" ]]; then
  log_ok "Postgres is ready"
else
  log_warn "Postgres not confirmed ready — continuing anyway (services may retry connections)"
fi

# ── 3. Start Python backend services ───────────────────────
for entry in "${PYTHON_SVCS[@]}"; do
  svc_name="${entry%%:*}"
  svc_port="${entry#*:}"
  svc_dir="$PROJECT_ROOT/services/$svc_name"

  if ! check_port "$svc_port"; then
    log_warn "$svc_name port $svc_port already in use — already running"
    ALREADY_RUNNING+=("$svc_name")
    continue
  fi

  if [[ ! -d "$svc_dir/.venv" ]]; then
    log_warn "$svc_name has no .venv — skipping"
    SKIPPED+=("$svc_name:no-venv")
    continue
  fi

  log_info "Starting $svc_name on port $svc_port..."
  cd "$svc_dir"
  if poetry run uvicorn app.main:app --port "$svc_port" --reload \
       >> "$PROJECT_ROOT/logs/${svc_name}.log" 2>&1 &
  then
    svc_pid=$!
    echo "$svc_name:$svc_pid" >> "$PIDS_FILE"
    cd "$PROJECT_ROOT"
    # Verify health endpoint before declaring started
    if health_check "$svc_port" "/health" 10; then
      log_ok "$svc_name started and healthy (PID $svc_pid)"
      STARTED+=("$svc_name")
    else
      log_warn "$svc_name launched but health check not confirmed"
      LAUNCHED_UNVERIFIED+=("$svc_name")
    fi
  else
    log_error "$svc_name failed to start"
    FAILED+=("$svc_name:start-failed")
    cd "$PROJECT_ROOT"
  fi
done

# ── 4. Start batch-engine ──────────────────────────────────
batch_dir="$PROJECT_ROOT/services/batch-engine"
if ! check_port 8007; then
  log_warn "batch-engine port 8007 already in use — already running"
  ALREADY_RUNNING+=("batch-engine")
elif [[ ! -d "$batch_dir/node_modules" ]]; then
  log_warn "batch-engine has no node_modules — skipping"
  SKIPPED+=("batch-engine:no-node_modules")
else
  log_info "Starting batch-engine on port 8007..."
  cd "$batch_dir"
  if DATABASE_URL="${DATABASE_URL:-postgresql://bhojango:bhojango_dev@localhost:5432/bhojango}" \
     npm run dev >> "$PROJECT_ROOT/logs/batch-engine.log" 2>&1 &
  then
    svc_pid=$!
    echo "batch-engine:$svc_pid" >> "$PIDS_FILE"
    cd "$PROJECT_ROOT"
    if health_check 8007 "/health" 10; then
      log_ok "batch-engine started and healthy (PID $svc_pid)"
      STARTED+=("batch-engine")
    else
      log_warn "batch-engine launched but health check not confirmed"
      LAUNCHED_UNVERIFIED+=("batch-engine")
    fi
  else
    log_error "batch-engine failed to start"
    FAILED+=("batch-engine:start-failed")
    cd "$PROJECT_ROOT"
  fi
fi

# ── 5. Start web (Next.js) ─────────────────────────────────
# Detect correct path: apps/web vs services/web
if [[ -f "$PROJECT_ROOT/apps/web/package.json" ]]; then
  web_dir="$PROJECT_ROOT/apps/web"
elif [[ -f "$PROJECT_ROOT/services/web/package.json" ]]; then
  web_dir="$PROJECT_ROOT/services/web"
else
  web_dir=""
fi

if [[ "${SKIP_WEB:-}" == "1" ]]; then
  log_info "SKIP_WEB=1 — skipping web"
  SKIPPED+=("web:SKIP_WEB")
elif [[ -z "$web_dir" ]]; then
  log_warn "web package.json not found in apps/web or services/web — skipping"
  SKIPPED+=("web:missing-package.json")
elif ! check_port 3000; then
  log_warn "web port 3000 already in use — already running"
  ALREADY_RUNNING+=("web")
else
  log_info "Starting web on port 3000..."
  cd "$web_dir"
  if pnpm --filter web dev >> "$PROJECT_ROOT/logs/web.log" 2>&1 &
  then
    svc_pid=$!
    echo "web:$svc_pid" >> "$PIDS_FILE"
    cd "$PROJECT_ROOT"
    # Web has no /health endpoint; report launched-unverified
    log_warn "web launched but no /health endpoint to verify (PID $svc_pid)"
    LAUNCHED_UNVERIFIED+=("web")
  else
    log_error "web failed to start"
    FAILED+=("web:start-failed")
    cd "$PROJECT_ROOT"
  fi
fi

# ── 6. Summary ─────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log_info "Startup summary"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

for s in "${ALREADY_RUNNING[@]}"; do
  log_ok "ALREADY RUNNING — $s"
done
for s in "${STARTED[@]}"; do
  log_ok "STARTED        — $s"
done
for s in "${LAUNCHED_UNVERIFIED[@]}"; do
  log_warn "LAUNCHED UNVERIFIED — $s"
done
for s in "${SKIPPED[@]}"; do
  log_warn "SKIPPED        — $s"
done
for s in "${FAILED[@]}"; do
  log_error "FAILED         — $s"
done

total_started=${#STARTED[@]}
total_already=${#ALREADY_RUNNING[@]}
total_unverified=${#LAUNCHED_UNVERIFIED[@]}
total_skipped=${#SKIPPED[@]}
total_failed=${#FAILED[@]}
total_required=${#PYTHON_SVCS[@]}
# batch-engine and web are also required-ish
total_required=$((total_required + 2))

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log_info "Total: $total_already already-running, $total_started started, $total_unverified launched-unverified, $total_skipped skipped, $total_failed failed"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Exit logic: success if no failures and all required services are either
# already running, started, or launched-unverified.
if [[ $total_failed -gt 0 ]]; then
  log_error "Some services failed to start. Check logs/ directory."
  exit_code=1
elif [[ $((total_already + total_started + total_unverified)) -ge $total_required ]]; then
  log_ok "All required services are accounted for."
  exit_code=0
else
  # Some required services were skipped (missing venv/node_modules/etc)
  log_warn "Some required services were skipped."
  exit_code=1
fi

echo "PIDs saved to: $PIDS_FILE"
echo "Logs: $PROJECT_ROOT/logs/"
echo "To stop all:  ./scripts/start-all.sh stop"
echo ""
exit $exit_code
