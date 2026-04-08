# BhojanGo Operations Runbook

## On-Call Setup

### PagerDuty Schedules
- **Primary on-call:** Weekly rotation, Mon 9AM → Mon 9AM
- **Escalation:** Primary → Secondary (15 min) → Engineering Lead (30 min)
- **Severity Levels:**
  - SEV1 (Critical): Platform down, payments failing — page immediately
  - SEV2 (High): Single service degraded — page during business hours
  - SEV3 (Medium): Non-critical bug — next business day

## Accessing Logs

### CloudWatch Logs Insights

**Find errors in a service (last 1 hour):**
```
fields @timestamp, @message
| filter @message like /error/
| filter @logStream like /user-svc/
| sort @timestamp desc
| limit 50
```

**Find slow requests (>2s):**
```
fields @timestamp, path, duration_ms
| filter duration_ms > 2000
| sort duration_ms desc
| limit 20
```

**Track a specific request:**
```
fields @timestamp, @message
| filter request_id = "abc-123-def"
| sort @timestamp asc
```

## ECS Task Health

```bash
# List running tasks
aws ecs list-tasks --cluster bhojango-prod --service-name user-svc

# Describe task health
aws ecs describe-tasks --cluster bhojango-prod --tasks <task-arn>

# View task logs
aws logs get-log-events --log-group-name /ecs/user-svc --log-stream-name <stream>
```

## Deployment Rollback

```bash
# List recent task definitions
aws ecs list-task-definitions --family-prefix bhojango-user-svc --sort DESC --max-items 5

# Rollback to previous version
aws ecs update-service \
  --cluster bhojango-prod \
  --service user-svc \
  --task-definition bhojango-user-svc:<previous-revision> \
  --force-new-deployment

# Monitor rollback
aws ecs wait services-stable --cluster bhojango-prod --services user-svc
```

## Common Failure Scenarios

### Scenario 1: Payment Service Down
**Symptoms:** Checkout fails, payment webhook errors  
**Steps:**
1. Check ECS task status for payment-svc
2. Check Stripe/Razorpay dashboard for outages
3. If payment-svc is down: rollback to last known good task definition
4. If payment provider is down: enable maintenance mode for checkout
5. For stuck payments: use Stripe/Razorpay dashboard to manually refund

### Scenario 2: Order Stuck in "preparing"
**Symptoms:** Customer complains order not progressing  
**Steps:**
1. Query order status: `GET /api/v1/orders/<id>`
2. Check restaurant-svc logs for errors
3. Admin can override: `PUT /api/v1/orders/<id>/status` with admin JWT
4. If systemic: check state machine logs for transition errors

### Scenario 3: RDS Failover
**Symptoms:** Database connection errors across services  
**Steps:**
1. Check RDS events in AWS console
2. Failover is automatic — new primary should be available in <60s
3. Services using PgBouncer should reconnect automatically
4. If connections don't recover: restart ECS tasks

### Scenario 4: Redis Full
**Symptoms:** OTP failures, token refresh errors, slow responses  
**Steps:**
1. Check Redis memory: `INFO memory` via redis-cli
2. Check eviction policy: should be `allkeys-lru`
3. Emergency flush of non-critical keys: `DEL` OTP keys, old blacklist entries
4. Scale up ElastiCache node if persistent issue

### Scenario 5: Driver Location Not Updating
**Symptoms:** Customer sees stale driver location  
**Steps:**
1. Check WebSocket connections in delivery-svc logs
2. Verify DynamoDB writes in CloudWatch
3. Check driver app is sending location (mobile logs)
4. Restart delivery-svc tasks if WebSocket connections are stuck

## Database Maintenance

### Running Migrations Safely
```bash
# 1. Take RDS snapshot before migration
aws rds create-db-snapshot --db-instance-identifier bhojango-prod --db-snapshot-identifier pre-migration-$(date +%Y%m%d)

# 2. Run migration from a bastion host or CI job
cd services/user-svc && alembic upgrade head

# 3. Verify migration
alembic current
```

### Temporarily Disable a Restaurant
```bash
# Via admin API
curl -X PATCH /api/v1/restaurants/<id> \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"is_active": false}'
```

### Manual Refund via Stripe
1. Go to Stripe Dashboard → Payments
2. Find payment by payment_intent_id
3. Click "Refund" → enter amount → confirm
4. Update order status to "cancelled" via admin API

## SLO Dashboard

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API availability | 99.9% | <99.5% |
| Order creation p99 | <500ms | >1000ms |
| Restaurant search p99 | <200ms | >500ms |
| Payment success rate | >99% | <98% |
| Delivery ETA accuracy | ±10 min | >15 min deviation |
