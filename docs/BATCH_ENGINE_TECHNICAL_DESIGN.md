# BhojanGo Batch Delivery Engine — Technical Design Document

| Field             | Value                                      |
|-------------------|--------------------------------------------|
| **Document**      | Technical Design Document (TDD)            |
| **Service**       | Batch Delivery Engine (`batch-engine`)      |
| **Version**       | 1.0                                        |
| **Date**          | April 5, 2026                              |
| **Author**        | BhojanGo Architecture Team                 |
| **Status**        | Ready for Development                      |
| **Reviewers**     | Backend Lead, DevOps Lead, Product Manager |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals and Non-Goals](#3-goals-and-non-goals)
4. [System Architecture](#4-system-architecture)
5. [Batching Rules and Business Logic](#5-batching-rules-and-business-logic)
6. [Scoring Algorithm](#6-scoring-algorithm)
7. [Route Optimization](#7-route-optimization)
8. [Database Schema](#8-database-schema)
9. [API Specification](#9-api-specification)
10. [Event Architecture](#10-event-architecture)
11. [Edge Case Handling](#11-edge-case-handling)
12. [Service Integration Map](#12-service-integration-map)
13. [Configuration and Tuning](#13-configuration-and-tuning)
14. [Observability and Metrics](#14-observability-and-metrics)
15. [Phased Rollout Plan](#15-phased-rollout-plan)
16. [Implementation Guide](#16-implementation-guide)
17. [Testing Strategy](#17-testing-strategy)
18. [Performance and Scalability](#18-performance-and-scalability)
19. [Security Considerations](#19-security-considerations)
20. [Open Questions and Future Work](#20-open-questions-and-future-work)
21. [Appendix A — Sample Request/Response Payloads](#appendix-a--sample-requestresponse-payloads)
22. [Appendix B — Full File Tree](#appendix-b--full-file-tree)
23. [Appendix C — Glossary](#appendix-c--glossary)

---

## 1. Executive Summary

The Batch Delivery Engine is a new microservice for BhojanGo that groups multiple nearby food delivery orders into a single driver trip. When orders share similar pickup locations (same or adjacent restaurants) and nearby delivery destinations, the engine assigns them to one driver instead of dispatching separate drivers for each.

**Key outcomes:**
- **15-40% reduction** in per-order delivery cost (fuel, driver time)
- **10-25% improvement** in driver utilization (more orders per hour)
- **Maintained SLA** — no customer receives their order more than 8 minutes later than a solo delivery

**Tech stack:** Node.js + TypeScript + PostgreSQL + Express + AWS SQS/SNS

**Integration:** The engine sits between `order-svc` (receives confirmed orders) and `delivery-svc` (assigns drivers to batched routes).

---

## 2. Problem Statement

### Current State
Today, every confirmed order is independently dispatched to the nearest available driver. This is simple but wasteful:
- Two orders from the same restaurant going to addresses 500m apart use two separate drivers
- Drivers deadhead (drive empty) back to restaurant areas between deliveries
- In high-density zones during peak hours, many nearby orders go out in parallel single trips

### Desired State
The system should recognize when orders can be efficiently combined and assign a single driver to pick up and deliver multiple orders in one trip, provided the grouping doesn't violate delivery time promises.

### Constraints
- Customer experience must not degrade beyond acceptable thresholds
- Priority (premium) orders must never be delayed by batching
- The system must work for both US and India markets with tunable parameters
- Must be backward-compatible — single-order delivery is just a batch of size 1

---

## 3. Goals and Non-Goals

### Goals
| ID | Goal | Success Metric |
|----|------|---------------|
| G1 | Reduce delivery cost per order | ≥15% distance savings on batched orders |
| G2 | Maintain delivery SLA | Max 8 min additional delay per order |
| G3 | Protect priority orders | 0 priority orders ever batched (unless opted in) |
| G4 | Scale to multi-vertical | Architecture supports food, grocery, parcel |
| G5 | Provide operational visibility | Real-time dashboard with batch metrics |
| G6 | Support market-specific tuning | Per-city configuration for radii, speeds, thresholds |

### Non-Goals (Out of Scope for v1)
- Global optimization across all drivers (we use greedy assignment for MVP)
- Real-time route recalculation using live traffic data
- Customer-facing UI for batch opt-in/opt-out
- Driver app changes (driver sees a multi-stop route, no new UI needed)
- Pricing adjustments (batch discount for customers)

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        order-svc (:8003)                        │
│      When order reaches "confirmed" + "preparing" status:       │
│      → Publishes "order.confirmed" event to SNS                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    SNS → SQS subscription
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  BATCH ENGINE (:8007)                            │
│                                                                  │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │ SQS Event   │─▶│ Order Pool │─▶│   Batch Builder Engine   │  │
│  │ Consumer    │  │ (Postgres) │  │   (runs every 30 sec)    │  │
│  └─────────────┘  └────────────┘  └─────────────┬────────────┘  │
│                                                   │              │
│                   ┌───────────────────────────────┘              │
│                   │                                              │
│          ┌────────▼────────┐                                     │
│          │ 1. Pull waiting │                                     │
│          │    orders       │                                     │
│          ├─────────────────┤                                     │
│          │ 2. Group by     │                                     │
│          │    pickup prox. │                                     │
│          ├─────────────────┤                                     │
│          │ 3. Generate     │                                     │
│          │    2/3-combos   │                                     │
│          ├─────────────────┤                                     │
│          │ 4. Route-       │                                     │
│          │    optimize     │                                     │
│          ├─────────────────┤                                     │
│          │ 5. Score each   │                                     │
│          │    candidate    │                                     │
│          ├─────────────────┤                                     │
│          │ 6. Greedy-      │                                     │
│          │    select best  │                                     │
│          └────────┬────────┘                                     │
│                   │                                              │
│  ┌────────────────▼──────────────┐  ┌─────────────────────────┐  │
│  │  Batch Repository (Postgres)  │  │  SNS Publisher          │  │
│  │  - batches table              │  │  batch.formed           │  │
│  │  - batch_orders table         │  │  batch.assigned         │  │
│  │  - route_stops table          │  │  batch.completed        │  │
│  │  - batch_events audit log     │  │  batch.order_removed    │  │
│  └───────────────────────────────┘  └─────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                  REST API (:8007)                          │   │
│  │  POST /api/v1/batch/pool          - add order to pool     │   │
│  │  GET  /api/v1/batch/pending       - list pending batches  │   │
│  │  GET  /api/v1/batch/:id           - batch details + route │   │
│  │  POST /api/v1/batch/:id/accept    - driver accepts        │   │
│  │  POST /api/v1/batch/:id/stops/:s/complete - mark done     │   │
│  │  POST /api/v1/batch/:id/orders/:oid/remove - cancel order │   │
│  │  POST /api/v1/batch/engine/cycle  - manual trigger        │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                           │
                    SNS → SQS subscription
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    delivery-svc (:8004)                          │
│     Receives "batch.formed" event → finds nearest driver        │
│     Offers batch to driver → driver accepts via batch engine    │
│     Driver follows multi-stop route with GPS tracking           │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Breakdown

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| **SQS Consumer** | Listens for order events, inserts into pool | AWS SDK, long-polling |
| **Order Pool** | Holds orders waiting for batch assignment | PostgreSQL table |
| **Batch Builder** | Core engine loop — runs every N seconds | Pure TypeScript (no I/O) |
| **Route Optimizer** | Finds best stop sequence for a batch | Exhaustive permutation (MVP) |
| **Batch Scorer** | Assigns composite score to candidate batches | Weighted scoring formula |
| **Batch Repository** | CRUD for batches, orders, routes | PostgreSQL + transactions |
| **REST API** | HTTP interface for driver ops and admin | Express.js |
| **SNS Publisher** | Broadcasts batch lifecycle events | AWS SDK |

### 4.3 Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | TypeScript (Node.js) | Fast iteration, strong typing, team familiarity |
| Database | PostgreSQL (shared instance) | Existing infra, ACID transactions for batch creation |
| Framework | Express.js | Lightweight, no overhead for a service with 7 endpoints |
| Route optimization | Custom permutation solver | Only 2-3 orders per batch = max 6 stops = tiny search space |
| Event bus | AWS SNS/SQS | Already used by order-svc and delivery-svc |
| Scheduling | setInterval (in-process) | Simple for MVP; migrate to SQS scheduled messages at scale |

---

## 5. Batching Rules and Business Logic

### 5.1 Order Lifecycle in the Batch Engine

```
order.confirmed (from order-svc)
        │
        ▼
  ┌──────────┐     max wait exceeded     ┌──────────┐
  │ WAITING  │ ──────────────────────────▶│ EXPIRED  │──▶ solo delivery
  │ in pool  │                            └──────────┘
  └────┬─────┘
       │ batch cycle matches it
       ▼
  ┌──────────┐     driver accepts     ┌──────────┐
  │ BATCHED  │ ─────────────────────▶ │ ASSIGNED │
  └──────────┘                        └────┬─────┘
                                           │ first pickup
                                           ▼
                                     ┌─────────────┐
                                     │ IN PROGRESS  │
                                     └──────┬──────┘
                                            │ all delivered
                                            ▼
                                     ┌───────────┐
                                     │ COMPLETED  │
                                     └───────────┘

  At any point, an order can be CANCELLED → removed from batch
  If last order is cancelled → batch status = FAILED
```

### 5.2 Batching Eligibility Rules

An order is eligible for batching if ALL of the following are true:

| # | Rule | Check |
|---|------|-------|
| 1 | **Status is "waiting"** | `order_pool.status = 'waiting'` |
| 2 | **Not expired** | `now() - created_at < MAX_WAIT_IN_POOL_MINUTES` |
| 3 | **Not priority** (unless configured) | `priority != 'priority'` OR `PRIORITY_ORDER_BATCHABLE = true` |
| 4 | **Pickup proximity** | Pickup point within `MAX_PICKUP_RADIUS_KM` of at least one other order |
| 5 | **Delivery proximity** | Delivery point within `MAX_DELIVERY_RADIUS_KM` of other orders in batch |
| 6 | **Prep time alignment** | `prep_ready_at` within 10 minutes of other orders (driver won't wait too long) |
| 7 | **Capacity fit** | Total `estimated_size_liters` ≤ driver bag capacity |

### 5.3 Configurable Thresholds

| Parameter | Default | India Override | Description |
|-----------|---------|---------------|-------------|
| `BATCH_CYCLE_SECONDS` | 30 | 20 | How often the engine runs |
| `MAX_ORDERS_PER_BATCH` | 3 | 3 | Max orders per driver trip |
| `MAX_PICKUP_RADIUS_KM` | 1.5 | 1.0 | Restaurants must be this close |
| `MAX_DELIVERY_RADIUS_KM` | 3.0 | 2.0 | Customers must be this close |
| `MAX_DETOUR_MINUTES` | 8 | 6 | Max extra time for any one customer |
| `MAX_EXTRA_DELAY_MINUTES` | 5 | 4 | Max delay past promised time |
| `MAX_WAIT_IN_POOL_MINUTES` | 5 | 3 | Auto-escalate to solo after this |
| `MIN_SAVINGS_PERCENT` | 15 | 15 | Don't batch unless we save this much |
| `AVERAGE_SPEED_KMH` | 25 | 20 | City driving speed for estimates |

---

## 6. Scoring Algorithm

### 6.1 Composite Score Formula

Each candidate batch receives a score from 0–100. Higher is better.

```
Score = W1 × DistanceSavings
      + W2 × TimeSavings
      + W3 × DetourPenalty
      + W4 × PriorityPenalty
      + W5 × CapacityFit
```

### 6.2 Weight Table

| Weight | Name | Default | Purpose |
|--------|------|---------|---------|
| W1 | `distanceSaving` | 0.30 | Reward shorter total routes |
| W2 | `timeSaving` | 0.25 | Reward faster overall completion |
| W3 | `detourPenalty` | 0.20 | Penalize customer wait increase |
| W4 | `priorityPenalty` | 0.15 | Penalize if priority orders included |
| W5 | `capacityFit` | 0.10 | Reward full utilization of driver |

### 6.3 Sub-Score Calculations

**Distance Savings Score (0-100):**
```
solo_distance = sum of (driver→pickup + pickup→delivery) for each order separately
batch_distance = optimized multi-stop route distance
savings_pct = (solo_distance - batch_distance) / solo_distance × 100
score = normalize(savings_pct, 0, 50)   // 50% savings = perfect 100
```

**Time Savings Score (0-100):**
```
solo_time = sum of individual delivery times
batch_time = optimized route time
savings_pct = (solo_time - batch_time) / solo_time × 100
score = normalize(savings_pct, 0, 40)
```

**Detour Penalty Score (0-100):**
```
max_detour = maximum extra wait time for any single customer
score = 100 - normalize(max_detour, 0, MAX_DETOUR_MINUTES)
// 0 min detour = 100 (perfect), MAX_DETOUR = 0 (terrible)
```

**Priority Penalty Score:**
```
if batch contains priority orders → score = 20 (harsh penalty)
if no priority orders → score = 100
```

**Capacity Fit Score (0-100):**
```
score = normalize(order_count, 1, MAX_ORDERS_PER_BATCH)
// 3 orders in a 3-max batch = 100, 1 order = 0
```

### 6.4 Rejection Criteria

A batch candidate is **rejected** (score = 0) if:
- `savingsPercent < MIN_SAVINGS_PERCENT` (not worth the complexity)
- `maxDetourMin > MAX_DETOUR_MINUTES` (customer impact too high)
- Any order would exceed its `promised_delivery_at` by more than `MAX_EXTRA_DELAY_MINUTES`

### 6.5 Scoring Example

**Scenario:** 2 orders from adjacent restaurants in Manhattan, delivering to addresses 800m apart.

| Metric | Solo (2 trips) | Batched (1 trip) |
|--------|---------------|-----------------|
| Total distance | 8.2 km | 5.4 km |
| Total time | 42 min | 28 min |
| Max detour | 0 min | 4.2 min |
| Distance savings | — | 34.1% |

```
distScore = normalize(34.1, 0, 50) = 68.2   × 0.30 = 20.5
timeScore = normalize(33.3, 0, 40) = 83.3   × 0.25 = 20.8
detourScore = 100 - normalize(4.2, 0, 8) = 47.5  × 0.20 = 9.5
priorityScore = 100 (no priority)            × 0.15 = 15.0
capacityScore = normalize(2, 1, 3) = 50     × 0.10 = 5.0

TOTAL SCORE = 70.8 / 100   ✅ Good batch
```

---

## 7. Route Optimization

### 7.1 Problem Definition

Given N orders (each with a pickup and delivery point), find the sequence of 2N stops that:
1. Minimizes total travel time
2. Respects the constraint: `pickup(order_i)` must come before `delivery(order_i)`
3. Respects prep time: don't arrive at restaurant before food is ready

### 7.2 Algorithm Choice

| Orders | Stops | Valid Permutations | Approach |
|--------|-------|--------------------|----------|
| 1 | 2 | 1 | Trivial |
| 2 | 4 | ~6 | Exhaustive |
| 3 | 6 | ~90 | Exhaustive |
| 4+ | 8+ | ~2500+ | Heuristic (future) |

For MVP (max 3 orders), exhaustive permutation search is fast enough (<1ms).

### 7.3 Pseudocode

```
function optimizeRoute(orders[], driverStart):
    // Generate all permutations of [pickup1, pickup2, delivery1, delivery2, ...]
    // Filter: keep only where pickup(i) comes before delivery(i)
    // For each valid permutation:
    //   - Calculate total distance (haversine × 1.4 road factor)
    //   - Calculate total time (distance / avgSpeed + dwell per stop)
    //   - If pickup arrives before food ready, add wait time
    //   - Calculate per-order detour vs solo delivery
    // Return the permutation with lowest total time that meets detour constraint
```

### 7.4 Distance Calculation

```
Haversine distance → straight-line km between two lat/lng points
Road distance = haversine × 1.4 (city driving factor)
Drive time = road_distance / AVERAGE_SPEED_KMH × 60 (minutes)
```

**Future improvement:** Replace with Google Routes API or OSRM for real road distances and live traffic.

### 7.5 Dwell Time at Stops

| Stop Type | Default Dwell | Includes |
|-----------|--------------|----------|
| Pickup | 2 min | Park, walk in, collect food, walk out |
| Delivery | 3 min | Park, walk to door, hand off, walk back |

---

## 8. Database Schema

### 8.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌──────────────────┐
│   order_pool    │       │     batches      │
│─────────────────│       │──────────────────│
│ id (PK)         │       │ id (PK)          │
│ order_id (UQ)   │──────▶│ driver_id        │
│ restaurant_id   │       │ status           │
│ pickup_lat/lng  │       │ score            │
│ delivery_lat/lng│       │ est_total_dist   │
│ prep_ready_at   │       │ est_total_time   │
│ promised_deliv  │       │ max_detour_min   │
│ priority        │       │ savings_percent  │
│ status          │       │ created_at       │
│ batch_id (FK)   │──────▶│ assigned_at      │
│ created_at      │       │ completed_at     │
└─────────────────┘       └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
           ┌───────▼──────┐ ┌────▼───────┐ ┌───▼────────────┐
           │ batch_orders │ │route_stops │ │ batch_events   │
           │──────────────│ │────────────│ │────────────────│
           │ id (PK)      │ │ id (PK)    │ │ id (PK)        │
           │ batch_id(FK) │ │ batch_id   │ │ batch_id (FK)  │
           │ order_id     │ │ sequence   │ │ event_type     │
           │ sequence     │ │ stop_type  │ │ order_id       │
           │ est_pickup   │ │ order_id   │ │ driver_id      │
           │ est_delivery │ │ lat/lng    │ │ metadata(JSONB)│
           │ detour_min   │ │ est_arrival│ │ created_at     │
           │ status       │ │ dwell_min  │ └────────────────┘
           └──────────────┘ └────────────┘
```

### 8.2 Table Definitions

#### `batch_engine.order_pool`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, auto | Pool entry ID |
| order_id | UUID | UNIQUE, NOT NULL | Reference to order-svc order |
| restaurant_id | UUID | NOT NULL | Restaurant identifier |
| restaurant_name | TEXT | NOT NULL | Display name |
| pickup_lat | DOUBLE PRECISION | NOT NULL | Restaurant latitude |
| pickup_lng | DOUBLE PRECISION | NOT NULL | Restaurant longitude |
| delivery_lat | DOUBLE PRECISION | NOT NULL | Customer latitude |
| delivery_lng | DOUBLE PRECISION | NOT NULL | Customer longitude |
| prep_ready_at | TIMESTAMPTZ | NOT NULL | When food will be ready |
| promised_delivery_at | TIMESTAMPTZ | NOT NULL | SLA promise to customer |
| priority | VARCHAR(20) | DEFAULT 'standard' | standard / priority / scheduled |
| item_count | INTEGER | DEFAULT 1 | Number of items |
| estimated_size_liters | REAL | DEFAULT 5.0 | Volume for capacity check |
| currency | VARCHAR(3) | DEFAULT 'USD' | USD / INR |
| delivery_fee | NUMERIC(10,2) | DEFAULT 0 | Fee charged to customer |
| status | VARCHAR(20) | DEFAULT 'waiting' | waiting / batched / expired / cancelled |
| batch_id | UUID | FK → batches | NULL until batched |
| created_at | TIMESTAMPTZ | DEFAULT now() | When order entered pool |
| updated_at | TIMESTAMPTZ | auto-updated | Last modification |

**Indexes:**
- `idx_pool_status` — partial index on `status = 'waiting'` (hot query path)
- `idx_pool_restaurant` — for grouping by pickup proximity
- `idx_pool_created` — for expiration checks

#### `batch_engine.batches`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, auto | Batch identifier |
| driver_id | UUID | nullable | Assigned driver |
| status | VARCHAR(20) | NOT NULL | forming/pending/assigned/in_progress/completed/failed |
| score | REAL | DEFAULT 0 | Composite quality score (0-100) |
| estimated_total_distance_km | REAL | DEFAULT 0 | Total route distance |
| estimated_total_time_min | REAL | DEFAULT 0 | Total route time |
| max_detour_min | REAL | DEFAULT 0 | Worst-case customer detour |
| savings_percent | REAL | DEFAULT 0 | % savings vs solo deliveries |
| created_at | TIMESTAMPTZ | DEFAULT now() | Batch creation time |
| assigned_at | TIMESTAMPTZ | nullable | When driver accepted |
| completed_at | TIMESTAMPTZ | nullable | When all deliveries done |

#### `batch_engine.batch_orders`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, auto | Join entry ID |
| batch_id | UUID | FK → batches, NOT NULL | Parent batch |
| order_id | UUID | NOT NULL | Order reference |
| pool_order_id | UUID | FK → order_pool | Pool entry reference |
| sequence | INTEGER | NOT NULL | Position in route |
| estimated_pickup_at | TIMESTAMPTZ | NOT NULL | ETA at restaurant |
| estimated_delivery_at | TIMESTAMPTZ | NOT NULL | ETA at customer |
| detour_minutes | REAL | DEFAULT 0 | Extra time vs solo |
| actual_pickup_at | TIMESTAMPTZ | nullable | Real pickup time |
| actual_delivery_at | TIMESTAMPTZ | nullable | Real delivery time |
| status | VARCHAR(20) | DEFAULT 'pending' | pending/picked_up/delivered/cancelled |

#### `batch_engine.route_stops`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, auto | Stop ID |
| batch_id | UUID | FK → batches | Parent batch |
| sequence | INTEGER | NOT NULL | Order driver visits stops |
| stop_type | VARCHAR(10) | NOT NULL | pickup / delivery |
| order_id | UUID | NOT NULL | Which order this stop serves |
| lat | DOUBLE PRECISION | NOT NULL | Stop latitude |
| lng | DOUBLE PRECISION | NOT NULL | Stop longitude |
| estimated_arrival_at | TIMESTAMPTZ | NOT NULL | ETA at this stop |
| estimated_dwell_min | REAL | DEFAULT 2 | Time spent at stop |

#### `batch_engine.batch_events` (Audit Log)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Event ID |
| batch_id | UUID | FK → batches |
| event_type | VARCHAR(50) | batch.formed, batch.assigned, etc. |
| order_id | UUID | nullable — relevant order |
| driver_id | UUID | nullable — relevant driver |
| metadata | JSONB | Additional context |
| created_at | TIMESTAMPTZ | Event timestamp |

#### `batch_engine.batch_metrics_daily` (Analytics)

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | PK with city |
| city | VARCHAR(100) | PK with date |
| total_batches | INTEGER | Batches formed that day |
| multi_order_batches | INTEGER | Batches with 2+ orders |
| avg_batch_size | REAL | Average orders per batch |
| avg_savings_pct | REAL | Average distance savings |
| avg_detour_min | REAL | Average customer detour |
| total_distance_saved_km | REAL | Total km saved |

---

## 9. API Specification

### 9.1 Base URL

```
Development:  http://localhost:8007/api/v1/batch
Via Kong:     http://localhost:8888/api/v1/batch
Production:   https://api.bhojango.com/api/v1/batch
```

### 9.2 Endpoints

#### POST `/api/v1/batch/pool` — Add Order to Pool

Called by `order-svc` when order reaches "confirmed + preparing" status.

**Request:**
```json
{
  "orderId": "550e8400-e29b-41d4-a716-446655440001",
  "restaurantId": "rest-nyc-001",
  "restaurantName": "Curry House NYC",
  "pickupPoint": { "lat": 40.7614, "lng": -73.9776 },
  "deliveryPoint": { "lat": 40.7484, "lng": -73.9857 },
  "prepReadyAt": "2026-04-05T12:20:00Z",
  "promisedDeliveryAt": "2026-04-05T13:00:00Z",
  "priority": "standard",
  "itemCount": 3,
  "estimatedSizeLiters": 6.5,
  "currency": "USD",
  "deliveryFee": 4.99
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "poolOrderId": "pool-550e8400-xxxx",
    "status": "waiting",
    "estimatedBatchWindow": "~30 seconds"
  },
  "timestamp": "2026-04-05T12:15:30Z"
}
```

#### GET `/api/v1/batch/:batchId` — Get Batch Details

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "batch-001",
    "driverId": "driver-042",
    "status": "assigned",
    "score": 72,
    "estimatedTotalDistanceKm": 5.4,
    "estimatedTotalTimeMin": 28,
    "maxDetourMin": 4.2,
    "savingsPercent": 34.1,
    "orders": [
      {
        "orderId": "order-001",
        "sequence": 1,
        "estimatedPickupAt": "2026-04-05T12:22:00Z",
        "estimatedDeliveryAt": "2026-04-05T12:38:00Z",
        "detourMinutes": 0,
        "status": "pending"
      },
      {
        "orderId": "order-002",
        "sequence": 2,
        "estimatedPickupAt": "2026-04-05T12:25:00Z",
        "estimatedDeliveryAt": "2026-04-05T12:42:00Z",
        "detourMinutes": 4.2,
        "status": "pending"
      }
    ],
    "route": [
      { "sequence": 1, "type": "pickup", "orderId": "order-001", "point": { "lat": 40.7614, "lng": -73.9776 }, "estimatedArrivalAt": "2026-04-05T12:22:00Z", "estimatedDwellMin": 2 },
      { "sequence": 2, "type": "pickup", "orderId": "order-002", "point": { "lat": 40.7618, "lng": -73.9770 }, "estimatedArrivalAt": "2026-04-05T12:25:00Z", "estimatedDwellMin": 2 },
      { "sequence": 3, "type": "delivery", "orderId": "order-001", "point": { "lat": 40.7484, "lng": -73.9857 }, "estimatedArrivalAt": "2026-04-05T12:35:00Z", "estimatedDwellMin": 3 },
      { "sequence": 4, "type": "delivery", "orderId": "order-002", "point": { "lat": 40.7488, "lng": -73.9850 }, "estimatedArrivalAt": "2026-04-05T12:42:00Z", "estimatedDwellMin": 3 }
    ],
    "createdAt": "2026-04-05T12:16:00Z",
    "assignedAt": "2026-04-05T12:16:30Z",
    "completedAt": null
  },
  "timestamp": "2026-04-05T12:20:00Z"
}
```

#### POST `/api/v1/batch/:batchId/accept` — Driver Accepts Batch

**Request:**
```json
{
  "driverId": "driver-042",
  "currentLocation": { "lat": 40.7580, "lng": -73.9855 }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "batchId": "batch-001",
    "status": "assigned",
    "route": [ "...same route array as above..." ],
    "estimatedCompletionAt": "2026-04-05T12:44:00Z"
  }
}
```

#### POST `/api/v1/batch/:batchId/stops/:sequence/complete` — Mark Stop Done

**Request:**
```json
{
  "driverId": "driver-042",
  "currentLocation": { "lat": 40.7614, "lng": -73.9776 },
  "timestamp": "2026-04-05T12:23:15Z"
}
```

#### POST `/api/v1/batch/:batchId/orders/:orderId/remove` — Remove Order

**Request:**
```json
{
  "reason": "customer_cancelled"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "batchId": "batch-001",
    "orderId": "order-002",
    "removed": true,
    "batchCancelled": false,
    "routeRecalculated": true
  }
}
```

#### POST `/api/v1/batch/engine/cycle` — Manual Trigger (Admin)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "batchesFormed": 4,
    "ordersMatched": 9,
    "ordersExpired": 1,
    "cycleTimeMs": 42
  }
}
```

---

## 10. Event Architecture

### 10.1 Events Consumed (from SNS → SQS)

| Event | Source | Action |
|-------|--------|--------|
| `order.confirmed` | order-svc | Insert order into batch pool |
| `order.cancelled` | order-svc | Remove from pool or batch |

### 10.2 Events Published (to SNS)

| Event | Trigger | Subscribers |
|-------|---------|-------------|
| `batch.formed` | New batch created | delivery-svc (find driver) |
| `batch.assigned` | Driver accepted | order-svc (update ETAs), notification-svc |
| `batch.order_delivered` | One order delivered | order-svc, notification-svc |
| `batch.completed` | All orders delivered | delivery-svc, analytics |
| `batch.failed` | Batch couldn't complete | order-svc (reassign), support |
| `batch.order_removed` | Order removed from batch | order-svc, notification-svc |

### 10.3 Event Payload Schema

```json
{
  "type": "batch.formed",
  "batchId": "batch-001",
  "driverId": null,
  "orderId": null,
  "timestamp": "2026-04-05T12:16:00Z",
  "metadata": {
    "orderCount": 2,
    "score": 72,
    "savingsPercent": 34.1,
    "orderIds": ["order-001", "order-002"]
  }
}
```

---

## 11. Edge Case Handling

| # | Edge Case | Handling |
|---|-----------|----------|
| 1 | **Only 1 order in pool** | Forms a single-order batch (batch size 1). No savings but consistent flow. |
| 2 | **Priority order arrives** | Bypasses batching entirely. Immediately creates a solo batch. Configurable via `PRIORITY_ORDER_BATCHABLE`. |
| 3 | **Order cancelled before batching** | Pool status → cancelled. No impact. |
| 4 | **Order cancelled after batching, before pickup** | Removed from batch. Route recalculated. If last order → batch fails. |
| 5 | **Order cancelled mid-delivery** | Order marked cancelled in batch. Driver skips its delivery stop. Remaining route continues. |
| 6 | **Restaurant closes unexpectedly** | External event from restaurant-svc. All orders from that restaurant removed from pool/batch. |
| 7 | **Driver goes offline mid-batch** | Batch status → failed. All non-delivered orders re-enter the pool for rebatching. |
| 8 | **No driver available** | Batch stays in "pending" status. delivery-svc retries driver assignment. After timeout, orders re-enter pool. |
| 9 | **Order exceeds pool wait time** | Auto-escalated to solo delivery. Marked as "expired" in pool. |
| 10 | **Two orders from same restaurant** | Best case — pickup radius = 0, most efficient batch possible. |
| 11 | **Deliveries in opposite directions** | Rejected by delivery proximity check (`MAX_DELIVERY_RADIUS_KM`). |
| 12 | **Prep times far apart** | Route optimizer adds wait time at second restaurant. If total time exceeds threshold, batch rejected by scorer. |
| 13 | **Driver's bag is full** | `estimatedSizeLiters` sum checked against driver's `capacityLiters` before assignment. |
| 14 | **Duplicate order submitted** | Unique constraint on `order_pool.order_id` → returns 409 Conflict. |
| 15 | **Engine cycle takes too long** | Candidate generation capped at 500 permutations. Cycle time logged for monitoring. |

---

## 12. Service Integration Map

### 12.1 How order-svc Integrates

```typescript
// In order-svc: after order confirmed + preparing
// Publish event to SNS (existing pattern)
await sns.publish({
  TopicArn: ORDER_EVENTS_TOPIC_ARN,
  Message: JSON.stringify({
    type: "order.confirmed",
    orderId: order.id,
    restaurantId: order.restaurant_id,
    restaurantName: restaurant.name,
    pickupPoint: { lat: restaurant.lat, lng: restaurant.lng },
    deliveryPoint: { lat: order.delivery_lat, lng: order.delivery_lng },
    prepReadyAt: order.estimated_prep_ready,
    promisedDeliveryAt: order.estimated_delivery,
    priority: order.priority,
    itemCount: order.items.length,
    estimatedSizeLiters: order.estimated_volume,
    currency: order.currency,
    deliveryFee: order.delivery_fee,
  }),
});
```

### 12.2 How delivery-svc Integrates

```typescript
// delivery-svc subscribes to "batch.formed" events
// When received:
//   1. Query available drivers near the batch pickup centroid
//   2. Filter by capacity and current load
//   3. Offer batch to best driver
//   4. On acceptance: POST /api/v1/batch/:batchId/accept
//   5. Stream route stops to driver app via existing WebSocket
```

### 12.3 How the Driver App Changes

The driver app already supports multi-stop routes via `delivery-svc` WebSocket. Changes:

| Current | With Batching |
|---------|--------------|
| Route: 1 pickup → 1 delivery | Route: N pickups → N deliveries |
| "Pick up from Restaurant A" | "Pick up Order #1 from Restaurant A, then Order #2 from Restaurant B" |
| "Deliver to Customer" | "Deliver Order #1 to [address], then Order #2 to [address]" |

**Minimal driver app changes required** — the route is just longer.

---

## 13. Configuration and Tuning

### 13.1 Environment Variables

```bash
# ── App ──────────────────────────────────────────
NODE_ENV=production
PORT=8007
LOG_LEVEL=info

# ── Database ─────────────────────────────────────
DATABASE_URL=postgresql://user:pass@rds-host:5432/bhojango

# ── Redis (future: driver location cache) ────────
REDIS_URL=redis://redis-host:6379/6

# ── AWS ──────────────────────────────────────────
AWS_DEFAULT_REGION=us-east-1
SNS_TOPIC_ARN_BATCH=arn:aws:sns:us-east-1:123456:bhojango-prod-batch-events
SQS_QUEUE_URL_BATCH=https://sqs.us-east-1.amazonaws.com/123456/bhojango-prod-batch-events

# ── Engine Tuning (override defaults per market) ─
BATCH_CYCLE_SECONDS=30
MAX_ORDERS_PER_BATCH=3
MAX_PICKUP_RADIUS_KM=1.5
MAX_DELIVERY_RADIUS_KM=3.0
MAX_DETOUR_MINUTES=8
MAX_EXTRA_DELAY_MINUTES=5
MAX_WAIT_IN_POOL_MINUTES=5
MIN_SAVINGS_PERCENT=15
PRIORITY_ORDER_BATCHABLE=false
AVERAGE_SPEED_KMH=25

# ── Scoring Weights ──────────────────────────────
SCORE_WEIGHT_DISTANCE=0.30
SCORE_WEIGHT_TIME=0.25
SCORE_WEIGHT_DETOUR=0.20
SCORE_WEIGHT_PRIORITY=0.15
SCORE_WEIGHT_CAPACITY=0.10
```

### 13.2 Per-Market Configuration Strategy

Deploy separate ECS task definitions per market (US, India) with different env vars:

| Parameter | US (NYC) | India (Mumbai) |
|-----------|----------|---------------|
| `BATCH_CYCLE_SECONDS` | 30 | 20 |
| `MAX_PICKUP_RADIUS_KM` | 1.5 | 1.0 |
| `MAX_DELIVERY_RADIUS_KM` | 3.0 | 2.0 |
| `AVERAGE_SPEED_KMH` | 25 | 18 |
| `MAX_DETOUR_MINUTES` | 8 | 6 |

---

## 14. Observability and Metrics

### 14.1 Key Metrics to Track

| Metric | Type | Alert Threshold |
|--------|------|----------------|
| `batch.cycle_time_ms` | Histogram | > 500ms |
| `batch.formed_total` | Counter | — |
| `batch.multi_order_total` | Counter | — |
| `batch.avg_score` | Gauge | < 30 |
| `batch.avg_savings_pct` | Gauge | < 10% |
| `batch.avg_detour_min` | Gauge | > 6 min |
| `batch.orders_expired` | Counter | > 10/min |
| `batch.pool_size` | Gauge | > 100 |
| `batch.assignment_time_sec` | Histogram | > 120s |
| `batch.cycle_errors` | Counter | > 0 |

### 14.2 Structured Logging

All logs are JSON in production:

```json
{
  "timestamp": "2026-04-05T12:16:00.123Z",
  "level": "info",
  "service": "batch-engine",
  "message": "Batch cycle complete",
  "batchesFormed": 4,
  "multiOrderBatches": 2,
  "ordersMatched": 9,
  "expiredOrders": 1,
  "cycleTimeMs": 42
}
```

### 14.3 Health Check Endpoint

```
GET /health

{
  "status": "healthy",
  "service": "batch-engine",
  "version": "0.1.0",
  "uptime": 86400,
  "checks": {
    "database": "ok",
    "engine": "running"
  },
  "config": {
    "batchCycleSeconds": 30,
    "maxOrdersPerBatch": 3,
    "maxPickupRadiusKm": 1.5,
    "maxDetourMinutes": 8
  }
}
```

### 14.4 CloudWatch Dashboard Widgets

1. **Batches Formed** — time series (solo vs multi-order)
2. **Average Savings %** — gauge with 15% target line
3. **Average Detour** — gauge with 8min ceiling
4. **Pool Size** — real-time count of waiting orders
5. **Cycle Time** — p50/p95/p99 histogram
6. **Orders Expired** — counter (should be near zero)

---

## 15. Phased Rollout Plan

### Phase 0: Shadow Mode (Week 1-2)

| What | Detail |
|------|--------|
| **Deploy** | Engine runs in production receiving real events |
| **Behavior** | Scores and logs batches but does NOT assign drivers |
| **Purpose** | Validate scoring logic against real traffic patterns |
| **Success criteria** | >20% of order pairs score above threshold; no false positives |
| **Rollback** | Remove SQS subscription |

### Phase 1: Single City Pilot (Week 3-4)

| What | Detail |
|------|--------|
| **Deploy** | Enable assignment in 1 high-density city (e.g., Manhattan or Mumbai) |
| **Behavior** | Real batching and driver assignment |
| **Monitoring** | Watch delivery times, driver complaints, customer ratings |
| **Success criteria** | ≥15% distance savings; ≤5% increase in average delivery time; no NPS drop |
| **Rollback** | Set `MAX_ORDERS_PER_BATCH=1` (forces all solo) |

### Phase 2: Customer Opt-In (Week 5-6)

| What | Detail |
|------|--------|
| **Deploy** | Add "Eco delivery — save $1" option at checkout |
| **Behavior** | Only opted-in orders enter the batch pool |
| **Purpose** | Measure customer willingness and satisfaction |
| **Success criteria** | >30% opt-in rate; 4.5+ star rating for batched deliveries |

### Phase 3: Default On (Week 7-8)

| What | Detail |
|------|--------|
| **Deploy** | All standard orders are batch-eligible by default |
| **Behavior** | Priority orders still exempt; customers can opt out |
| **Monitoring** | Full metrics dashboard; weekly review |
| **Success criteria** | ≥20% of deliveries are multi-order batches; cost per delivery drops 15%+ |

### Phase 4: Multi-Market Expansion (Month 3+)

| What | Detail |
|------|--------|
| **Deploy** | Roll out to all cities with market-specific tuning |
| **Additions** | Per-city config profiles; A/B testing framework for weights |
| **Future** | Extend to grocery (larger batches) and parcel (longer routes) |

---

## 16. Implementation Guide

### 16.1 File Structure

```
services/batch-engine/
├── src/
│   ├── main.ts                              # App entry, Express setup, startup
│   ├── config/index.ts                      # Environment config + engine rules
│   ├── types/index.ts                       # All TypeScript interfaces
│   ├── dto/batch.dto.ts                     # Request/response DTOs
│   ├── engine/
│   │   ├── batch-builder.ts                 # Core cycle: group → score → select
│   │   ├── batch-scorer.ts                  # Weighted scoring algorithm
│   │   └── route-optimizer.ts               # Permutation-based route optimization
│   ├── services/
│   │   └── batch.service.ts                 # Business logic orchestration layer
│   ├── db/
│   │   ├── connection.ts                    # PostgreSQL pool + migration runner
│   │   ├── migrations/
│   │   │   └── 001_create_batch_tables.sql  # Full schema (6 tables)
│   │   └── repositories/
│   │       ├── batch.repository.ts          # Batch + orders + route CRUD
│   │       └── order-pool.repository.ts     # Pool CRUD
│   ├── api/
│   │   ├── routes.ts                        # Express route definitions
│   │   ├── batch.controller.ts              # HTTP handler functions
│   │   └── middleware/
│   │       └── validation.ts                # Request body validators
│   ├── events/
│   │   ├── consumer.ts                      # SQS long-polling listener
│   │   └── publisher.ts                     # SNS event publisher
│   └── utils/
│       ├── geo.ts                           # Haversine, road distance, ETA
│       └── logger.ts                        # Structured JSON logger
├── tests/
│   └── batch-scorer.test.ts                 # Unit tests (scorer + optimizer)
├── package.json                             # Dependencies + scripts
├── tsconfig.json                            # TypeScript config
├── Dockerfile                               # Multi-stage build
└── .env.example                             # All environment variables
```

### 16.2 Development Setup

```bash
cd services/batch-engine

# Install dependencies
npm install

# Run database migration
psql $DATABASE_URL -f src/db/migrations/001_create_batch_tables.sql

# Start in development (hot reload)
npm run dev

# Run tests
npm test

# Build for production
npm run build
npm start
```

### 16.3 Docker Compose Entry

The service is already added to `docker-compose.yml`:

```yaml
batch-engine:
  build:
    context: ./services/batch-engine
    dockerfile: Dockerfile
  ports:
    - "8007:8007"
  environment:
    DATABASE_URL: postgresql://bhojango:bhojango_dev@postgres:5432/bhojango
    REDIS_URL: redis://redis:6379/6
    AWS_ENDPOINT_URL: http://localstack:4566
    BATCH_CYCLE_SECONDS: "30"
    MAX_ORDERS_PER_BATCH: "3"
  depends_on:
    postgres: { condition: service_healthy }
    redis: { condition: service_healthy }
```

### 16.4 Kong Gateway Route

```yaml
- name: batch-engine
  url: http://batch-engine:8007
  routes:
    - name: batch-routes
      paths: [/api/v1/batch]
      strip_path: false
```

---

## 17. Testing Strategy

### 17.1 Unit Tests (Engine Logic)

| Test | File | What It Validates |
|------|------|-------------------|
| Single-order route | `batch-scorer.test.ts` | 2 stops, 0 detour |
| Pickup-before-delivery | `batch-scorer.test.ts` | Route constraint enforced |
| Nearby orders score higher | `batch-scorer.test.ts` | Savings > threshold |
| Priority order penalty | `batch-scorer.test.ts` | Score decreases |
| Distant deliveries rejected | `batch-scorer.test.ts` | High detour / low score |
| Haversine accuracy | `geo.test.ts` | Known distance within 1% |

### 17.2 Integration Tests

| Test | Scope |
|------|-------|
| Add to pool → verify DB row | Repository + database |
| Full cycle → verify batches created | Service + engine + database |
| Accept batch → verify status change | Controller + service + database |
| Cancel order → verify route update | Controller + service + database |
| SQS message → verify pool insertion | Consumer + service |

### 17.3 E2E Tests

| Test | Flow |
|------|------|
| Happy path | order-svc confirms 2 nearby orders → engine batches them → driver accepts → pickups → deliveries → completed |
| Cancellation | order batched → customer cancels → order removed → remaining route continues |
| Priority protection | priority order → immediately solo batched → no delay |
| Pool expiry | order sits 6 minutes → auto-escalated to solo |

---

## 18. Performance and Scalability

### 18.1 Current Capacity

| Metric | Value | Basis |
|--------|-------|-------|
| Orders per cycle | ~200 | 5-minute pool with 40 orders/min |
| Candidate generation time | <50ms | For 200 orders grouped into ~30 clusters |
| Route optimization time | <1ms per candidate | 6-stop permutation search |
| Database writes per cycle | ~50 | Batch creation transactions |
| **Target cycle time** | **<200ms** | Well within 30-second window |

### 18.2 Scaling Strategy

| Scale Point | Solution |
|-------------|----------|
| >500 orders/cycle | Partition by city (separate engine instances) |
| >4 orders/batch | Replace permutation solver with Google Routes Optimization API |
| >10K orders/min | Introduce Redis for pool (read-heavy), PostgreSQL for batch state (write) |
| Global optimization | Replace greedy selection with Hungarian algorithm or OR-Tools |

### 18.3 Database Performance

- **Hot query:** `SELECT * FROM order_pool WHERE status = 'waiting'` — covered by partial index
- **Write pattern:** Batch creation is a single transaction (batch + N orders + N stops)
- **No table scans:** All queries use indexed columns
- **Cleanup:** Completed batches can be archived to cold storage after 30 days

---

## 19. Security Considerations

| Concern | Mitigation |
|---------|------------|
| API access | All endpoints behind Kong gateway with JWT auth |
| Admin endpoints | `POST /engine/cycle` restricted to admin role |
| Driver impersonation | Driver ID verified against delivery-svc before batch acceptance |
| SQL injection | Parameterized queries throughout (no string concatenation) |
| Event spoofing | SQS/SNS access controlled by IAM roles |
| Data exposure | No customer PII in batch tables (only order IDs and coordinates) |

---

## 20. Open Questions and Future Work

### Open Questions (Need Product/Eng Decision)

| # | Question | Options | Recommendation |
|---|----------|---------|---------------|
| 1 | Should customers see "Batched delivery" in their tracking UI? | Yes (transparent) / No (invisible) | Yes — builds trust |
| 2 | Should batched delivery get a discount? | Fixed discount / % of savings / None | $0.50-1.00 discount (share savings) |
| 3 | Should drivers get a bonus for multi-order batches? | Per-extra-order bonus / Higher batch fee | $1.50 per extra order |
| 4 | Max batch size for grocery orders? | 2 / 3 / 5 | 5 (grocery bags are smaller per order) |

### Future Work (Post-MVP)

| # | Feature | Priority | Complexity |
|---|---------|----------|------------|
| 1 | Real-time traffic integration (Google Routes API) | High | Medium |
| 2 | ML-based scoring (learn from actual delivery data) | High | High |
| 3 | Customer opt-in/out toggle at checkout | High | Low |
| 4 | Global optimization (Hungarian algorithm) | Medium | High |
| 5 | Dynamic pricing (batch discount at checkout) | Medium | Medium |
| 6 | Grocery/parcel batch profiles (larger batches, longer routes) | Medium | Medium |
| 7 | Driver preference learning (some drivers prefer batches) | Low | Medium |
| 8 | A/B testing framework for scoring weights | Low | Low |
| 9 | PostGIS spatial indexing for pickup clustering | Low | Low |

---

## Appendix A — Sample Request/Response Payloads

### A.1 Full Batch Cycle Example

**Step 1:** Two orders arrive 10 seconds apart.

```
12:15:00 — order-001 confirmed (Curry House, pickup: 40.7614, -73.9776 → delivery: 40.7484, -73.9857)
12:15:10 — order-002 confirmed (Spice Palace, pickup: 40.7618, -73.9770 → delivery: 40.7488, -73.9850)
```

**Step 2:** Engine cycle runs at 12:15:30.

```
Pool: [order-001 (waiting, 30s), order-002 (waiting, 20s)]
Groups: [[order-001, order-002]] (pickups 50m apart)
Candidates: [batch(order-001, order-002)]
Score: 72/100 (34% distance savings, 4.2 min max detour)
→ Batch formed: batch-001
```

**Step 3:** delivery-svc finds nearest driver and offers batch.

```
POST /api/v1/batch/batch-001/accept
{ "driverId": "driver-042", "currentLocation": { "lat": 40.7580, "lng": -73.9855 } }
```

**Step 4:** Driver follows route: pickup-1 → pickup-2 → delivery-1 → delivery-2.

```
12:22 — Arrive at Curry House, pick up order-001
12:25 — Arrive at Spice Palace, pick up order-002
12:35 — Deliver order-001 to customer
12:42 — Deliver order-002 to customer
```

**Step 5:** Batch completed.

```
Solo would have taken: 42 min total (two separate trips)
Batched took: 28 min total (one trip)
Savings: 34% distance, 33% time
Customer 1 detour: 0 min (delivered first)
Customer 2 detour: 4.2 min (delivered second)
```

---

## Appendix B — Full File Tree

```
services/batch-engine/                    24 files
├── .env.example                          Environment variables reference
├── Dockerfile                            Multi-stage Node.js build
├── package.json                          Dependencies + scripts
├── tsconfig.json                         TypeScript compiler config
├── src/
│   ├── main.ts                           Express app + startup sequence
│   ├── config/
│   │   └── index.ts                      All config from env vars
│   ├── types/
│   │   └── index.ts                      TypeScript interfaces (30+ types)
│   ├── dto/
│   │   └── batch.dto.ts                  Request/response DTOs
│   ├── engine/
│   │   ├── batch-builder.ts              Core cycle: group → generate → select
│   │   ├── batch-scorer.ts               Weighted composite scoring
│   │   └── route-optimizer.ts            Permutation-based TSP solver
│   ├── services/
│   │   └── batch.service.ts              Business logic orchestration
│   ├── db/
│   │   ├── connection.ts                 PostgreSQL pool + health check
│   │   ├── migrations/
│   │   │   └── 001_create_batch_tables.sql   6 tables + indexes + triggers
│   │   └── repositories/
│   │       ├── batch.repository.ts       Batch CRUD with transactions
│   │       └── order-pool.repository.ts  Pool CRUD
│   ├── api/
│   │   ├── routes.ts                     7 route definitions
│   │   ├── batch.controller.ts           HTTP handlers
│   │   └── middleware/
│   │       └── validation.ts             Request validators
│   ├── events/
│   │   ├── consumer.ts                   SQS long-polling listener
│   │   └── publisher.ts                  SNS event publisher
│   └── utils/
│       ├── geo.ts                        Haversine + road distance + ETA
│       └── logger.ts                     Structured JSON logger
└── tests/
    └── batch-scorer.test.ts              Unit tests for scorer + optimizer
```

---

## Appendix C — Glossary

| Term | Definition |
|------|-----------|
| **Batch** | A group of 1-N orders assigned to a single driver for one trip |
| **Pool** | The holding area where confirmed orders wait for batch assignment |
| **Cycle** | One execution of the batch engine (default every 30 seconds) |
| **Detour** | Extra time a customer waits because their order was batched vs solo |
| **Savings** | Distance/cost reduction achieved by batching vs individual deliveries |
| **Score** | Composite quality rating (0-100) for a candidate batch |
| **Route Stop** | A single pickup or delivery point in the driver's sequence |
| **Dwell Time** | Minutes a driver spends at a stop (loading food, handing off) |
| **Greedy Selection** | Algorithm that picks the best batch first, then the next non-conflicting best |
| **Shadow Mode** | Engine runs but doesn't assign — logs what it would do |
| **Solo Delivery** | A batch containing exactly 1 order (traditional single-order delivery) |

---

*End of Technical Design Document*
