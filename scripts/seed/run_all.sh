#!/bin/bash
set -e

ENV="${1:---env}"
ENV_VAL="${2:-local}"

# Accept --env local or just local
if [ "$ENV" = "--env" ]; then
    TARGET_ENV="$ENV_VAL"
else
    TARGET_ENV="$ENV"
fi

echo "=== BhojanGo Seed Data Loader ==="
echo "Target environment: $TARGET_ENV"
echo ""

# Database connection
if [ "$TARGET_ENV" = "local" ]; then
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    DB_USER="${DB_USER:-bhojango}"
    DB_PASS="${DB_PASS:-bhojango_dev}"
    DB_NAME="${DB_NAME:-bhojango}"
elif [ "$TARGET_ENV" = "staging" ]; then
    if [ -z "$DB_HOST" ]; then
        echo "ERROR: DB_HOST must be set for staging environment"
        exit 1
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PGPASSWORD="$DB_PASS"

echo "[1/3] Seeding users..."
python3 "$SCRIPT_DIR/seed_users.py" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q
echo "  Users seeded successfully"

echo "[2/3] Seeding restaurants and menus..."
python3 "$SCRIPT_DIR/seed_restaurants.py" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q
echo "  Restaurants and menus seeded successfully"

echo "[3/3] Seeding orders..."
python3 "$SCRIPT_DIR/seed_orders.py" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q
echo "  Orders seeded successfully"

echo ""
echo "=== Seed data loaded successfully ==="
echo ""
echo "Test credentials:"
echo "  customer1@test.com / Test1234! (customer, India)"
echo "  customer2@test.com / Test1234! (customer, USA)"
echo "  owner1@test.com    / Test1234! (restaurant owner, India)"
echo "  owner2@test.com    / Test1234! (restaurant owner, USA)"
echo "  driver1@test.com   / Test1234! (driver, India)"
echo "  driver2@test.com   / Test1234! (driver, USA)"
echo "  admin@bhojango.com / Admin1234! (super admin)"
