# Health Check Matrix — SPR-01 Evidence

**Date:** 2026-06-15
**Test:** `GET /health` on each service

## Health Endpoint Results

| Service | Port | Status | HTTP Code | Latency (s) | Healthy | Details |
|---------|------|--------|-----------|-------------|---------|---------|
| user-svc | 8001 | 200 OK | 200 | 0.0125 | YES | redis: ok, database: ok |
| restaurant-svc | 8002 | 200 OK | 200 | 0.0156 | YES | redis: ok, database: ok |
| order-svc | 8003 | 200 OK | 200 | 0.0179 | YES | redis: ok, database: ok |
| delivery-svc | 8004 | 200 OK | 200 | 0.0036 | YES | redis: ok (no db check) |
| payment-svc | 8005 | 200 OK | 200 | 0.0086 | YES | database: ok |
| notification-svc | 8006 | 200 OK | 200 | 0.0083 | YES | database: ok, sqs_configured: not_configured |
| batch-engine | 8007 | 200 OK | 200 | 0.0034 | YES | database: ok, engine: running |
| web | 3000 | N/A | 404 | N/A | N/A | No /health endpoint, returns Next.js 404 |

## Latency Summary

| Service | Latency (ms) |
|---------|--------------|
| batch-engine | 3.4ms |
| delivery-svc | 3.6ms |
| notification-svc | 8.3ms |
| payment-svc | 8.6ms |
| user-svc | 12.5ms |
| restaurant-svc | 15.6ms |
| order-svc | 17.9ms |

## Observations

1. All Python services return healthy status with 200 OK
2. All latency values are under 20ms — excellent performance
3. web (port 3000) has no /health endpoint — returns 404 on root request
4. notification-svc reports `sqs_configured: not_configured` — expected in dev without SQS
5. delivery-svc has no database check in health — uses DynamoDB instead

## Sample Health Response (user-svc)

```json
{
  "status": "healthy",
  "service": "user-svc",
  "version": "0.1.0",
  "uptime_seconds": 83921.7,
  "checks": {
    "redis": "ok",
    "database": "ok"
  },
  "timestamp": "2026-06-14T19:15:37.592759Z"
}
```

## Sample Health Response (batch-engine)

```json
{
  "status": "healthy",
  "service": "batch-engine",
  "version": "0.1.0",
  "uptime": 76406.173066958,
  "checks": {
    "database": "ok",
    "engine": "running"
  },
  "config": {
    "batchCycleSeconds": 30,
    "maxOrdersPerBatch": 3,
    "maxPickupRadiusKm": 1.5,
    "maxDetourMinutes": 8
  },
  "timestamp": "2026-06-14T19:15:37.776Z"
}
```