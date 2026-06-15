# Seed Data Verification — SPR-01 Evidence

**Date:** 2026-06-15
**Database:** PostgreSQL 16 on localhost:5432
**Database:** bhojango
**User:** bhojango

## Seed Verification Query

```sql
SELECT 'restaurants' as table_name, COUNT(*) as count FROM restaurants
UNION ALL SELECT 'menu_categories', COUNT(*) FROM menu_categories
UNION ALL SELECT 'menu_items', COUNT(*) FROM menu_items
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'reviews', COUNT(*) FROM reviews
UNION ALL SELECT 'notifications', COUNT(*) FROM notifications
UNION ALL SELECT 'wallets', COUNT(*) FROM wallets;
```

## Results

| Table | Count | Status |
|-------|-------|--------|
| restaurants | 96 | PASS (>= 90 required) |
| menu_categories | 521 | PASS |
| menu_items | 1669 | PASS |
| users | 12 | PASS |
| orders | 110 | PASS |
| reviews | 0 | WARN (no data) |
| notifications | 40 | PASS |
| wallets | 12 | PASS |

## Schema Information

- Schemas: batch_engine, delivery_svc, notification_svc, order_svc, payment_svc, public, restaurant_svc, user_svc
- All user-facing tables are in `public` schema
- Service-specific schemas exist but tables use public schema with model-level schema qualification

## Alembic Migration Tables

- alembic_version
- alembic_version_notification
- alembic_version_order
- alembic_version_payment
- alembic_version_restaurant
- alembic_version_user

## Notes

1. **restaurants (96)**: Seed requirement was >= 90, current count is 96 — PASS
2. **reviews (0)**: No review data present. May need seed script for reviews.
3. All other tables have data — seed appears successful
4. Seed data loaded via comprehensive_seed.py or comprehensive_seed.sql

## Discrepancies

- `reviews` table is empty (0 records)
- restaurant_svc schema exists but tables are in public schema
- orders count (110) may be from previous test runs

## Recommendations

1. Consider running seed script for reviews if reviews are needed for testing
2. Seed data appears stable — services are healthy with this data