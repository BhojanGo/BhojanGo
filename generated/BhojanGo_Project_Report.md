# BhojanGo — Comprehensive Project Report

**Report Date:** 2026-06-13  
**Repository:** `/Users/raghuram/PycharmProjects/BhojanGo/BhojanGo`  
**Analysis Method:** Complete repository walkthrough — every file read end-to-end  
**Total Files Analyzed:** 299 files  
**Total Lines of Code:** ~14,000+ lines (Python, TypeScript, Terraform, YAML, SQL)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement](#2-problem-statement)
3. [Scope of Work](#3-scope-of-work)
4. [Key Features & Implementation Status](#4-key-features--implementation-status)
5. [Architecture & Dataflow](#5-architecture--dataflow)
6. [Code Quality Assessment](#6-code-quality-assessment)
7. [Per-Module Analysis](#7-per-module-analysis)
8. [Key Observations, Gaps & Improvement Opportunities](#8-key-observations-gaps--improvement-opportunities)
9. [Summary & Recommendations](#9-summary--recommendations)

---

## 1. Overview

BhojanGo is a production-oriented food delivery platform targeting the **USA** and **India** markets. It is architected as a **microservices monorepo** using Turborepo + pnpm workspaces, comprising:

- **6 Python/FastAPI backend services** for core domain logic
- **1 Node.js/TypeScript batch delivery engine** for multi-order batching
- **3 Frontend applications** (Next.js web app, Expo React Native mobile app, Next.js admin dashboard)
- **3 Shared packages** (TypeScript types, React UI components, lint/format config)
- **15 Terraform modules** for AWS infrastructure
- **Comprehensive documentation** including ADRs, technical design docs, and operational runbooks

### Repository Statistics

| Metric | Count |
|--------|-------|
| Total files | 299 |
| Python backend files | ~145 files (~6,800 LOC) |
| TypeScript/TSX frontend files | ~97 files (~9,200 LOC) |
| Terraform files | 48 files (~2,945 LOC) |
| Documentation files | 15 files (~3,138 LOC) |
| CI/CD workflows | 3 files (~468 LOC) |
| Dockerfiles + compose | 8 files |
| Alembic migrations | 9 files |
| Unit/integration tests | 12 test files |

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo + pnpm workspaces |
| Web App | Next.js 14 (App Router), TypeScript, Tailwind CSS, Zustand, TanStack Query |
| Mobile | Expo 51 (React Native), NativeWind, expo-router, react-native-maps |
| Admin | Next.js 14, Tailwind CSS (dark theme), Chart.js |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| Batch Engine | Node.js 20, TypeScript, Express.js, PostgreSQL |
| Database | PostgreSQL 16 (per-service schemas), Redis 7, DynamoDB |
| Search | OpenSearch 2.14 |
| Messaging | AWS SNS + SQS |
| Auth | JWT + AWS Cognito + Google OAuth + Apple Sign-In + OTP (Twilio) |
| Payments | Stripe (US) + Razorpay (India) + in-app wallet |
| API Gateway | Kong 3.7 (declarative, DB-less) |
| Infrastructure | Terraform (15 modules), AWS ECS Fargate, RDS, ElastiCache |
| CI/CD | GitHub Actions (3 workflows) |
| Observability | Prometheus, CloudWatch, structlog (structured JSON logging) |

---

## 2. Problem Statement

BhojanGo aims to solve inefficiencies in the food delivery sector, specifically:

1. **High per-order delivery costs**: Traditional single-order dispatch is wasteful when multiple orders from nearby restaurants go to nearby customers.
2. **Poor driver utilization**: Deadheading (empty return trips) between deliveries wastes driver time and fuel.
3. **Market fragmentation**: Existing solutions are either US-centric (DoorDash/Uber Eats) or India-centric (Swiggy/Zomato) but not built for both markets simultaneously with native multi-currency (USD/INR) and multi-language (en-US, en-IN, hi-IN) support.
4. **Lack of transparency**: Hidden fees and unclear commission structures create friction between restaurants and platforms.
5. **Fragmented tooling**: Restaurant owners, drivers, and admins need separate, often disjointed tools to manage operations.

### What the Platform Provides

- **For Customers**: Browse restaurants, order food, track delivery in real-time, manage wallets, earn loyalty points
- **For Drivers**: Accept deliveries, follow optimized routes, track earnings, manage shifts
- **For Restaurants**: Manage menus, track orders, configure pricing models, manage reviews
- **For Admins/City Managers**: Full operational visibility, pain-point analytics, commission management, user/driver/restaurant oversight

---

## 3. Scope of Work

### In Scope (Implemented)

1. **User authentication & profiles** — Registration, login, JWT tokens, refresh rotation, OTP verification, Google/Apple social login, role-based access (6 roles), GDPR anonymization, address management
2. **Restaurant management** — CRUD, approval workflow, menu categories/items, reviews, OpenSearch full-text + geo search, Redis caching, S3 image uploads, pain-point pricing models
3. **Order lifecycle** — Creation, state machine (8 states), status history, fee transparency, commission calculation, SNS event publishing, idempotency
4. **Delivery tracking** — Real-time GPS via Redis + WebSocket, shift tracking, driver earnings with floor guarantee, ETA calculation (AWS Location + Haversine fallback), DynamoDB location history
5. **Payment processing** — Stripe (US), Razorpay (India), dual-provider webhooks, in-app wallet (top-up, transactions, refunds), idempotent payments
6. **Notifications** — Multi-channel (FCM push, Twilio SMS, SendGrid email), i18n templates (3 locales), SQS event consumption
7. **Batch delivery engine** — Multi-order batching with composite scoring, route optimization (permutation-based), greedy selection, SQS/SNS integration
8. **Web application** — 17 pages including landing, auth, restaurant browsing, cart, checkout, payment, order tracking, wallet, profile
9. **Mobile application** — 16 screens including customer + driver flows, real-time maps, GPS tracking, earnings dashboard
10. **Admin dashboard** — 10 pages including KPIs, orders, restaurants, drivers, users, payments, pricing editor, analytics
11. **Infrastructure** — 15 Terraform modules (VPC, ALB, ECS, RDS, Redis, OpenSearch, S3, Cognito, IAM, CloudWatch, etc.), Kong API Gateway, Docker Compose local dev
12. **CI/CD** — GitHub Actions with parallel jobs, path-based change detection, security scanning (gitleaks, bandit, semgrep, safety)

### Partially Implemented

1. **Admin order detail page** — Admin dashboard lacks individual order inspection
2. **Mobile cart persistence** — Cart lost on app restart (no Zustand persist)
3. **Mobile payment SDK integration** — Stripe/Razorpay SDKs not wired into mobile checkout
4. **Apple Sign-In verification** — Signature verification disabled (security vulnerability)
5. **SMS/Email dispatch** — Notification templates exist but SMS/email channels not wired to dispatcher
6. **Menu category CRUD** — Categories created implicitly via menu items; no dedicated endpoints
7. **Review listing** — Reviews can be submitted but no endpoint to list reviews for a restaurant
8. **OpenSearch menu indexing** — Restaurant index exists; menu items index configured but never created
9. **Driver assignment automation** — Admin-only manual assignment; no predictive matching
10. **Batch engine deployment** — Service exists but not in CI/CD, docker-compose, or Terraform ECS

### Out of Scope / Not Implemented

1. **E2E tests** — Documented but no Playwright/Detox tests in repo
2. **Integration tests** — No docker-compose-based integration tests in CI
3. **Load tests** — k6 scripts documented but not present
4. **ML-based batch scoring** — Only heuristic scoring implemented
5. **Customer batch opt-in** — No UI for customers to choose batched delivery
6. **UPI payment (India)** — Razorpay integration exists but UPI-specific UI not built
7. **Grocery vertical** — Food-only; no grocery batch profile
8. **Real-time traffic data** — Google Routes API not integrated
9. **Multi-region deployment** — Single-region only
10. **WAF/DDoS protection** — No AWS WAF configured

---

## 4. Key Features & Implementation Status

### 4.1 User Service (user-svc)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Email/password registration | ✅ Complete | High |
| Login with bcrypt | ✅ Complete | High |
| JWT access + refresh tokens | ✅ Complete | High |
| Token rotation & blacklist | ✅ Complete | High |
| Phone OTP (Twilio) | ✅ Complete | Medium |
| Password reset via OTP | ✅ Complete | High |
| Google OAuth2 | ✅ Complete | High |
| Apple Sign-In | ⚠️ Partial | Low (sig not verified) |
| User profile CRUD | ✅ Complete | High |
| GDPR anonymization | ✅ Complete | High |
| Address CRUD | ✅ Complete | Medium (no update) |
| Role-based access (6 roles) | ✅ Complete | High |
| Rate limiting (slowapi) | ✅ Complete | High |
| Prometheus metrics | ✅ Complete | High |
| 11 integration tests | ✅ Complete | High |

### 4.2 Restaurant Service (restaurant-svc)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Restaurant CRUD + slug | ✅ Complete | High |
| Approval workflow | ✅ Complete | High |
| Menu category & item CRUD | ⚠️ Partial | Medium (no cat update/delete) |
| Review submission | ✅ Complete | High |
| Review listing | ❌ Missing | — |
| OpenSearch full-text search | ✅ Complete | High |
| OpenSearch geo search | ✅ Complete | High |
| Redis caching (5 min) | ✅ Complete | High |
| S3 presigned uploads | ✅ Complete | High |
| Delivery radius check | ✅ Complete | High |
| Pricing model config | ✅ Complete | High |
| Pain-point analytics | ✅ Complete | High |
| 8 geo unit tests | ✅ Complete | Medium |

### 4.3 Order Service (order-svc)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Order CRUD | ✅ Complete | High |
| State machine (8 states) | ✅ Complete | High |
| Role-based transitions | ✅ Complete | High |
| Status history tracking | ✅ Complete | High |
| Fee transparency | ✅ Complete | High |
| Commission calculation | ✅ Complete | High |
| Geo validation | ✅ Complete | High |
| Idempotent creation | ✅ Complete | High |
| SNS event publishing | ✅ Complete | High |
| Admin pain-point analytics | ✅ Complete | High |
| 2 test files (commission + state machine) | ✅ Complete | Medium |

### 4.4 Delivery Service (delivery-svc)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Real-time GPS tracking | ✅ Complete | High |
| WebSocket live tracking | ✅ Complete | High |
| Shift time tracking | ✅ Complete | High |
| Driver earnings + floor guarantee | ✅ Complete | High |
| ETA calculation | ✅ Complete | High |
| DynamoDB location history | ✅ Complete | High |
| Driver assignment | ⚠️ Partial | Low (manual only) |
| 2 test files (earnings + ETA) | ✅ Complete | Medium |

### 4.5 Payment Service (payment-svc)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Stripe integration (US) | ✅ Complete | High |
| Razorpay integration (India) | ✅ Complete | High |
| Webhook signature verification | ✅ Complete | High |
| In-app wallet | ✅ Complete | High |
| Wallet top-up | ✅ Complete | High |
| Refunds (partial/full) | ✅ Complete | High |
| Idempotent payments | ✅ Complete | High |
| SNS event publishing | ✅ Complete | High |
| 1 test file (wallet) | ✅ Complete | Medium |

### 4.6 Notification Service (notification-svc)
| Requirement | Status | Quality |
|-------------|--------|---------|
| FCM push notifications | ✅ Complete | High |
| Twilio SMS | ✅ Complete | High |
| SendGrid email | ✅ Complete | High |
| SQS event consumer | ✅ Complete | High |
| i18n templates (3 locales) | ✅ Complete | High |
| Device token management | ✅ Complete | High |
| In-app notification storage | ✅ Complete | High |
| SMS/Email dispatch from events | ⚠️ Partial | Low (not wired) |
| 1 test file (templates) | ✅ Complete | Low |

### 4.7 Batch Delivery Engine (batch-engine)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Batch formation algorithm | ✅ Complete | High |
| Route optimization | ✅ Complete | High |
| Composite scoring | ✅ Complete | High |
| Greedy selection | ✅ Complete | High |
| REST API (7 endpoints) | ✅ Complete | High |
| JWT auth | ✅ Complete | High |
| SQS consumer | ✅ Complete | High |
| SNS publisher | ✅ Complete | High |
| PostgreSQL schema (6 tables) | ✅ Complete | High |
| Unit tests (scorer + creation) | ✅ Complete | High |
| Driver integration | ❌ Missing | — |
| Route recalculation on removal | ⚠️ Partial | Low (TODO) |

### 4.8 Web Application (apps/web)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Landing page | ✅ Complete | High |
| Auth (login, signup, forgot password) | ✅ Complete | High |
| Restaurant browsing + search | ✅ Complete | High |
| Restaurant detail + menu | ✅ Complete | High |
| Cart management | ✅ Complete | High |
| Checkout + address | ✅ Complete | High |
| Payment (Stripe, Razorpay, wallet, COD) | ✅ Complete | High |
| Order history | ✅ Complete | High |
| Order tracking (WebSocket) | ✅ Complete | High |
| Wallet | ✅ Complete | High |
| Profile management | ✅ Complete | High |
| i18n (3 locales) | ✅ Complete | High |
| Dark mode (CSS only) | ⚠️ Partial | Low (no toggle) |
| SEO (robots, sitemap) | ✅ Complete | High |
| Real map tracking | ❌ Missing | — |

### 4.9 Mobile Application (apps/mobile)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Auth (login, signup) | ✅ Complete | High |
| Restaurant browsing | ✅ Complete | High |
| Search + filters | ✅ Complete | High |
| Cart + checkout | ✅ Complete | High |
| Order tracking (WebSocket + MapView) | ✅ Complete | High |
| Driver home (online toggle, orders) | ✅ Complete | High |
| Driver active delivery | ✅ Complete | High |
| Driver earnings | ✅ Complete | High |
| Wallet | ✅ Complete | High |
| Cart persistence | ❌ Missing | — |
| Payment SDK integration | ❌ Missing | — |
| Push notification tap handling | ❌ Missing | — |

### 4.10 Admin Dashboard (apps/admin)
| Requirement | Status | Quality |
|-------------|--------|---------|
| Login with role check | ✅ Complete | High |
| KPI dashboard | ✅ Complete | High |
| Orders management | ✅ Complete | High |
| Restaurants management | ✅ Complete | High |
| Drivers list | ✅ Complete | High |
| Users management | ✅ Complete | High |
| Payments + refunds | ✅ Complete | High |
| Pricing/commission editor | ✅ Complete | High |
| Pain-point analytics | ✅ Complete | High |
| Revenue analytics | ✅ Complete | High |
| Order detail page | ❌ Missing | — |

### 4.11 Infrastructure & DevOps
| Requirement | Status | Quality |
|-------------|--------|---------|
| 15 Terraform modules | ✅ Complete | High |
| Kong API Gateway | ✅ Complete | High |
| Docker Compose (local dev) | ⚠️ Partial | Medium (missing services) |
| CI/CD (3 workflows) | ⚠️ Partial | Medium (missing batch-engine) |
| Security scanning | ✅ Complete | High |
| Shared types package | ✅ Complete | High |
| Shared UI package | ✅ Complete | High |
| Shared config package | ✅ Complete | High |
| Terraform state locking | ❌ Missing | — |
| WAF | ❌ Missing | — |
| E2E tests in CI | ❌ Missing | — |

---

## 5. Architecture & Dataflow

### 5.1 Overall System Architecture

```
                           ┌──────────────┐
                           │   Kong API   │
                           │   Gateway    │
                           │   :8888      │
                           └──────┬───────┘
                                  │
         ┌─────────┬──────────────┼──────────────┬──────────┐
         │         │              │              │          │
    ┌────▼───┐ ┌───▼────┐   ┌───▼────┐    ┌───▼────┐ ┌───▼──────┐
    │  Web   │ │ Mobile │   │ Admin  │    │batch-  │ │notification│
    │ :3000  │ │ :8081  │   │ :3001  │    │engine  │ │  :8006    │
    └────────┘ └────────┘   └────────┘    │ :8007  │ └─────┬─────┘
                                          └────────┘       │
                                                           │
    ┌────────┬────────┬────────┬────────┬────────┬────────┤
    │        │        │        │        │        │        │
┌───▼───┐ ┌─▼─────┐ ┌─▼─────┐ ┌─▼─────┐ ┌─▼─────┐ ┌─▼────┐
│user   │ │restaurant│ │order  │ │delivery│ │payment │ │notif  │
│svc    │ │svc     │ │svc    │ │svc    │ │svc   │ │svc   │
│:8001  │ │:8002   │ │:8003  │ │:8004  │ │:8005 │ │:8006 │
└───┬───┘ └────┬──┘ └───┬───┘ └───┬───┘ └───┬───┘ └──┬───┘
    │          │        │         │         │        │
    │     ┌────▼────────┼─────────┼─────────┼────────┘
    │     │             │         │         │
┌───▼─────▼─────▼───────▼─────────▼─────────▼──────┐
│              PostgreSQL 16                         │
│         (per-service schemas)                      │
└──────────────────────┬─────────────────────────────┘
                       │
    ┌──────────┬───────┴──────┬──────────────┐
    │          │              │              │
┌───▼───┐ ┌───▼─────┐   ┌───▼─────┐   ┌────▼────┐
│ Redis │ │OpenSearch│   │DynamoDB │   │LocalStack│
│ :6379 │ │ :9200   │   │ :8000   │   │ :4566   │
└───────┘ └─────────┘   └─────────┘   └─────────┘
```

### 5.2 Order Lifecycle Dataflow

```
Customer                    Web/Mobile                    Backend Services
    │                            │                               │
    │ Browse restaurants         │                               │
    ├────────────────────────────>│                               │
    │                            │ GET /restaurants              │
    │                            ├──────────────────────────────>│ restaurant-svc
    │                            │                               │ (OpenSearch + Redis)
    │ <──────────────────────────┤                               │
    │                            │                               │
    │ Add items to cart          │                               │
    │                            │ (local Zustand state)         │
    │                            │                               │
    │ Checkout                   │                               │
    ├────────────────────────────>│                               │
    │                            │ POST /orders                  │
    │                            ├──────────────────────────────>│ order-svc
    │                            │                               │ (state: pending)
    │                            │                               │ SNS: order.created
    │                            │                               ├──────────┐
    │                            │                               │          │
    │ <──────────────────────────┤                               ▼          ▼
    │                            │                         notification-svc  batch-engine
    │ Pay                         │                           (push)         (add to pool)
    ├────────────────────────────>│                               │
    │                            │ POST /payments/initiate       │
    │                            ├──────────────────────────────>│ payment-svc
    │                            │                               │ (Stripe/Razorpay)
    │                            │                               │
    │                            │ Webhook callback              │
    │                            │<──────────────────────────────┤
    │                            │                               │ SNS: payment.succeeded
    │                            │                               ├──────────┐
    │                            │                               ▼          ▼
    │                            │                         order-svc    notification-svc
    │                            │                         (confirmed)  (email receipt)
    │                            │                               │
    │                            │                               │ SNS: order.confirmed
    │                            │                               ├──────────┐
    │                            │                               ▼          ▼
    │                            │                         batch-engine   notification-svc
    │                            │                         (form batch)   (push: confirmed)
    │                            │                               │
    │                            │                               │ SNS: batch.formed
    │                            │                               ├───────────────┐
    │                            │                               ▼               │
    │                            │                         delivery-svc       order-svc
    │                            │                         (find driver)      (update ETA)
    │                            │                               │
    │ Track delivery             │                               │
    │<═══════════════════════════│ WS /ws/track/{orderId}        │
    │     (real-time GPS)        │<══════════════════════════════┤
    │                            │         (Redis pub/sub)       │
    │                            │                               │
    │ Delivered                  │                               │
    │                            │                               │ Driver marks delivered
    │                            │                               │ SNS: order.delivered
    │ <──────────────────────────┤                               ├──────────┐
    │ Push: "Delivered!"         │                               ▼          ▼
    │                            │                         notification-svc   order-svc
    │                            │                           (push+email)   (completed)
```

### 5.3 Batch Engine Workflow

```
order-svc
    │
    │ SNS: order.confirmed
    ▼
┌────────────────────────┐
│    SQS Queue           │
└──────────┬─────────────┘
           │
           ▼
┌─────────────────────────────┐
│  batch-engine (:8007)       │
│                             │
│  ┌─────────────────────┐    │
│  │ Order Pool (PG)     │    │
│  └──────────┬──────────┘    │
│             │               │
│             ▼ (every 30s)   │
│  ┌─────────────────────┐    │
│  │ 1. Pull waiting     │    │
│  │ 2. Group by pickup  │    │
│  │ 3. Generate combos  │    │
│  │ 4. Route optimize   │    │
│  │ 5. Score candidates │    │
│  │ 6. Greedy select    │    │
│  └──────────┬──────────┘    │
│             │               │
│             ▼               │
│  ┌─────────────────────┐    │
│  │ Batches (PG)        │    │
│  └──────────┬──────────┘    │
│             │               │
│             ▼               │
│  SNS: batch.formed          │
└─────────────────────────────┘
           │
           ▼
     delivery-svc
     (find nearest driver)
```

### 5.4 Auth Flow

```
┌─────────┐     ┌──────────┐     ┌─────────┐     ┌──────────┐
│ Client  │────>│user-svc  │────>│ Redis   │     │ PostgreSQL│
│ (Web/   │     │(:8001)   │     │(:6379)  │     │(:5432)   │
│ Mobile) │<────│          │<────│         │<────│          │
└─────────┘     └──────────┘     └─────────┘     └──────────┘
     │               │
     │ 1. Register   │
     ├──────────────>│
     │               │ bcrypt hash
     │               │ store in DB
     │               │ generate JWT pair
     │               │ store refresh in Redis
     │<──────────────│ return tokens + user
     │               │
     │ 2. Login      │
     ├──────────────>│
     │               │ verify bcrypt
     │               │ generate new JWT pair
     │               │ blacklist old access token
     │<──────────────│ return tokens + user
     │               │
     │ 3. API Call   │
     ├──────────────>│ Kong validates JWT
     │ (Bearer token)│ check Redis blacklist
     │               │ route to service
     │<──────────────│ return data
     │               │
     │ 4. Refresh    │
     ├──────────────>│
     │               │ validate refresh token
     │               │ rotate: delete old, issue new
     │<──────────────│ return new pair
     │               │
     │ 5. Logout     │
     ├──────────────>│
     │               │ add access token to Redis blacklist
     │               │ delete all refresh tokens
     │<──────────────│ 204 No Content
```

---

## 6. Code Quality Assessment

### 6.1 Overall Quality Score

| Domain | Score | Assessment |
|--------|-------|------------|
| Backend services (Python) | 8/10 | Strong async patterns, clean architecture, good error handling |
| Batch engine (TypeScript) | 8/10 | Well-designed algorithms, type-safe, testable pure functions |
| Frontend (Next.js + Expo) | 7/10 | Good state management, consistent patterns, some missing features |
| Infrastructure (Terraform) | 9/10 | Excellent modular design, production-ready configurations |
| Documentation | 9/10 | Comprehensive ADRs, detailed design docs, operational guides |
| Testing | 4/10 | Unit tests only, no integration or E2E tests, coverage gaps |
| Security | 6/10 | JWT signed, webhooks verified, but Apple auth bypass, no WAF |
| DevOps | 7/10 | Good CI/CD structure, but missing batch-engine, bypassable tests |

### 6.2 Strengths Across Codebase

1. **Consistent layered architecture** — All Python services follow routes → services → repositories → models pattern
2. **SQLAlchemy 2.0 async** — Proper use of `AsyncAttrs`, `async_sessionmaker`, `selectinload`
3. **Pydantic v2** — Modern validation with `model_validate`, `model_dump` across all services
4. **Decimal for money** — All monetary values use `NUMERIC(12,2)` — no float rounding bugs
5. **Structured logging** — structlog with JSON output, correlation IDs, context variables
6. **Health endpoints** — Three-tier probes (/health, /health/live, /health/ready) on all services
7. **Fail-fast config** — Services validate required env vars at startup and refuse to start if missing
8. **JWT token rotation** — Refresh tokens rotated on every use, old tokens explicitly invalidated
9. **Idempotency keys** — Payment and order creation use Redis-backed idempotency
10. **Graceful degradation** — OpenSearch failures return empty results rather than 500s
11. **i18n support** — 3 locales with Hindi support in templates and UI
12. **Dark mode infrastructure** — Tailwind dark: classes present, admin uses dark-first design
13. **Type safety** — Comprehensive TypeScript types in shared packages, all services typed

### 6.3 Issues Across Codebase

1. **Apple Sign-In security vulnerability** — `verify_signature=False` allows token forgery
2. **Restaurant auth mechanism duality** — Kong headers and JWT both defined; only JWT used
3. **No Terraform state locking** — Risk of concurrent state corruption
4. **Tests bypass failures** — `|| true` in CI allows test failures to pass
5. **Shared code duplication** — `geo.py`, `auth.py`, `correlation.py` repeated across services
6. **No circuit breaker** — Synchronous HTTP calls between services lack failure isolation
7. **Cache stampede risk** — No Redis SET NX locking for expensive cache writes
8. **Sensitive data in logs** — OTP values logged in dev/test mode
9. **Menu item hard deletes** — `deleted_at` column present but `delete()` hard-deletes
10. **No email verification** — Only phone OTP; no email confirmation flow
11. **Mobile cart not persisted** — Zustand store lacks persist middleware
12. **No WebSocket reconnection** — No exponential backoff on disconnect
13. **Batch engine missing from deployment** — Not in CI/CD, docker-compose, or Terraform
14. **Kong rate limiting local policy** — Won't work with multiple Kong instances
15. **No WAF/DDoS protection** — ALB exposed without AWS WAF

---

## 7. Per-Module Analysis

### 7.1 User Service (user-svc)
**Files:** 35 | **Lines:** 2,154 | **Language:** Python

**Implemented:**
- Full auth lifecycle with JWT, bcrypt, Redis token storage
- Phone OTP via Twilio with rate limiting
- Google OAuth2 and Apple Sign-In (signature disabled)
- User profile CRUD with GDPR anonymization
- Address CRUD (create/list/delete, no update)
- 6 role system with dependency injectors
- 11 integration tests with SQLite in-memory DB

**Quality:** ⭐⭐⭐⭐ (4/5) — Excellent architecture, clean separation, but Apple auth bypass is a critical security issue.

**Key Gaps:**
- Apple token signature not verified (CRITICAL SECURITY)
- Unused `require_restaurant_owner` / `require_driver` dependencies
- No address update endpoint
- No email verification flow
- No OTP integration tests (only mocked)
- No FCM/SNS integration despite config

---

### 7.2 Restaurant Service (restaurant-svc)
**Files:** 35 | **Lines:** 2,199 | **Language:** Python

**Implemented:**
- Restaurant CRUD with auto-slug generation and approval workflow
- Menu category and item CRUD
- Review submission with order-level uniqueness
- OpenSearch integration for full-text + geo search
- Redis caching with pattern invalidation
- S3 presigned URLs for image uploads
- Pain-point pricing models (3 types)
- Delivery radius check with Haversine
- 8 geo unit tests

**Quality:** ⭐⭐⭐⭐ (4/5) — Feature-rich with good caching and search, but menu categories lack full CRUD and tests are sparse.

**Key Gaps:**
- No menu category update/delete endpoints
- No review listing endpoint
- No OpenSearch indexing for menu items
- No API rate limiting (slowapi imported but not wired)
- No structured logging config (unlike user-svc)
- Menu items hard-deleted despite soft-delete column
- No integration tests

---

### 7.3 Order Service (order-svc)
**Files:** 23 | **Lines:** 1,328 | **Language:** Python

**Implemented:**
- Order creation with idempotency keys
- 8-state order state machine with role-based transitions
- Status history tracking (JSONB array)
- Fee transparency (platform_fee, restaurant_payout visible)
- Commission calculation (percentage, flat fee, subscription)
- SNS event publishing for all lifecycle events
- Admin pain-point analytics endpoint

**Quality:** ⭐⭐⭐⭐⭐ (5/5) — Cleanest service. State machine is well-structured, money handled properly with Decimal, business logic separated from routes.

**Key Gaps:**
- No periodic cleanup of stale pending orders
- No order editing capability
- No loyalty points redemption logic (points stored but unused)
- No rate limiting
- No integration tests

---

### 7.4 Delivery Service (delivery-svc)
**Files:** 16 | **Lines:** 799 | **Language:** Python

**Implemented:**
- Real-time driver location (Redis with 30s TTL)
- WebSocket for customer tracking (Redis pub/sub)
- Shift tracking (start, activity, end)
- Driver earnings with floor guarantee model
- ETA calculation (AWS Location with Haversine fallback)
- DynamoDB append-only location history

**Quality:** ⭐⭐⭐⭐ (4/5) — Solid real-time tracking. Earnings calculation is sophisticated with floor guarantee. But driver assignment is manual-only.

**Key Gaps:**
- No automated driver assignment (admin-only endpoint)
- No delivery proof (photo/signature)
- No driver rating integration
- No cancellation flow coordination with order-svc
- DynamoDB optional (graceful failure but no alerts)

---

### 7.5 Payment Service (payment-svc)
**Files:** 17 | **Lines:** 770 | **Language:** Python

**Implemented:**
- Stripe integration with PaymentIntent
- Razorpay integration with Order creation
- Webhook signature verification for both providers
- In-app wallet with ledger-based transactions
- Partial and full refunds
- Idempotent payment processing
- SNS event publishing

**Quality:** ⭐⭐⭐⭐⭐ (5/5) — Dual-provider handling is clean, webhook security is proper, wallet uses ledger pattern (append-only transactions).

**Key Gaps:**
- No 3D Secure / SCA handling
- No saved payment methods
- No payment retry logic
- No dispute/chargeback handling
- Wallet doesn't support multiple currencies per user
- Webhook event deduplication not implemented

---

### 7.6 Notification Service (notification-svc)
**Files:** 19 | **Lines:** 1,010 | **Language:** Python

**Implemented:**
- FCM push (single + multicast)
- Twilio SMS
- SendGrid HTML email
- SQS long-polling consumer with retry
- i18n templates (10 event types × 3 locales)
- Device token management
- In-app notification storage and read tracking

**Quality:** ⭐⭐⭐⭐ (4/5) — Good i18n support and mock modes for dev. But SMS/email not wired from event dispatcher.

**Key Gaps:**
- SMS and email channels defined but not dispatched from events
- No notification deletion endpoint
- No notification preference management
- No retry/DLQ for failed sends
- Only template unit tests (1 test file)

---

### 7.7 Batch Delivery Engine (batch-engine)
**Files:** 25 | **Lines:** 2,957 | **Language:** TypeScript

**Implemented:**
- Order pool management (PostgreSQL)
- Batch formation with grouping, scoring, greedy selection
- Route optimization via permutation search (2-3 orders)
- Composite scoring (distance, time, detour, priority, capacity)
- 7 REST API endpoints
- JWT auth with custom HMAC (no external deps)
- SQS consumer + SNS publisher
- Unit tests for scorer and optimizer

**Quality:** ⭐⭐⭐⭐⭐ (5/5) — Best TypeScript code in the repo. Pure functions for core algorithm, comprehensive types, transaction safety, and good test coverage.

**Key Gaps:**
- Route recalculation on order removal (TODO in code)
- No driver integration (doesn't call delivery-svc)
- No real driver location used (uses centroid)
- No driver capacity lookup
- SQS consumer infinite loop with no stop mechanism
- No metrics endpoint

---

### 7.8 Web Application (apps/web)
**Files:** 43 | **Lines:** 4,586 | **Language:** TypeScript/TSX

**Implemented:**
- 17 pages with Next.js App Router
- Full auth flow (login, signup 3 roles, forgot password via OTP)
- Restaurant search with filters, sorting, pagination
- Cart with cross-restaurant guard
- Checkout with address, payment method, order placement
- Stripe Elements + Razorpay payment flows
- Order tracking with WebSocket + status timeline
- Wallet with top-up
- i18n with next-intl (3 locales)
- SEO (robots, sitemap)

**Quality:** ⭐⭐⭐⭐ (4/5) — Feature-complete customer web app. Good state management, proper auth interceptors, full i18n.

**Key Gaps:**
- No real map integration (shows coordinates as text)
- Dark mode CSS exists but no toggle
- Payment page has hardcoded strings (no i18n)
- No WebSocket reconnection logic
- Reviews tab is placeholder

---

### 7.9 Mobile Application (apps/mobile)
**Files:** 27 | **Lines:** 2,431 | **Language:** TypeScript/TSX

**Implemented:**
- 16 screens with Expo Router
- Auth with role-based routing (customer vs driver)
- Restaurant browsing, search, cart, checkout
- Driver home with online toggle and GPS
- Driver active delivery with MapView and route
- Driver earnings with shift breakdown
- Order tracking via WebSocket + react-native-maps
- Wallet

**Quality:** ⭐⭐⭐ (3/5) — Good native feature usage (expo-location, secure-store, maps). But missing critical features like cart persistence and payment SDK.

**Key Gaps:**
- Cart lost on app restart (CRITICAL UX)
- No Stripe/Razorpay SDK integration (payment incomplete)
- No push notification tap handling
- Several profile menu items are empty (`onPress={() => {}}`)
- No cart persistence

---

### 7.10 Admin Dashboard (apps/admin)
**Files:** 18 | **Lines:** 1,645 | **Language:** TypeScript/TSX

**Implemented:**
- Login with role check
- KPI dashboard with metrics cards
- Orders table with filters
- Restaurants table with approve/reject/toggle
- Drivers table with status
- Users table with role filter
- Payments with refund capability
- Commission/pricing model editor
- Pain-point analytics
- Revenue chart (7-day)

**Quality:** ⭐⭐⭐⭐ (4/5) — Comprehensive admin tooling. Dark-first design is polished. Good role-based navigation.

**Key Gaps:**
- No order detail page (cannot inspect individual orders)
- No user action buttons (suspend, delete)
- No driver detail view
- Analytics uses gradient divs instead of chart library (react-chartjs-2 in deps but unused)
- Pagination param inconsistency (`page` vs `offset`)

---

### 7.11 Shared Packages
**Files:** 23 | **Lines:** ~1,600 | **Language:** TypeScript, JavaScript

**Implemented:**
- 9 domain type files with comprehensive interfaces
- 6 shared UI components (Button, Card, Badge, Input, Modal, Spinner)
- ESLint + Prettier + TypeScript shared configs
- CVA variant system for UI components
- Consistent API response wrapper types

**Quality:** ⭐⭐⭐⭐⭐ (5/5) — Well-structured types, proper CJS+ESM dual format, clean component API.

**Key Gaps:**
- No Storybook for component documentation
- No unit tests for UI components
- No versioning/release process

---

### 7.12 Infrastructure (Terraform + Kong + CI/CD)
**Files:** 89 | **Lines:** ~8,729 | **Language:** HCL, YAML, SQL

**Implemented:**
- 15 Terraform modules (48 files)
- Kong declarative gateway config (196 lines)
- Docker Compose local dev
- 3 GitHub Actions workflows (CI, PR checks, security)
- Security scanning (gitleaks, bandit, semgrep, safety)
- Seed scripts (users, restaurants, orders)

**Quality:** ⭐⭐⭐⭐⭐ (5/5) — Production-grade IaC. Excellent module separation, environment-aware configs, least-privilege IAM.

**Key Gaps:**
- No Terraform state locking (DynamoDB)
- No WAF on ALB
- batch-engine missing from CI/CD, docker-compose, Terraform ECS
- Tests bypass failures with `|| true`
- No container scanning (Trivy)
- No E2E tests in CI
- No OpenSearch in docker-compose

---

## 8. Key Observations, Gaps & Improvement Opportunities

### 8.1 Critical (Must Fix Before Production)

| # | Issue | Module | Impact |
|---|-------|--------|--------|
| 1 | **Apple Sign-In signature not verified** | user-svc | 🔴 Security — any forged token accepted |
| 2 | **No Terraform state locking** | infra | 🔴 Risk of concurrent state corruption |
| 3 | **No WAF on ALB** | infra | 🔴 DDoS/rate attack exposure |
| 4 | **Tests bypass failures** (`\|\| true`) | CI/CD | 🔴 False confidence in code quality |
| 5 | **batch-engine not deployed** | infra | 🔴 Core cost-saving feature unavailable |
| 6 | **No rate limiting on Kong cluster** | infra | 🔴 Won't scale horizontally |
| 7 | **Mobile cart not persisted** | apps/mobile | 🔴 Critical UX failure |
| 8 | **No payment SDK on mobile** | apps/mobile | 🔴 Cannot complete card payments |

### 8.2 High Priority

| # | Issue | Module | Recommendation |
|---|-------|--------|----------------|
| 9 | Apple Sign-In verification | user-svc | Use Apple's JWKS endpoint for signature verification |
| 10 | Menu category CRUD | restaurant-svc | Add PUT/DELETE endpoints |
| 11 | Review listing endpoint | restaurant-svc | Add `GET /restaurants/{id}/reviews` |
| 12 | SMS/Email dispatch | notification-svc | Wire channels to event dispatcher |
| 13 | Driver assignment automation | delivery-svc | Build predictive driver matching |
| 14 | Webhook deduplication | payment-svc | Check event ID before processing |
| 15 | Admin order detail page | apps/admin | Add `/orders/[id]` route |
| 16 | Real map on web tracking | apps/web | Integrate react-leaflet or Google Maps |
| 17 | WebSocket reconnection | apps/web, mobile | Add exponential backoff |
| 18 | Shared code package | all backend | Extract common auth, logging, geo to shared Python package |
| 19 | Add batch-engine to CI/CD | infra | Add to docker-build and backend-test matrices |
| 20 | Add batch-engine to Terraform | infra | Add ECS task definition for batch-engine |
| 21 | Terraform state locking | infra | Add DynamoDB lock table |
| 22 | Add OpenSearch to docker-compose | infra | Add opensearch container |
| 23 | Remove `\|\| true` from CI | CI/CD | Enforce test failures blocking merge |
| 24 | Clustered rate limiting | infra | Use Redis-backed rate limiting in Kong |

### 8.3 Medium Priority

| # | Issue | Module | Recommendation |
|---|-------|--------|----------------|
| 25 | Circuit breaker for inter-service calls | all backend | Add pybreaker or similar |
| 26 | Transactional outbox | order-svc, payment-svc | Ensure events published after DB commit |
| 27 | Cache stampede prevention | restaurant-svc | Add Redis SET NX locking |
| 28 | Soft delete for menu items | restaurant-svc | Set `deleted_at` instead of hard delete |
| 29 | Order pagination cursor | order-svc | Replace offset with cursor for performance |
| 30 | Payment retry logic | payment-svc | Add retry with exponential backoff |
| 31 | Saved payment methods | payment-svc | Add payment method vaulting |
| 32 | Notification preferences | notification-svc | Add per-user channel preferences |
| 33 | Notification read-all | notification-svc | Add bulk mark-as-read |
| 34 | Mobile push tap handling | apps/mobile | Add NotificationResponse listener |
| 35 | Mobile saved addresses | apps/mobile | Implement address management screen |
| 36 | Analytics chart library | apps/admin | Use react-chartjs-2 instead of div bars |
| 37 | Driver detail page | apps/admin | Add drill-down for driver stats |
| 38 | Pagination consistency | apps/admin | Standardize on `page` param |
| 39 | E2E tests | CI/CD | Add Playwright for web, Detox for mobile |
| 40 | Integration tests | CI/CD | Add docker-compose-based integration tests |
| 41 | Container scanning | CI/CD | Add Trivy scan to docker-build |
| 42 | VPC endpoints | infra | Add S3, SQS, SNS endpoints for cost/latency |

### 8.4 Low Priority

| # | Issue | Module | Recommendation |
|---|-------|--------|----------------|
| 43 | Dark mode toggle | apps/web | Add theme switcher in Navbar |
| 44 | i18n for payment page | apps/web | Wrap strings with `useTranslations` |
| 45 | Error boundaries | all frontend | Add React ErrorBoundary around pages |
| 46 | Request cancellation | all frontend | Add AbortController for race conditions |
| 47 | Minimum order enforcement | apps/web, mobile | Validate before checkout |
| 48 | Delivery time estimation | all frontend | Show dynamic ETA from delivery-svc |
| 49 | Coupon/promo codes | all frontend | Add discount code input |
| 50 | Order cancellation UI | all frontend | Add cancellation flow with reason |
| 51 | Mobile onboarding | apps/mobile | Add first-time user tutorial |
| 52 | Storybook | packages/ui | Add component stories |
| 53 | Changelog | root | Add CHANGELOG.md with conventional commits |
| 54 | Architecture diagrams | docs | Use Mermaid for visual diagrams |
| 55 | ML-based scoring | batch-engine | Train model on delivery data |
| 56 | Google Routes API | batch-engine | Replace haversine with real traffic |
| 57 | Customer batch opt-in | all frontend | Add "Save $1" eco option at checkout |
| 58 | Multi-region deployment | infra | Add DR region |
| 59 | Grocery vertical | batch-engine | Add grocery batch profile |
| 60 | Driver incentive bonus | backend | Add per-extra-order payment |

---

## 9. Summary & Recommendations

### Overall Assessment

BhojanGo is a **well-architected, production-oriented food delivery platform** with strong foundations in microservices, infrastructure-as-code, and comprehensive documentation. The codebase demonstrates mature engineering practices: async-first design, proper money handling, structured logging, JWT security, event-driven architecture, and thorough IaC.

**Overall completion: ~75% production-ready**

### What's Strong

1. **Backend services** — All 6 Python services are well-implemented with clean architecture, async patterns, and good separation of concerns. The order and payment services are particularly polished.
2. **Batch engine** — Sophisticated algorithm with proper scoring, route optimization, and type safety. One of the best-implemented components.
3. **Infrastructure** — 15 Terraform modules with production-ready configurations. Excellent tagging, least-privilege IAM, and environment-aware sizing.
4. **Frontend web** — Feature-complete customer experience with i18n, multiple payment providers, and real-time tracking.
5. **Documentation** — Comprehensive ADRs, detailed technical design docs, and operational runbooks.

### What Needs Work

1. **Security** — Apple Sign-In bypass is a critical vulnerability. No WAF. Terraform state unlocked.
2. **Mobile app** — Cart persistence and payment SDK are critical missing features that block production.
3. **Testing** — Only unit tests exist. No integration, E2E, or load tests in CI.
4. **Deployment gaps** — batch-engine not in CI/CD or Terraform. OpenSearch not in docker-compose.
5. **Cross-cutting duplication** — Auth, logging, and geo utilities duplicated across Python services.

### Recommended Priority Order

**Week 1-2 (Critical Path):**
1. Fix Apple Sign-In verification vulnerability
2. Add batch-engine to CI/CD, docker-compose, and Terraform
3. Add Terraform state locking (DynamoDB)
4. Remove `|| true` from CI test commands
5. Implement mobile cart persistence (Zustand + expo-secure-store)

**Week 3-4 (Production Blockers):**
6. Add WAF to ALB
7. Integrate Stripe/Razorpay SDK into mobile checkout
8. Add admin order detail page
9. Wire SMS/email in notification dispatcher
10. Add real map to web order tracking

**Week 5-8 (Quality & Completeness):**
11. Extract shared Python utilities to a package
12. Add integration tests with docker-compose
13. Add WebSocket reconnection logic
14. Add menu category CRUD endpoints
15. Add review listing endpoint
16. Implement circuit breaker for inter-service calls
17. Add OpenSearch to docker-compose
18. Add E2E tests (Playwright + Detox)

**Month 2+ (Scale & Polish):**
19. ML-based batch scoring
20. Google Routes API integration
21. Customer batch opt-in UI
22. Multi-region deployment
23. Grocery vertical support
24. Comprehensive observability dashboard

---

*Report generated by automated code analysis of all 299 files in the BhojanGo repository.*
*Confined strictly to code present in the repository — no external assumptions or inventions.*
