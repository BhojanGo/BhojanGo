# Service Boot Matrix — SPR-01 Evidence

**Date:** 2026-06-15
**Environment:** macOS (darwin), native processes
**Docker Status:** Docker not available on this system

## Service Boot Status

| Service | Port | Status | Uptime | First Error |
|---------|------|--------|--------|-------------|
| user-svc | 8001 | BOOTED | 83921.7s (~23.3h) | None |
| restaurant-svc | 8002 | BOOTED | 83764.5s (~23.3h) | None |
| order-svc | 8003 | BOOTED | 87065.5s (~24.2h) | None |
| delivery-svc | 8004 | BOOTED | 87040.3s (~24.2h) | None |
| payment-svc | 8005 | BOOTED | 86035.1s (~23.9h) | None |
| notification-svc | 8006 | BOOTED | 84814.7s (~23.6h) | None |
| batch-engine | 8007 | BOOTED | 76406.2s (~21.2h) | None |
| web | 3000 | BOOTED | N/A | None (no /health endpoint) |

## Infrastructure Services

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| postgres | 5432 | RUNNING | Native macOS install, PID 52095 |
| redis | 6379 | RUNNING | Native macOS install, PID 52348 |
| opensearch | 9200 | NOT RUNNING | Docker not available |
| pgbouncer | 6432 | NOT RUNNING | Depends on docker-compose |
| localstack | 4566 | NOT RUNNING | Docker not available |
| kong | 8080/8081 | NOT RUNNING | Docker not available |

## Environment Files Status

| Service | .env Present | DATABASE_URL | JWT_SECRET | REDIS_URL |
|---------|--------------|--------------|------------|-----------|
| user-svc | Yes | Yes | Yes | Yes |
| restaurant-svc | Yes | Yes | Yes | Yes |
| order-svc | Yes | Yes | Yes | Yes |
| delivery-svc | No DATABASE_URL | No | Yes | Yes |
| payment-svc | Yes | Yes | Yes | Yes |
| notification-svc | Yes | Yes | Yes | Yes |

## Notes

- All Python services (user-svc through notification-svc) and batch-engine are running natively via poetry/virtualenv
- web (Next.js) is running on port 3000
- Docker unavailable — cannot start opensearch, pgbouncer, localstack, kong
- delivery-svc has no DATABASE_URL in .env (uses DynamoDB instead, which is also unavailable)

## Blockers

1. **Docker unavailable**: Cannot start opensearch, pgbouncer, localstack, kong
2. **delivery-svc**: Missing DATABASE_URL in .env (noted but uses DynamoDB, may be intentional)