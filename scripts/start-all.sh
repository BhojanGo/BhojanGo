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
> "$PIDS_FILE"

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

# ── Check port availability ────────────────────────────────
check_port() {
  local port=$1
  if lsof -i ":$port" > /dev/null 2>&1; then
    return 1  # port in use
  fi
  return 0   # port free
}

wait_for_port() {
  local port=$1
  local svc=$2
  local max_wait=${3:-60}
  local elapsed=0
  while ! lsof -i ":$port" > /dev/null 2>&1; do
    sleep 1
    elapsed=$((elapsed + 1))
    if (( elapsed >= max_wait )); then
      log_error "$svc did not start on port $port within ${max_wait}s"
      return 1
    fi
  done
  log_ok "$svc is listening on port $port"
  return 0
}

# ── Stop all ───────────────────────────────────────────────
stop-all() {
  log_info "Stopping all services..."

  # Kill backend PIDs
  if [[ -f "$PIDS_FILE" ]]; then
    while IFS=: read -r name pid; do
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        log_info "Stopping $name (PID $pid)"
        kill "$pid" 2>/dev/null || true
      fi
    done < "$PIDS_FILE"
  fi

  # Stop docker-compose services
  log_info "Stopping docker-compose services..."
  docker-compose down 2>/dev/null || true

  # Clean up PID file
  rm -f "$PIDS_FILE"

  log_ok "All services stopped"
  exit 0
}

# ── Trap for clean shutdown ────────────────────────────────
trap 'stop-all' INT TERM

# ══════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════

log_info "Starting BhojanGo services..."

# ── 1. Docker Compose services ─────────────────────────────
log_info "Starting Docker Compose services..."
docker-compose up --detach

# ── 2. Wait for Postgres ───────────────────────────────────
log_info "Waiting for Postgres to be healthy..."
max_wait=60
elapsed=0
while true; do
  if docker exec "$(docker-compose ps -q postgres)" pg_isready -U bhojango > /dev/null 2>&1; then
    log_ok "Postgres is ready"
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
  if (( elapsed >= max_wait )); then
    log_error "Postgres did not become healthy within ${max_wait}s"
    exit 1
  fi
done

# ── 3. Start Python backend services ───────────────────────
for entry in "${PYTHON_SVCS[@]}"; do
  svc_name="${entry%%:*}"
  svc_port="${entry#*:}"
  svc_dir="$PROJECT_ROOT/services/$svc_name"

  if ! check_port "$svc_port"; then
    log_warn "$svc_name port $svc_port already in use — skipping"
    continue
  fi

  if [[ ! -d "$svc_dir/.venv" ]]; then
    log_warn "$svc_name has no .venv — skipping"
    continue
  fi

  log_info "Starting $svc_name on port $svc_port..."
  cd "$svc_dir"
  poetry run uvicorn app.main:app --port "$svc_port" --reload \
    >> "$PROJECT_ROOT/logs/${svc_name}.log" 2>&1 &
  svc_pid=$!
  echo "$svc_name:$svc_pid" >> "$PIDS_FILE"
  cd "$PROJECT_ROOT"
  log_ok "$svc_name started (PID $svc_pid)"
done

# ── 4. Start batch-engine ──────────────────────────────────
batch_dir="$PROJECT_ROOT/services/batch-engine"
if ! check_port 8007; then
  log_warn "batch-engine port 8007 already in use — skipping"
elif [[ ! -d "$batch_dir/node_modules" ]]; then
  log_warn "batch-engine has no node_modules — skipping"
else
  log_info "Starting batch-engine on port 8007..."
  cd "$batch_dir"
  # Check if DATABASE_URL is set, warn if not
  if [[ -z "$DATABASE_URL" ]]; then
    log_warn "DATABASE_URL not set — batch-engine may fail to start"
  fi
  DATABASE_URL="${DATABASE_URL:-postgresql://bhojango:bhojango_dev@localhost:5432/bhojango}" \
    npm run dev >> "$PROJECT_ROOT/logs/batch-engine.log" 2>&1 &
  svc_pid=$!
  echo "batch-engine:$svc_pid" >> "$PIDS_FILE"
  cd "$PROJECT_ROOT"
  log_ok "batch-engine started (PID $svc_pid)"
fi

# ── 5. Start web (Next.js) ─────────────────────────────────
# Only start if SKIP_WEB is not set
if [[ "${SKIP_WEB:-}" != "1" ]]; then
  web_dir="$PROJECT_ROOT/services/web"
  if ! check_port 3000; then
    log_warn "web port 3000 already in use — skipping"
  elif [[ ! -f "$web_dir/package.json" ]]; then
    log_warn "web has no package.json — skipping"
  else
    log_info "Starting web on port 3000..."
    cd "$web_dir"
    pnpm --filter web dev >> "$PROJECT_ROOT/logs/web.log" 2>&1 &
    svc_pid=$!
    echo "web:$svc_pid" >> "$PIDS_FILE"
    cd "$PROJECT_ROOT"
    log_ok "web started (PID $svc_pid)"
  fi
else
  log_info "SKIP_WEB=1 — skipping web"
fi

# ── 6. Verify services are listening ───────────────────────
log_info "Verifying services are listening..."
sleep 5  # Give services a moment to start

all_ok=true
for entry in "${PYTHON_SVCS[@]}"; do
  svc_name="${entry%%:*}"
  svc_port="${entry#*:}"
  if ! check_port "$svc_port"; then
    log_ok "$svc_name is up"
  else
    log_warn "$svc_name may not be up yet (port $svc_port not listening)"
    all_ok=false
  fi
done

if ! check_port 8007; then
  log_ok "batch-engine is up"
else
  log_warn "batch-engine may not be up yet (port 8007 not listening)"
fi

if [[ "${SKIP_WEB:-}" != "1" ]] && ! check_port 3000; then
  log_ok "web is up"
elif [[ "${SKIP_WEB:-}" != "1" ]]; then
  log_warn "web may not be up yet (port 3000 not listening)"
fi

# ── Summary ────────────────────────────────────────────────
echo ""
log_info "PIDs saved to: $PIDS_FILE"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
log_ok "All services started!"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "To stop all services: ./scripts/start-all.sh stop-all"
echo ""