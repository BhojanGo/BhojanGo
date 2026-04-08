# BhojanGo Testing Strategy

## Overview

This document outlines the testing approach across the BhojanGo platform to ensure reliability, security, and performance at every layer.

## 1. Unit Tests

**Tools:** pytest, pytest-asyncio, factory_boy, freezegun  
**Target:** >80% coverage per service  
**Run:** On every commit and PR

### Structure
```
services/<svc>/tests/
├── conftest.py         # Shared fixtures, mock Redis, test DB
├── test_auth.py        # Auth endpoint tests
├── test_models.py      # Model validation tests
├── test_services.py    # Business logic tests
└── test_repositories.py # Data access tests
```

### Key Practices
- Use `factory_boy` for generating test fixtures (User, Restaurant, Order factories)
- Use `freezegun` for time-dependent logic (JWT expiry, OTP windows)
- Mock external services (Twilio, Stripe, Razorpay) with `unittest.mock`
- Each test runs in a transaction that is rolled back (no side effects)

## 2. Integration Tests

**Tools:** pytest-docker, testcontainers  
**Target:** Critical paths — auth flow, order lifecycle, payment processing  
**Run:** On merge to develop

### Setup
- Real PostgreSQL via Docker container
- Real Redis via Docker container
- LocalStack for SQS/SNS

### Scenarios
- User registration → login → token refresh → logout
- Restaurant creation → menu setup → approval → visibility
- Order placement → status transitions → delivery → completion
- Payment initiation → webhook processing → refund

## 3. API Tests

**Tools:** httpx TestClient (FastAPI), pytest  
**Target:** All API endpoints across all services

### Coverage
- Request validation (missing fields, invalid types, boundary values)
- Authentication and authorization (role checks, token expiry)
- Error responses (400, 401, 403, 404, 409, 422, 500)
- Pagination, filtering, sorting
- Idempotency key handling

## 4. End-to-End Tests

**Tools:** Playwright (web), Detox (mobile)  
**Target:** Critical user journeys  
**Run:** On merge to staging

### Web (Playwright)
- Customer: signup → browse → add to cart → checkout → track order
- Restaurant Owner: login → add menu → view orders → update status
- Admin: login → view dashboard → approve restaurant → manage users

### Mobile (Detox)
- Customer: login → browse → order → track
- Driver: go online → accept order → pickup → deliver

## 5. Load Tests

**Tools:** k6  
**Target:** Peak order flow — 1000 orders/minute  
**Run:** Before every production release

### Scenarios
```javascript
// k6 scenarios
export const options = {
  scenarios: {
    peak_ordering: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 500,
      maxVUs: 2000,
      stages: [
        { duration: '2m', target: 50 },   // Ramp up
        { duration: '5m', target: 100 },  // Peak
        { duration: '2m', target: 0 },    // Ramp down
      ],
    },
  },
};
```

### SLOs
- p99 response time < 500ms for order creation
- p99 response time < 200ms for restaurant listing
- Error rate < 0.1% under peak load
- Zero data loss during load test

## 6. Security Tests

**Tools:** bandit (SAST), safety (dependency audit), OWASP ZAP  
**Run:** On every PR (SAST), weekly (ZAP)

### Static Analysis
- `bandit` for Python SAST — block on HIGH severity
- `safety` for CVE checks on dependencies
- `npm audit` for JavaScript dependencies
- `semgrep` for common security anti-patterns

### Dynamic Analysis
- OWASP ZAP scan against staging environment
- SQL injection testing on all input endpoints
- XSS testing on frontend rendering
- Authentication bypass attempts

## 7. Test Data

### Factories (factory_boy)
```python
class UserFactory(factory.Factory):
    class Meta:
        model = User
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    full_name = factory.Faker("name")
    country = "US"

class RestaurantFactory(factory.Factory):
    # ... similar pattern

class OrderFactory(factory.Factory):
    # ... similar pattern
```

### Seed Data
- `scripts/seed/` contains SQL-generating scripts for local/staging
- Idempotent (safe to run multiple times)

## 8. CI Strategy

| Test Type | Trigger | Environment | Blocking |
|-----------|---------|-------------|----------|
| Unit | Every PR | In-memory SQLite + mock Redis | Yes |
| Integration | Merge to develop | Docker PostgreSQL + Redis | Yes |
| API | Every PR | TestClient (in-process) | Yes |
| E2E | Merge to staging | Full stack (Docker Compose) | Yes |
| Load | Pre-production release | Staging environment | Yes (if SLOs breached) |
| Security (SAST) | Every PR | Static analysis | Yes (HIGH severity) |
| Security (DAST) | Weekly | Staging | No (report only) |

## 9. Coverage Reporting

- `pytest-cov` generates coverage reports per service
- Coverage data uploaded to Codecov via GitHub Actions
- Minimum threshold: 80% per service
- Coverage badge on repository README

## 10. Contract Testing (Phase 2)

**Tools:** Pact  
**Purpose:** Verify API contracts between services

### Plan
- Define consumer-driven contracts for inter-service calls
- order-svc ↔ restaurant-svc (menu prices, restaurant info)
- order-svc ↔ payment-svc (payment initiation, webhooks)
- notification-svc ↔ all services (event schemas)
