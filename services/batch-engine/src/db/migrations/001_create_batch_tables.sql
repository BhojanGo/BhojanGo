-- ============================================================================
-- Batch Delivery Engine — Database Schema
-- ============================================================================
-- Tables live in the batch_engine schema to isolate from other services.
-- Run: psql $DATABASE_URL -f 001_create_batch_tables.sql
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS batch_engine;
SET search_path TO batch_engine;

-- ── Order Pool ──────────────────────────────────────────────────────────────
-- Orders land here when order-svc publishes "order.confirmed".
-- The engine reads from this table every batch cycle.

CREATE TABLE order_pool (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL UNIQUE,
    restaurant_id   UUID NOT NULL,
    restaurant_name TEXT NOT NULL,

    -- Geo coordinates (stored as double precision for simplicity;
    -- PostGIS would be used at scale for spatial indexing)
    pickup_lat      DOUBLE PRECISION NOT NULL,
    pickup_lng      DOUBLE PRECISION NOT NULL,
    delivery_lat    DOUBLE PRECISION NOT NULL,
    delivery_lng    DOUBLE PRECISION NOT NULL,

    -- Timing
    prep_ready_at       TIMESTAMPTZ NOT NULL,   -- when food will be ready
    promised_delivery_at TIMESTAMPTZ NOT NULL,   -- SLA to customer

    -- Order metadata
    priority        VARCHAR(20) NOT NULL DEFAULT 'standard'
                    CHECK (priority IN ('standard', 'priority', 'scheduled')),
    item_count      INTEGER NOT NULL DEFAULT 1,
    estimated_size_liters REAL NOT NULL DEFAULT 5.0,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    delivery_fee    NUMERIC(10,2) NOT NULL DEFAULT 0,

    -- State
    status          VARCHAR(20) NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting', 'batched', 'expired', 'cancelled')),
    batch_id        UUID REFERENCES batches(id) ON DELETE SET NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pool_status ON order_pool(status) WHERE status = 'waiting';
CREATE INDEX idx_pool_restaurant ON order_pool(restaurant_id) WHERE status = 'waiting';
CREATE INDEX idx_pool_created ON order_pool(created_at) WHERE status = 'waiting';

-- ── Batches ─────────────────────────────────────────────────────────────────
-- A batch groups 1-N orders for a single driver trip.

CREATE TABLE batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id       UUID,
    status          VARCHAR(20) NOT NULL DEFAULT 'forming'
                    CHECK (status IN (
                        'forming', 'pending', 'assigned',
                        'in_progress', 'completed', 'failed'
                    )),

    -- Scoring & metrics
    score                      REAL NOT NULL DEFAULT 0,
    estimated_total_distance_km REAL NOT NULL DEFAULT 0,
    estimated_total_time_min   REAL NOT NULL DEFAULT 0,
    max_detour_min             REAL NOT NULL DEFAULT 0,
    savings_percent            REAL NOT NULL DEFAULT 0,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_at     TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_batch_status ON batches(status);
CREATE INDEX idx_batch_driver ON batches(driver_id) WHERE status IN ('assigned', 'in_progress');

-- ── Batch Orders ────────────────────────────────────────────────────────────
-- Join table: which orders belong to which batch, in what sequence.

CREATE TABLE batch_orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    order_id        UUID NOT NULL,
    pool_order_id   UUID NOT NULL REFERENCES order_pool(id),
    sequence        INTEGER NOT NULL,

    -- Per-order estimates
    estimated_pickup_at   TIMESTAMPTZ NOT NULL,
    estimated_delivery_at TIMESTAMPTZ NOT NULL,
    detour_minutes        REAL NOT NULL DEFAULT 0,

    -- Actuals (filled as delivery progresses)
    actual_pickup_at    TIMESTAMPTZ,
    actual_delivery_at  TIMESTAMPTZ,

    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'picked_up', 'delivered', 'cancelled')),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (batch_id, order_id)
);

CREATE INDEX idx_batchorder_batch ON batch_orders(batch_id);

-- ── Route Stops ─────────────────────────────────────────────────────────────
-- The optimized stop-by-stop route the driver follows.

CREATE TABLE route_stops (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    sequence        INTEGER NOT NULL,
    stop_type       VARCHAR(10) NOT NULL CHECK (stop_type IN ('pickup', 'delivery')),
    order_id        UUID NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lng             DOUBLE PRECISION NOT NULL,
    estimated_arrival_at TIMESTAMPTZ NOT NULL,
    estimated_dwell_min  REAL NOT NULL DEFAULT 2,

    UNIQUE (batch_id, sequence)
);

CREATE INDEX idx_route_batch ON route_stops(batch_id);

-- ── Batch Event Log ─────────────────────────────────────────────────────────
-- Immutable audit log for every state change — useful for analytics & debugging.

CREATE TABLE batch_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    UUID NOT NULL REFERENCES batches(id),
    event_type  VARCHAR(50) NOT NULL,
    order_id    UUID,
    driver_id   UUID,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_batchevent_batch ON batch_events(batch_id);
CREATE INDEX idx_batchevent_type ON batch_events(event_type);

-- ── Batch Metrics (materialized for dashboards) ─────────────────────────────

CREATE TABLE batch_metrics_daily (
    date            DATE NOT NULL,
    city            VARCHAR(100) NOT NULL,
    total_batches   INTEGER NOT NULL DEFAULT 0,
    multi_order_batches INTEGER NOT NULL DEFAULT 0,
    avg_batch_size  REAL NOT NULL DEFAULT 1,
    avg_savings_pct REAL NOT NULL DEFAULT 0,
    avg_detour_min  REAL NOT NULL DEFAULT 0,
    total_distance_saved_km REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (date, city)
);

-- ── Helper: auto-update updated_at ──────────────────────────────────────────

CREATE OR REPLACE FUNCTION batch_engine.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pool_updated BEFORE UPDATE ON order_pool
    FOR EACH ROW EXECUTE FUNCTION batch_engine.update_updated_at();

CREATE TRIGGER trg_batch_updated BEFORE UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION batch_engine.update_updated_at();
