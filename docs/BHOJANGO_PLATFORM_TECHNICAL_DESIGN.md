# BhojanGo — Platform Technical Design Document

| Field | Value |
|-------|-------|
| **Document** | Platform Technical Design Document |
| **Product** | BhojanGo — Food Delivery Platform |
| **Version** | 1.0 |
| **Date** | April 5, 2026 |
| **Status** | Implementation Complete — Ready for QA & Deployment |
| **Markets** | USA + India |

---

## Table of Contents

1. [What is BhojanGo](#1-what-is-bhojango)
2. [Platform Architecture](#2-platform-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Service Catalog](#4-service-catalog)
5. [User Service (user-svc)](#5-user-service)
6. [Restaurant Service (restaurant-svc)](#6-restaurant-service)
7. [Order Service (order-svc)](#7-order-service)
8. [Delivery Service (delivery-svc)](#8-delivery-service)
9. [Payment Service (payment-svc)](#9-payment-service)
10. [Notification Service (notification-svc)](#10-notification-service)
11. [Batch Delivery Engine (batch-engine)](#11-batch-delivery-engine)
12. [Web App (apps/web)](#12-web-app)
13. [Mobile App (apps/mobile)](#13-mobile-app)
14. [Admin Dashboard (apps/admin)](#14-admin-dashboard)
15. [Shared Packages](#15-shared-packages)
16. [Database Architecture](#16-database-architecture)
17. [Event-Driven Architecture](#17-event-driven-architecture)
18. [API Gateway (Kong)](#18-api-gateway)
19. [Complete API Reference](#19-complete-api-reference)
20. [Authentication & Authorization](#20-authentication--authorization)
21. [Infrastructure (Terraform)](#21-infrastructure-terraform)
22. [CI/CD Pipeline](#22-cicd-pipeline)
23. [Local Development Setup](#23-local-development-setup)
24. [Observability & Monitoring](#24-observability--monitoring)
25. [Security](#25-security)
26. [End-to-End User Flows](#26-end-to-end-user-flows)
27. [What's Done vs What's Next](#27-whats-done-vs-whats-next)
28. [Dev Team Next Steps](#28-dev-team-next-steps)

---

## 1. What is BhojanGo

BhojanGo is a production-ready food delivery platform targeting the USA and India. Think Uber Eats / DoorDash with multi-currency (USD + INR), multi-language (en-US, en-IN, hi-IN), and a smart batch delivery engine that groups nearby orders to reduce costs.

### Key Numbers

| Metric | Value |
|--------|-------|
| Total files in repo | 348 |
| Backend services | 7 (6 Python + 1 Node.js) |
| Frontend apps | 3 (web + mobile + admin) |
| Shared packages | 3 (types, UI, config) |
| API endpoints | 52 (45 REST + 7 batch engine) |
| Terraform modules | 15 |
| Database tables | ~30 across all services |
| Docker containers | 14 (in local dev) |

### User Roles

| Role | Can Do |
|------|--------|
| **Customer** | Browse restaurants, order food, track delivery, manage wallet |
| **Driver** | Accept deliveries, follow routes, update location, complete stops |
| **Restaurant Owner** | Manage menu, update availability, view orders, manage reviews |
| **City Manager** | View own city data, manage restaurants and drivers in their city |
| **Admin / Super Admin** | Full access — all users, orders, payments, analytics, refunds |

---

## 2. Platform Architecture

```
                    ┌──────────────┐ ┌──────────────┐ ┌─────���────────┐
                    │   Web App    │ │  Mobile App  │ │    Admin     │
                    │  Next.js 14  │ │   Expo 51    │ │  Next.js 14  │
                    │   :3000      │ │   :8081      │ │   :3001      │
                    └──────┬──────���┘ └──────┬───────┘ └──────���───────┘
                           │                │                │
                           └────────────────┼───���────────────┘
                                            │
                                    ┌───────▼───────┐
                                    │  Kong Gateway  │
                                    │    :8888       │
                                    │  (routing,     │
                                    │   rate limit,  │
                                    │   CORS)        │
                                    └───────┬───────┘
                                            │
              ┌──────────┬──────────┬───────┼───────┬──────────┬──────────┐
              │          │          │       │       │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌───▼──┐ ┌──▼───┐ ┌▼─────┐ ┌──▼───┐ ┌───▼────┐
         │ user   │ │ rest   │ │order │ │deliv │ │pay   │ │notif │ │ batch  │
         │ svc    │ │ svc    │ │ svc  │ │ svc  │ │ svc  │ │ svc  │ │engine  │
         │ :8001  │ │ :8002  │ │:8003 │ ��:8004 │ │:8005 │ │:8006 │ │ :8007  │
         │ Python │ │ Python │ │Python│ │Python│ │Python│ │Python│ │ Node   │
         └───┬────┘ └───┬────┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬���──┘ └───┬────┘
             │          │         │        │        │        │         │
         ┌───▼──────────▼─────────▼────────▼────────▼────────▼─────────▼──┐
         │                     PostgreSQL 16                                │
         │              (per-service schemas)                               │
         └─────────────────────────┬───────────────────────────────────────┘
                                   │
    ┌──────────┐  ┌────────────┐  ┌▼──────────┐  ┌──────────────┐
    │ Redis 7  │  │ OpenSearch │  │ DynamoDB   │  │ LocalStack   │
    │ (cache)  │  │ (search)   │  │ (delivery  │  │ (SQS+SNS+S3)│
    │ :6379    │  │ :9200      │  │  history)  │  │ :4566        │
    └──────────┘  └────────────┘  └────────────┘  └──────────────┘
```

### Design Principles

1. **Microservices** — each service owns its data and logic, communicates via API or events
2. **Event-driven** — SNS/SQS for async communication (order events, payment events, notifications)
3. **API Gateway** — Kong handles routing, rate limiting, CORS — services never talk to the internet directly
4. **Schema isolation** — single PostgreSQL instance, separate schemas per service
5. **Config via environment** — zero hardcoded secrets, everything in env vars or Secrets Manager

---

## 3. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Monorepo** | Turborepo + pnpm | Fast builds, shared packages, single repo |
| **Web App** | Next.js 14 (App Router) | SSR, SEO, TypeScript, Tailwind |
| **Mobile** | Expo 51 (React Native) | iOS + Android from one codebase |
| **Admin** | Next.js 14 | Same stack as web, role-based access |
| **Backend (6 services)** | Python FastAPI | Async, fast, auto-generated Swagger docs |
| **Batch Engine** | Node.js + TypeScript | Math-heavy scoring, team flexibility |
| **Database** | PostgreSQL 16 | Relational, JSONB, proven at scale |
| **Cache** | Redis 7 | Session tokens, driver locations, restaurant cache |
| **Search** | OpenSearch 2.14 | Full-text restaurant and menu search |
| **NoSQL** | DynamoDB (Local) | Delivery location history |
| **Messaging** | AWS SQS + SNS | Async event bus between services |
| **Object Storage** | AWS S3 + CloudFront | Restaurant images, user avatars |
| **Auth** | JWT + Cognito + Google + Apple + OTP | Multi-provider authentication |
| **Payments USA** | Stripe | Cards, Apple Pay, Google Pay |
| **Payments India** | Razorpay | Cards, UPI, net banking |
| **Push Notifications** | Firebase FCM | iOS + Android push |
| **SMS** | Twilio | OTP verification, order updates |
| **Email** | SendGrid | Order confirmation, receipts |
| **API Gateway** | Kong 3.7 | Declarative routing, rate limiting |
| **IaC** | Terraform (15 modules) | VPC, ECS, RDS, Redis, ALB, etc. |
| **CI/CD** | GitHub Actions | Lint, test, build, deploy on merge to main |
| **Containers** | Docker + ECS Fargate | Serverless container orchestration |

---

## 4. Service Catalog

| Service | Port | Language | Database | Key Responsibility |
|---------|------|----------|----------|--------------------|
| **user-svc** | 8001 | Python | PostgreSQL + Redis | Auth, profiles, loyalty, OTP |
| **restaurant-svc** | 8002 | Python | PostgreSQL + Redis + OpenSearch | Menus, search, reviews, images |
| **order-svc** | 8003 | Python | PostgreSQL + Redis | Order lifecycle, state machine, events |
| **delivery-svc** | 8004 | Python | Redis + DynamoDB | GPS tracking, WebSocket, ETA |
| **payment-svc** | 8005 | Python | PostgreSQL + Redis | Stripe, Razorpay, wallet, refunds |
| **notification-svc** | 8006 | Python | PostgreSQL | Push (FCM), SMS (Twilio), email (SendGrid) |
| **batch-engine** | 8007 | Node.js | PostgreSQL + Redis | Multi-order delivery batching |

Every service has:
- `/health` endpoint with dependency checks
- `/docs` Swagger UI (FastAPI auto-generated) or equivalent
- Structured JSON logging (structlog / custom logger)
- Alembic migrations (Python) or SQL migrations (Node.js)
- Dockerfile for containerized deployment
- Unit tests with 80%+ coverage target

---

## 5. User Service

**Port:** 8001 | **Tech:** FastAPI + SQLAlchemy + Redis + Twilio

### What It Does
Handles everything about users: registration, login, JWT tokens, social login (Google/Apple), phone OTP verification, profile management, and loyalty points.

### Data Model

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| email | string | Unique, required |
| phone | string | Optional, OTP-verified |
| full_name | string | Display name |
| hashed_password | string | bcrypt hash |
| role | enum | customer, driver, restaurant_owner, admin, super_admin, city_manager |
| is_active | bool | Account active |
| is_verified | bool | Email verified |
| loyalty_points | int | Earned from orders |
| preferred_currency | USD/INR | User's market |
| preferred_locale | string | en-US, en-IN, hi-IN |
| country | US/IN | Market identifier |

### Auth Flow

```
Register → bcrypt hash password → save user → return JWT pair
Login → verify password → generate access token (15 min) + refresh token (7 days)
Refresh → validate refresh token → issue new pair → blacklist old access token
Logout → blacklist access token in Redis
OTP → generate 6-digit code → store in Redis (10 min TTL) → send via Twilio
Social → verify Google/Apple ID token → find-or-create user → return JWT pair
```

### Endpoints (11)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | Public | Create account |
| POST | /auth/login | Public | Email + password login |
| POST | /auth/refresh | Public | Refresh JWT tokens |
| POST | /auth/logout | Auth | Invalidate tokens |
| POST | /auth/send-otp | Public | Send SMS OTP |
| POST | /auth/verify-otp | Public | Verify OTP code |
| POST | /auth/social-login | Public | Google / Apple login |
| GET | /users/me | Auth | Get own profile |
| PUT | /users/me | Auth | Update own profile |
| DELETE | /users/me | Auth | Soft-delete account |
| GET | /users/{id} | Admin | Get any user |

---

## 6. Restaurant Service

**Port:** 8002 | **Tech:** FastAPI + SQLAlchemy + OpenSearch + S3 + Redis

### What It Does
Manages restaurants, menus, menu items, categories, and reviews. Powers the search experience via OpenSearch. Handles image uploads via S3 presigned URLs. Caches restaurant listings in Redis (5 min TTL).

### Data Models

**Restaurant:** id, name, slug, owner_id, description, cuisine_types, logo_url, cover_url, address (JSONB), location (lat/lng), rating, review_count, is_open, delivery_time_min/max, minimum_order_amount, delivery_fee, currency, country, city

**MenuItem:** id, restaurant_id, name, description, price, image_url, category, is_veg, is_available, allergens (array), customizations (JSONB)

**Review:** id, restaurant_id, user_id, rating (1-5), comment, created_at

### Endpoints (10)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /restaurants | Public | List with filters (city, cuisine, rating) |
| GET | /restaurants/search | Public | OpenSearch full-text search |
| GET | /restaurants/{id} | Public | Restaurant detail |
| GET | /restaurants/{id}/menu | Public | Full menu with categories |
| POST | /restaurants | Owner | Create restaurant |
| PUT | /restaurants/{id} | Owner | Update restaurant |
| POST | /restaurants/{id}/menu-items | Owner | Add menu item |
| PUT | /restaurants/{id}/menu-items/{itemId} | Owner | Update menu item |
| DELETE | /restaurants/{id}/menu-items/{itemId} | Owner | Remove menu item |
| POST | /restaurants/{id}/reviews | Auth | Submit review |

---

## 7. Order Service

**Port:** 8003 | **Tech:** FastAPI + SQLAlchemy + SNS

### What It Does
Manages the entire order lifecycle from creation to delivery. Enforces a strict state machine. Publishes events to SNS on every status change so other services can react.

### Order State Machine

```
pending ──▶ confirmed ──▶ preparing ──▶ ready_for_pickup ──▶ picked_up ��─▶ delivered
   │                                                                          
   └──────────────────── cancelled (from any state, with reason) ◀────────────┘
```

**Who can transition:**

| Transition | Allowed By |
|------------|-----------|
| pending → confirmed | Restaurant, Admin |
| confirmed → preparing | Restaurant |
| preparing → ready_for_pickup | Restaurant |
| ready_for_pickup → picked_up | Driver |
| picked_up → delivered | Driver |
| any → cancelled | Customer (pending only), Restaurant, Admin |

### Order Data Model

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| customer_id | UUID | Who placed it |
| restaurant_id | UUID | Which restaurant |
| driver_id | UUID | Assigned driver (nullable) |
| items | JSONB | Array of {item_id, name, qty, price, customizations} |
| status | enum | State machine value |
| subtotal | decimal | Items total |
| delivery_fee | decimal | Delivery charge |
| taxes | decimal | Tax amount |
| tip | decimal | Driver tip |
| total | decimal | Final amount |
| currency | USD/INR | Market |
| delivery_address | JSONB | {street, city, state, zip, lat, lng} |
| payment_method | string | stripe / razorpay / wallet |

### Events Published

| Event | When | Who Listens |
|-------|------|------------|
| order.created | New order placed | notification-svc, batch-engine |
| order.confirmed | Restaurant accepts | batch-engine (adds to pool), notification-svc |
| order.status_changed | Any transition | notification-svc, delivery-svc |
| order.cancelled | Order cancelled | payment-svc (refund), batch-engine (remove), notification-svc |

### Endpoints (7)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /orders | Auth | Create order |
| GET | /orders | Auth | My order history |
| GET | /orders/{id} | Auth | Order detail |
| PUT | /orders/{id}/status | Role-based | Update status |
| POST | /orders/{id}/cancel | Auth | Cancel order |
| GET | /orders/restaurant/{id} | Owner | Restaurant's orders |
| GET | /orders/driver/active | Driver | Driver's current order |

---

## 8. Delivery Service

**Port:** 8004 | **Tech:** FastAPI + Redis + DynamoDB + WebSocket

### What It Does
Tracks driver locations in real-time, streams updates to customers via WebSocket, calculates ETAs, and stores delivery history in DynamoDB.

### How Real-Time Tracking Works

```
Driver app                  delivery-svc                     Customer web/mobile
    │                            │                                   │
    │  POST /driver/location     │                                   │
    │  {lat, lng} every 5s       │                                   │
    │ ──────────────────────────▶│                                   │
    │                            │  Store in Redis                   │
    │                            │  (key: driver:{id}:location       │
    │                            │   TTL: 30s)                       │
    │                            │                                   │
    │                            │  WS /ws/track/{orderId}           │
    │                            │◀──────────────────────────────────│
    │                            │                                   │
    │                            │  Push location update             │
    │                            │──────────────────────────────────▶│
    │                            │  {lat, lng, eta, status}          │
```

### Endpoints (4 REST + 1 WebSocket)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /delivery/driver/location | Driver | Update GPS (every 5s) |
| GET | /delivery/driver/active-order | Driver | Current delivery info |
| POST | /delivery/assign | Admin | Assign driver to order |
| GET | /delivery/{orderId}/eta | Auth | Get ETA |
| WS | /ws/track/{orderId}?token=JWT | Auth | Real-time location stream |

---

## 9. Payment Service

**Port:** 8005 | **Tech:** FastAPI + SQLAlchemy + Stripe + Razorpay

### What It Does
Routes payments to the correct provider based on country (Stripe for USA, Razorpay for India). Manages an in-app wallet with top-up, deduction, and refund. Handles webhook verification from both providers.

### Payment Flow

```
Customer places order
    │
    ▼
POST /payments/initiate
    │
    ├── Country = US ──▶ Stripe PaymentIntent ──▶ customer pays ──▶ Stripe webhook ──▶ payment.succeeded
    │
    └── Country = IN ──▶ Razorpay Order ──▶ customer pays ──▶ Razorpay webhook ──▶ payment.captured
                                                                        │
                                                                        ▼
                                                              order-svc confirms order
```

### Wallet Model

| Field | Type | Description |
|-------|------|-------------|
| user_id | UUID | Wallet owner |
| balance | decimal | Current balance |
| currency | USD/INR | Wallet currency |

**Wallet transactions** are a ledger (append-only): top-up, deduction, refund, cashback.

### Endpoints (8)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /payments/initiate | Auth | Start payment (auto-routes by country) |
| POST | /payments/stripe/webhook | Public | Stripe event handler |
| POST | /payments/razorpay/webhook | Public | Razorpay event handler |
| GET | /payments/{orderId} | Auth | Payment details |
| POST | /payments/{orderId}/refund | Admin | Issue refund |
| POST | /payments/wallet/topup | Auth | Add money to wallet |
| GET | /payments/wallet/balance | Auth | Check balance |
| GET | /payments/wallet/transactions | Auth | Transaction history |

---

## 10. Notification Service

**Port:** 8006 | **Tech:** FastAPI + SQLAlchemy + FCM + Twilio + SendGrid + SQS

### What It Does
Listens to all domain events via SQS and dispatches notifications through the right channel. Supports three channels: push (FCM), SMS (Twilio), and email (SendGrid). Templates are per-event and per-locale.

### Event → Notification Mapping

| Event | Push | SMS | Email |
|-------|------|-----|-------|
| order.confirmed | "Your order is confirmed!" | - | Order confirmation receipt |
| order.status_changed (preparing) | "Restaurant is preparing..." | - | - |
| order.status_changed (picked_up) | "Driver picked up your order" | - | - |
| order.status_changed (delivered) | "Order delivered!" | - | Delivery receipt |
| order.cancelled | "Your order was cancelled" | - | Cancellation notice |
| payment.succeeded | - | - | Payment receipt |
| payment.failed | "Payment failed" | SMS alert | - |

### Endpoints (4)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /notifications/device-token | Auth | Register FCM token |
| DELETE | /notifications/device-token | Auth | Unregister token |
| GET | /notifications | Auth | Notification inbox |
| PUT | /notifications/{id}/read | Auth | Mark as read |

---

## 11. Batch Delivery Engine

**Port:** 8007 | **Tech:** Node.js + TypeScript + Express + PostgreSQL

### What It Does
Groups nearby orders into batches for a single driver trip. Runs a scoring cycle every 30 seconds. Reduces delivery cost by 15-40% while keeping customer wait time within 8 minutes.

### How Batching Works (30-second cycle)

```
1. Pull all "waiting" orders from pool
2. Group by pickup proximity (restaurants within 1.5 km)
3. Within each group, try all 2-order and 3-order combos
4. For each combo: optimize the route (best stop sequence)
5. Score each candidate (distance saving, time saving, detour penalty)
6. Greedily select highest-scoring non-overlapping batches
7. Orders waiting too long → forced to solo delivery
```

### Scoring Formula

```
Score (0-100) = 0.30 × DistanceSavings
              + 0.25 × TimeSavings
              + 0.20 × (100 - DetourPenalty)
              + 0.15 × PriorityProtection
              + 0.10 × CapacityFit
```

### Key Rules

| Rule | Value |
|------|-------|
| Max orders per batch | 3 |
| Max pickup radius | 1.5 km (USA), 1.0 km (India) |
| Max delivery radius | 3.0 km (USA), 2.0 km (India) |
| Max detour per customer | 8 minutes |
| Min savings to batch | 15% |
| Priority orders | Never batched |

### Endpoints (7)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /batch/pool | Service | Add order to pool |
| GET | /batch/pending | Auth | List pending batches |
| GET | /batch/{id} | Auth | Batch details + route |
| POST | /batch/{id}/accept | Driver | Accept batch |
| POST | /batch/{id}/stops/{seq}/complete | Driver | Mark stop done |
| POST | /batch/{id}/orders/{orderId}/remove | Auth | Remove order |
| POST | /batch/engine/cycle | Admin | Manual trigger |

> Full design details: see `docs/BATCH_ENGINE_TECHNICAL_DESIGN.md`

---

## 12. Web App

**Path:** `apps/web` | **Tech:** Next.js 14 (App Router) + TypeScript + Tailwind + Zustand + React Query

### Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Landing | Hero, featured restaurants, how it works |
| `/login` | Login | Email/password + Google + Apple |
| `/signup` | Register | Registration + phone OTP |
| `/restaurants` | Browse | Restaurant listing with filters |
| `/restaurants/[slug]` | Detail | Menu, reviews, add to cart |
| `/cart` | Cart | Items, customizations, promo codes |
| `/checkout` | Checkout | Address, payment, order summary |
| `/orders` | History | Past orders |
| `/orders/[id]` | Tracking | Real-time map + WebSocket tracking |
| `/profile` | Profile | User info, addresses, loyalty |
| `/wallet` | Wallet | Balance, top-up, transactions |

### Key Features
- **i18n:** next-intl with en-US, en-IN, hi-IN locales
- **Currency:** USD / INR formatting
- **Dark mode:** Tailwind `dark:` classes
- **SEO:** metadata, OpenGraph, sitemap.xml, robots.txt
- **State:** Zustand (auth, cart), React Query (server data)
- **Maps:** Google Maps for delivery tracking

---

## 13. Mobile App

**Path:** `apps/mobile` | **Tech:** Expo 51 + React Native + NativeWind + expo-router

### Screens

| Route | Screen | Description |
|-------|--------|-------------|
| (auth)/login | Login | Email + Google + Apple |
| (auth)/signup | Register | Registration + OTP |
| (tabs)/home | Home | Restaurant discovery |
| (tabs)/search | Search | Search restaurants + items |
| (tabs)/orders | Orders | History + active tracking |
| (tabs)/profile | Profile | Settings, wallet, loyalty |
| restaurant/[id] | Detail | Restaurant menu |
| cart | Cart | Checkout flow |
| order/[id] | Tracking | Real-time map (react-native-maps) |
| wallet | Wallet | Balance + top-up |

### Native Features
- **GPS:** expo-location for location permissions
- **Push:** expo-notifications for FCM registration
- **Secure storage:** expo-secure-store for JWT tokens
- **Maps:** react-native-maps for tracking
- **Offline:** cached data when network unavailable

---

## 14. Admin Dashboard

**Path:** `apps/admin` | **Tech:** Next.js 14 + TypeScript + Tailwind + Chart.js

### Pages

| Route | Page | Access |
|-------|------|--------|
| /login | Admin login | Public |
| /dashboard | KPIs | Admin, City Manager |
| /orders | Order management | Admin, City Manager, Support |
| /restaurants | Restaurant management | Admin, City Manager |
| /users | User management | Admin |
| /drivers | Driver management | Admin, City Manager |
| /payments | Payment transactions | Admin |
| /analytics | Revenue charts, heatmaps | Admin |

### Role-Based Access

| Role | Scope |
|------|-------|
| super_admin | Everything |
| admin | Everything |
| city_manager | Own city only |
| support | Read-only + refunds |

---

## 15. Shared Packages

### packages/types (11 files)
Shared TypeScript interfaces used by all 3 frontend apps.

| File | Types Defined |
|------|--------------|
| user.ts | User, UserRole, AuthTokens, RegisterInput, LoginInput, SocialLoginInput |
| restaurant.ts | Restaurant, MenuItem, MenuCategory, Review |
| order.ts | Order, OrderItem, OrderStatus (state machine) |
| delivery.ts | DriverLocation, DeliveryTracking, GeoPoint |
| payment.ts | PaymentIntent, PaymentMethod, Wallet, WalletTransaction |
| notification.ts | Notification, DeviceToken |
| events.ts | DomainEvent (typed union for all SNS/SQS events) |
| api.ts | ApiResponse, PaginationMeta |

### packages/ui (10 files)
Shared React component library — used by both web and admin apps.

| Component | Props | Features |
|-----------|-------|----------|
| Button | variant, size, loading, disabled | Primary/secondary/ghost variants |
| Card | children, className | Dark mode, hover states |
| Badge | variant, children | Status badges (green/yellow/red) |
| Input | label, error, type | Form input with validation styling |
| Modal | open, onClose, title | Accessible dialog (aria attributes) |
| Spinner | size | Loading indicator |

### packages/config (6 files)
Shared ESLint, TypeScript, and Prettier configuration.

---

## 16. Database Architecture

### Schema Strategy
Single PostgreSQL 16 instance, separate schemas per service:

```
bhojango (database)
├── user_svc (schema)        ← user-svc owns this
├── restaurant_svc (schema)  ← restaurant-svc owns this
├── order_svc (schema)       ← order-svc owns this
├── payment_svc (schema)     ← payment-svc owns this
├── notification_svc (schema)← notification-svc owns this
├── delivery_svc (schema)    ← (placeholder, uses Redis/DynamoDB)
└── batch_engine (schema)    ← batch-engine owns this
```

### Key Tables Per Service

| Service | Tables |
|---------|--------|
| user-svc | users |
| restaurant-svc | restaurants, menu_categories, menu_items, reviews |
| order-svc | orders |
| payment-svc | payment_intents, wallets, wallet_transactions |
| notification-svc | notifications, device_tokens |
| batch-engine | order_pool, batches, batch_orders, route_stops, batch_events, batch_metrics_daily |

### Redis Usage (by DB number)

| DB | Service | What's Stored |
|----|---------|--------------|
| 0 | user-svc | JWT blacklist, OTP codes, sessions |
| 1 | restaurant-svc | Restaurant listing cache (5 min TTL) |
| 2 | order-svc | Order status cache |
| 3 | delivery-svc | Driver locations (30s TTL) |
| 4 | payment-svc | Idempotency keys |
| 5 | notification-svc | (reserved) |
| 6 | batch-engine | (reserved for driver cache) |

---

## 17. Event-Driven Architecture

### SNS Topics

| Topic | Publisher | Purpose |
|-------|----------|---------|
| bhojango-order-events | order-svc | Order lifecycle events |
| bhojango-payment-events | payment-svc | Payment success/failure |
| bhojango-batch-events | batch-engine | Batch lifecycle events |

### SQS Queues

| Queue | Subscriber | Receives From |
|-------|-----------|---------------|
| bhojango-notifications | notification-svc | order-events + payment-events |
| bhojango-order-events | order-svc | payment-events (auto-confirm) |
| bhojango-batch-events | batch-engine | order-events (add to pool) |

### Event Flow Diagram

```
Customer places order
    │
    ▼
order-svc: order.created ──SNS──▶ notification-svc (push: "Order received!")
    │                              batch-engine (add to pool)
    ▼
Restaurant confirms
    │
    ▼
order-svc: order.confirmed ──SNS──▶ batch-engine (eligible for batching)
                                     notification-svc (push: "Order confirmed!")
    │
    ▼
payment-svc: payment.succeeded ──SNS──▶ order-svc (auto-confirm order)
                                          notification-svc (email receipt)
    │
    ▼
batch-engine: batch.formed ──SNS──▶ delivery-svc (find driver)
    │
    ▼
Driver delivers
    │
    ▼
order-svc: order.delivered ──SNS──▶ notification-svc (push + email receipt)
```

---

## 18. API Gateway

### Kong Configuration

Kong runs in declarative (DB-less) mode with config at `infra/kong/kong.yml`.

| Service | Kong Route | Upstream |
|---------|-----------|----------|
| user-svc | /api/v1/auth/*, /api/v1/users/* | http://user-svc:8001 |
| restaurant-svc | /api/v1/restaurants/*, /api/v1/search/* | http://restaurant-svc:8002 |
| order-svc | /api/v1/orders/* | http://order-svc:8003 |
| delivery-svc | /api/v1/delivery/*, /ws/* | http://delivery-svc:8004 |
| payment-svc | /api/v1/payments/*, /api/v1/wallet/* | http://payment-svc:8005 |
| notification-svc | /api/v1/notifications/* | http://notification-svc:8006 |
| batch-engine | /api/v1/batch/* | http://batch-engine:8007 |

### Global Plugins
- **CORS** — allows localhost:3000, localhost:3001
- **Rate limiting** — per-service limits (30-120 req/min)
- **Request ID** — X-Request-ID header on every request

---

## 19. Complete API Reference

### Summary: 52 Endpoints

| Service | Endpoints | Auth Types |
|---------|-----------|-----------|
| user-svc | 11 | Public (7), Auth (3), Admin (1) |
| restaurant-svc | 10 | Public (4), Auth (1), Owner (5) |
| order-svc | 7 | Auth (4), Role-based (2), Driver (1) |
| delivery-svc | 5 | Driver (2), Admin (1), Auth (1), WS Auth (1) |
| payment-svc | 8 | Auth (5), Public (2, webhooks), Admin (1) |
| notification-svc | 4 | Auth (4) |
| batch-engine | 7 | Service (1), Auth (3), Driver (2), Admin (1) |

> Full endpoint details are in Sections 5-11 above.

---

## 20. Authentication & Authorization

### JWT Token Structure

```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "customer",
  "country": "US",
  "type": "access",
  "iat": 1712300000,
  "exp": 1712300900,
  "jti": "unique-token-id"
}
```

### Token Lifecycle

| Token | Lifetime | Storage |
|-------|----------|---------|
| Access token | 15 minutes | Client memory (web), SecureStore (mobile) |
| Refresh token | 7 days (web), 30 days (mobile) | HttpOnly cookie (web), SecureStore (mobile) |

### Auth Env Var (all services)

```
JWT_SECRET=<shared-secret-across-all-services>
JWT_ALGORITHM=HS256
```

### Social Login Support

| Provider | ID Token Verification | Supported Platforms |
|----------|----------------------|---------------------|
| Google | `google-auth` library, verifies against Google certs | Web, Mobile, Admin |
| Apple | Apple public key verification | Mobile (iOS), Web |

---

## 21. Infrastructure (Terraform)

### 15 Terraform Modules

| Module | Resources Created |
|--------|-------------------|
| **vpc** | VPC, 3 AZs, public/private/database subnets, NAT gateways, route tables |
| **security_groups** | ALB SG, ECS SG, RDS SG, Redis SG, OpenSearch SG |
| **kms** | KMS key with rotation for encryption at rest |
| **ecr** | Docker image repositories per service |
| **rds** | PostgreSQL 16 (Multi-AZ in prod), auto-scaling storage, Secrets Manager |
| **redis** | ElastiCache Redis 7 (cluster mode in prod), TLS, auth token |
| **opensearch** | OpenSearch 2.14, zone-aware in prod, VPC-deployed |
| **sqs_sns** | 3 SNS topics, 2 SQS queues, DLQs, cross-subscriptions |
| **s3** | Uploads (versioned), Assets (CloudFront CDN), Logs (Glacier lifecycle) |
| **cognito** | User pool, Google/Apple IdPs, web + mobile clients |
| **secrets** | Secrets Manager for JWT, Stripe, Razorpay, Twilio, SendGrid, Firebase |
| **iam** | ECS execution + task roles with least-privilege policies |
| **alb** | ALB, HTTPS listener, per-service target groups, path-based routing |
| **ecs** | Fargate cluster, 7 task definitions, auto-scaling (2-10 tasks in prod) |
| **cloudwatch** | Log groups, dashboard (6 widgets), CPU + 5xx + RDS alarms |

### Deployment Commands

```bash
cd infra/terraform
terraform init
terraform plan -var="environment=prod" -var="certificate_arn=arn:aws:acm:..."
terraform apply
```

---

## 22. CI/CD Pipeline

### On Push to `main` (ci.yml)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. FRONTEND (parallel)                                       │
│    pnpm install → lint → typecheck → build                   │
├─────────────────────────────────────────────────────────────┤
│ 2. BACKEND (parallel, 7 services)                            │
│    pip install → pytest (80% coverage) per service           │
├─────────────────────────────────────────────────────────────┤
│ 3. BUILD + PUSH (parallel, 7 services)                       │
│    Docker build → push to ECR with :latest and :sha tags     │
├──────────────���──────────────────────────────────────────────┤
│ 4. DEPLOY (max 2 parallel)                                   │
│    aws ecs update-service → wait for stable                  │
└���────────────────────────────────────────────────────────────┘
```

### On Pull Request (pr-checks.yml)

```
1. Detect which files changed (frontend? backend? terraform?)
2. Run only relevant checks:
   - Frontend changes → lint + typecheck
   - Backend changes → pytest per changed service + Docker build
   - Terraform changes → terraform fmt + validate
3. All checks must pass to merge
```

---

## 23. Local Development Setup

### Prerequisites

| Tool | Version |
|------|---------|
| Node.js | >= 20 |
| pnpm | >= 9 |
| Python | >= 3.12 |
| Docker Desktop | latest |

### Quick Start (5 commands)

```bash
# 1. Install frontend dependencies
pnpm install

# 2. Copy environment file
cp .env.example .env

# 3. Start all infrastructure + services
docker compose up -d

# 4. Run database migrations
for svc in user-svc restaurant-svc order-svc payment-svc notification-svc; do
  cd services/$svc && alembic upgrade head && cd ../..
done
psql $DATABASE_URL -f services/batch-engine/src/db/migrations/001_create_batch_tables.sql

# 5. Start frontend dev servers
pnpm dev
```

### Local URLs

| Service | URL |
|---------|-----|
| Web App | http://localhost:3000 |
| Admin Dashboard | http://localhost:3001 |
| Kong Gateway | http://localhost:8888 |
| All API docs | http://localhost:800{1-7}/docs |
| Adminer (DB UI) | http://localhost:8080 |
| Kong Admin | http://localhost:8444 |

### Docker Compose Services (14 containers)

| Container | Purpose |
|-----------|---------|
| postgres | PostgreSQL 16 |
| redis | Redis 7 |
| opensearch | OpenSearch 2.14 |
| dynamodb-local | DynamoDB for delivery history |
| localstack | SQS + SNS + S3 |
| adminer | Database UI |
| kong | API Gateway |
| user-svc through notification-svc | 6 Python services |
| batch-engine | Node.js batch service |

---

## 24. Observability & Monitoring

### Logging
- All Python services use **structlog** (JSON in production, pretty in dev)
- Batch engine uses custom JSON logger
- Every log entry has: timestamp, level, service, message, + context

### Health Checks
Every service exposes `GET /health` returning:
```json
{
  "status": "healthy",
  "service": "user-svc",
  "version": "0.1.0",
  "uptime": 86400,
  "checks": { "database": "ok", "redis": "ok" }
}
```

### Metrics (via Prometheus)
Python services expose `GET /metrics` (prometheus-fastapi-instrumentator):
- Request count, latency histograms
- In-flight requests

### CloudWatch Dashboard
- Per-service CPU and memory utilization
- RDS CPU and connection count
- Redis hit/miss rate
- ALB request count, latency, 5xx errors

### Alerting
- CPU > 80% on any ECS service → SNS alert
- ALB 5xx > 10/min → SNS alert
- RDS CPU > 80% → SNS alert
- Batch engine cycle errors > 0 → SNS alert

---

## 25. Security

| Area | Implementation |
|------|----------------|
| **Auth** | JWT with 15-min expiry, bcrypt passwords, token blacklisting |
| **API access** | All traffic through Kong gateway |
| **Secrets** | AWS Secrets Manager (never in code or env files) |
| **Encryption at rest** | KMS key for RDS, S3, SQS, SNS, CloudWatch |
| **Encryption in transit** | TLS 1.2+ on ALB, Redis auth + TLS, OpenSearch HTTPS |
| **SQL injection** | Parameterized queries (SQLAlchemy ORM, node-pg $1 params) |
| **Input validation** | Pydantic v2 on all FastAPI endpoints, custom validators on batch-engine |
| **CORS** | Restricted to app domains |
| **Rate limiting** | Kong rate-limiting plugin per service |
| **Webhook verification** | Stripe signature verification, Razorpay signature verification |
| **IAM** | Least-privilege ECS task roles (can only access own resources) |
| **Network** | Private subnets for services, public only for ALB |
| **PII** | No customer PII in logs; coordinates only in batch tables |

---

## 26. End-to-End User Flows

### Flow 1: Customer Orders Food

```
1. Customer opens app → GET /restaurants?city=NYC
2. Selects restaurant → GET /restaurants/{id}/menu
3. Adds items to cart (local state — Zustand)
4. Goes to checkout → POST /orders (creates order, status = pending)
5. Pays → POST /payments/initiate (routes to Stripe/Razorpay)
6. Payment succeeds → webhook → order confirmed → batch-engine adds to pool
7. Batch engine forms batch → delivery-svc finds driver
8. Driver accepts → POST /batch/{id}/accept
9. Customer tracks → WS /ws/track/{orderId} (real-time GPS)
10. Driver picks up → POST /batch/{id}/stops/1/complete
11. Driver delivers → POST /batch/{id}/stops/2/complete
12. Push notification: "Your order has been delivered!"
```

### Flow 2: Restaurant Owner Manages Menu

```
1. Owner logs in → POST /auth/login (role = restaurant_owner)
2. Views orders → GET /orders/restaurant/{id}
3. Accepts order → PUT /orders/{id}/status (pending → confirmed)
4. Updates menu → PUT /restaurants/{id}/menu-items/{id}
5. Adds new item �� POST /restaurants/{id}/menu-items
```

### Flow 3: Admin Handles Refund

```
1. Admin logs in ��� POST /auth/login (role = admin)
2. Finds order → GET /orders/{id}
3. Issues refund → POST /payments/{id}/refund
4. Customer notified via push + email
```

---

## 27. What's Done vs What's Next

### Done (Implemented)

| Area | Status | Files |
|------|--------|-------|
| Monorepo scaffold (Turborepo + pnpm) | Done | 6 root files |
| User service (auth, profiles, OTP, social login) | Done | 35 files |
| Restaurant service (menus, search, reviews, S3) | Done | 27 files |
| Order service (state machine, SNS events) | Done | 27 files |
| Delivery service (GPS, WebSocket, ETA, DynamoDB) | Done | 19 files |
| Payment service (Stripe, Razorpay, wallet) | Done | 27 files |
| Notification service (FCM, Twilio, SendGrid, SQS) | Done | 28 files |
| Batch delivery engine (scoring, routing, batching) | Done | 24 files |
| Next.js web app (11 pages, i18n, dark mode) | Done | 32 files |
| Expo mobile app (10 screens, maps, push) | Done | 21 files |
| Admin dashboard (8 pages, RBAC, charts) | Done | 18 files |
| Shared types, UI components, config | Done | 27 files |
| Terraform (15 modules, 48 .tf files) | Done | 51 files |
| Docker Compose (14 containers) | Done | 1 file |
| Kong API Gateway (declarative config) | Done | 1 file |
| GitHub Actions CI/CD (2 workflows) | Done | 2 files |
| Documentation (README, CONTRIBUTING, TDDs) | Done | 4 files |

### Not Yet Done (Dev Team Next Steps)

See Section 28 below.

---

## 28. Dev Team Next Steps

### Priority 1 — Before Go-Live (Week 1-2)

| # | Task | Owner | Effort | Notes |
|---|------|-------|--------|-------|
| 1 | **Provision AWS accounts** and run `terraform apply` | DevOps | 2 days | See Section 21 |
| 2 | **Set up external accounts**: Stripe, Razorpay, Twilio, SendGrid, Firebase, Google OAuth, Apple Sign-In | DevOps | 2 days | Get production API keys |
| 3 | **Run full E2E test** on Docker Compose locally | QA | 2 days | Register → order → pay → track → deliver |
| 4 | **Load testing** on key endpoints (order creation, payment, search) | Backend | 2 days | Use k6 or Artillery, target 500 req/s |
| 5 | **Domain + SSL** — purchase domain, set up Route 53, ACM cert | DevOps | 1 day | Required for ALB HTTPS |
| 6 | **Update webhook URLs** in Stripe + Razorpay dashboards | Backend | 1 hour | Point to production ALB |
| 7 | **Seed test data** — create sample restaurants, menu items, users for each market | Backend | 1 day | Scripts or admin API |

### Priority 2 — Quality & Polish (Week 2-3)

| # | Task | Owner | Effort | Notes |
|---|------|-------|--------|-------|
| 8 | **Write integration tests** for all services | Backend | 3 days | Focus on order flow, payment webhooks |
| 9 | **Add Sentry** error tracking to all services + frontends | Full-stack | 1 day | Configure DSN per service |
| 10 | **Implement token blacklist check** in all downstream services | Backend | 1 day | Currently only user-svc checks Redis blacklist |
| 11 | **Add refresh token logic** to admin dashboard | Frontend | 0.5 day | Currently logs out on expiry instead of refreshing |
| 12 | **Add UPI payment option** for India market | Frontend + Backend | 1 day | Razorpay supports UPI natively |
| 13 | **Expo build** — create iOS and Android builds, test on real devices | Mobile | 2 days | EAS Build for both platforms |
| 14 | **Error boundaries** in all React apps | Frontend | 0.5 day | Graceful error screens |

### Priority 3 — Launch (Week 3-4)

| # | Task | Owner | Effort | Notes |
|---|------|-------|--------|-------|
| 15 | **Deploy to production** — merge to main, CI/CD pushes to ECS | DevOps | 1 day | Monitor CloudWatch during deploy |
| 16 | **Batch engine shadow mode** — enable in 1 city, log but don't assign | Backend | 0.5 day | Set `MAX_ORDERS_PER_BATCH=1` initially |
| 17 | **Submit mobile apps** to App Store + Play Store | Mobile | 1 day | Allow 1-2 weeks for review |
| 18 | **Set up PagerDuty / OpsGenie** for alerting | DevOps | 0.5 day | Subscribe to CloudWatch SNS topic |
| 19 | **Soft launch** — 1 city, invite-only, monitor all metrics | Product + Eng | Ongoing | Watch NPS, delivery times, error rates |

### Priority 4 — Post-Launch (Month 2+)

| # | Task | Owner | Effort | Notes |
|---|------|-------|--------|-------|
| 20 | **Enable batch engine** in pilot city | Backend | 0.5 day | Remove shadow mode, real driver assignment |
| 21 | **Add customer batch opt-in** at checkout ("Save $1") | Frontend + Backend | 2 days | A/B test conversion |
| 22 | **Google Routes API** integration for real traffic-aware ETAs | Backend | 3 days | Replace haversine estimates |
| 23 | **ML-based scoring** for batch engine | Data/ML | 2 weeks | Learn from actual delivery data |
| 24 | **Expand to 5 cities** per market | Product + Ops | Ongoing | Tune per-city config |
| 25 | **Grocery vertical** — extend batch engine for larger batches | Backend | 1 week | New batch profile, higher capacity |
| 26 | **Driver incentive system** — bonus for multi-order batches | Backend + Product | 3 days | Per-extra-order payment |
| 27 | **Analytics dashboards** — Grafana or Metabase for business metrics | Data | 1 week | Revenue, orders/day, top restaurants |

---

### External Accounts Checklist

Before anything runs in production, the team needs these accounts:

| Account | What You Need | Where to Sign Up |
|---------|--------------|------------------|
| **AWS** | Account with billing, IAM deploy role | aws.amazon.com |
| **Stripe** | Production API keys (US market) | dashboard.stripe.com |
| **Razorpay** | Production API keys (India market) | dashboard.razorpay.com |
| **Twilio** | Account SID, auth token, US + India phone numbers | twilio.com |
| **SendGrid** | API key, verified sender domain | sendgrid.com |
| **Firebase** | FCM project, service account JSON | console.firebase.google.com |
| **Google Cloud** | OAuth 2.0 client ID + secret, Maps API key | console.cloud.google.com |
| **Apple Developer** | Sign In with Apple (service ID, team ID, key) | developer.apple.com |
| **Google Play** | Developer account ($25) | play.google.com/console |
| **Apple App Store** | Developer account ($99/yr) | developer.apple.com |
| **Sentry** | Error tracking DSN | sentry.io |
| **Domain registrar** | bhojango.com (or similar) | Any registrar |

### Estimated Monthly Infrastructure Cost

| Service | Cost |
|---------|------|
| ECS Fargate (7 services × 2 tasks) | $200-400 |
| RDS PostgreSQL (Multi-AZ) | $300-400 |
| ElastiCache Redis | $200-300 |
| OpenSearch | $300-400 |
| ALB + data transfer | $50-100 |
| S3 + CloudFront | $20-50 |
| SQS/SNS | $5-10 |
| **Total infrastructure** | **$1,100-1,700/mo** |

---

*End of Platform Technical Design Document*

*For batch engine deep-dive, see: `docs/BATCH_ENGINE_TECHNICAL_DESIGN.md`*
*For contribution guidelines, see: `CONTRIBUTING.md`*
*For local setup, see: `README.md`*
