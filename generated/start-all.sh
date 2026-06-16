#!/bin/bash
# BhojanGo — Start all backend services + frontend (macOS)
# Opens a new Terminal window/tab per service so you can watch logs.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "============================================"
echo "  BhojanGo — Starting All Services"
echo "  Project: $PROJECT_DIR"
echo "============================================"
echo ""

# ── PostgreSQL & Redis pre-flight ──
echo "Checking PostgreSQL..."
if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    echo "  ⚠️  PostgreSQL not running. Start it first:  brew services start postgresql@16"
    exit 1
fi
echo "  ✅ PostgreSQL OK"

echo "Checking Redis..."
if ! redis-cli -h localhost -p 6379 ping >/dev/null 2>&1; then
    echo "  ⚠️  Redis not running. Start it first:  brew services start redis"
    exit 1
fi
echo "  ✅ Redis OK"
echo ""

# ── Helper ──
open_tab() {
    local title="$1"
    local work_dir="$2"
    local cmd="$3"
    osascript <<EOF
tell application "Terminal"
    activate
    tell application "System Events" to tell process "Terminal" to keystroke "t" using command down
    do script "cd '$work_dir' && echo '--- $title ---' && $cmd" in front window
end tell
EOF
    sleep 0.8
}

# ── Backend services ──
open_tab "user-svc (8001)"        "$PROJECT_DIR/services/user-svc"        "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001"
open_tab "restaurant-svc (8002)"  "$PROJECT_DIR/services/restaurant-svc"  "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8002"
open_tab "order-svc (8003)"       "$PROJECT_DIR/services/order-svc"       "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8003"
open_tab "delivery-svc (8004)"    "$PROJECT_DIR/services/delivery-svc"    "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8004"
open_tab "payment-svc (8005)"     "$PROJECT_DIR/services/payment-svc"     "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8005"
open_tab "notification-svc (8006)" "$PROJECT_DIR/services/notification-svc" "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8006"
open_tab "batch-engine (8007)"    "$PROJECT_DIR/services/batch-engine"    "npx tsx src/main.ts"

# ── Frontend ──
open_tab "frontend-web (3000)"    "$PROJECT_DIR/apps/web"                  "pnpm dev"

echo ""
echo "============================================"
echo "  All services launching in Terminal tabs!"
echo "============================================"
echo ""
echo "Endpoints:"
echo "  User API        http://localhost:8001"
echo "  Restaurant API  http://localhost:8002"
echo "  Order API       http://localhost:8003"
echo "  Delivery API    http://localhost:8004"
echo "  Payment API     http://localhost:8005"
echo "  Notification API http://localhost:8006"
echo "  Batch Engine    http://localhost:8007"
echo "  Frontend Web    http://localhost:3000"
echo ""
echo "Test logins:"
echo "  customer1@test.com / Test1234!  (customer)"
echo "  customer2@test.com / Test1234!  (customer)"
echo "  owner1@test.com    / Test1234!  (restaurant owner)"
echo "  owner2@test.com    / Test1234!  (restaurant owner)"
echo "  driver1@test.com   / Test1234!  (driver)"
echo "  driver2@test.com   / Test1234!  (driver)"
echo "  admin@bhojango.com / Admin1234! (super admin)"
echo "  rr_admin@bhojango.com / Arr@Admin1 (admin)"
echo ""
echo "Swagger docs:"
echo "  http://localhost:8001/docs"
echo "  http://localhost:8002/docs"
echo "  http://localhost:8003/docs"
echo ""
