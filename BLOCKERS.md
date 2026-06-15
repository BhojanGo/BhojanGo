# BhojanGo Blockers — SPR-01

**Document Date:** 2026-06-15
**Status:** Active blockers preventing full infrastructure startup

---

## BLOCKER-001: Docker Not Available

**Severity:** High
**Category:** Infrastructure
**Status:** Open

### Description
Docker and docker-compose are not available on this macOS system. This prevents starting Docker-based infrastructure services.

### Impact
- Cannot start **opensearch** (port 9200) — used for restaurant search/recommendations
- Cannot start **pgbouncer** (port 6432) — connection pooler
- Cannot start **localstack** (port 4566) — AWS SQS/SNS/S3 emulation
- Cannot start **kong** (port 8080/8081) — API gateway

### Reproduction Steps
```bash
# 1. Check Docker availability
docker --version
# Output: /bin/bash: docker: command not found

docker compose version
# Output: /bin/bash: docker-compose: command not found

# 2. Attempt docker-compose up
docker-compose up --detach postgres
# Output: /bin/bash: docker-compose: command not found
```

### Workaround
Services run natively without Docker. PostgreSQL and Redis are running via native macOS installs.

### Resolution
Install Docker Desktop for Mac or ensure Docker is in PATH.

---

## BLOCKER-002: delivery-svc Missing DATABASE_URL

**Severity:** Low
**Category:** Configuration
**Status:** Open (may be intentional)

### Description
The `delivery-svc/.env` file does not contain a `DATABASE_URL` variable.

### Reproduction Steps
```bash
cat services/delivery-svc/.env | grep DATABASE_URL
# Output: (empty)
```

### Analysis
- delivery-svc uses DynamoDB for delivery tracking, not PostgreSQL
- Health check shows delivery-svc as healthy with only Redis check
- This may be intentional design — delivery-svc is DynamoDB-first

### Impact
- None observed — service is healthy
- If PostgreSQL is needed for delivery-svc in future, this will block

### Resolution
If intentional, add comment `# Uses DynamoDB, not PostgreSQL` to .env
If not intentional, add: `DATABASE_URL=postgresql+asyncpg://bhojango:bhojango_dev@localhost:5432/bhojango`

---

## BLOCKER-003: reviews Table Empty

**Severity:** Low
**Category:** Seed Data
**Status:** Open

### Description
The `reviews` table in the database has 0 records. No seed data was loaded for reviews.

### Reproduction Steps
```sql
psql -h localhost -U bhojango -d bhojango -c "SELECT COUNT(*) FROM reviews;"

-- Output:
 count
-------
     0
(1 row)
```

### Impact
- Cannot test review-related features (display reviews, submit reviews, rating aggregation)
- restaurant-svc health is unaffected

### Resolution
Run the seed script for reviews:
```bash
# Check if seed script exists for reviews
ls scripts/seed/
# If not, create seed data or update comprehensive_seed.py
```

---

## BLOCKER-004: web Service Has No /health Endpoint

**Severity:** Low
**Category:** Monitoring
**Status:** Open

### Description
The Next.js web service on port 3000 does not expose a `/health` endpoint. Requests to `/health` return 404.

### Reproduction Steps
```bash
curl -s -w "\n%{http_code}" http://localhost:3000/health
# Returns: 404 (Next.js 404 page)
```

### Impact
- Cannot easily monitor web service health via HTTP endpoint
- Port check confirms service is running but not application-level health

### Resolution
Add a Next.js API route at `apps/web/src/app/api/health/route.ts`:
```typescript
export async function GET() {
  return Response.json({ status: 'healthy', service: 'web' })
}
```

---

## Summary Table

| Blocker | Severity | Service | Docker Required | Status |
|---------|----------|---------|-----------------|--------|
| BLOCKER-001 | HIGH | opensearch, pgbouncer, localstack, kong | Yes | OPEN |
| BLOCKER-002 | LOW | delivery-svc | No | OPEN (may be intentional) |
| BLOCKER-003 | LOW | reviews | No | OPEN |
| BLOCKER-004 | LOW | web | No | OPEN |

---

## Resolved Issues

None in this session.

---

*Document created as part of SPR-01 Service Boot and Health Evidence Collection*