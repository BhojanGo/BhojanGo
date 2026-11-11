import { BatchEngineConfig, ScoringWeights } from "../types";

/**
 * Configuration — all values from environment with sensible defaults.
 * Tunable per-market: India has denser cities → tighter radii, faster cycles.
 */

function env(key: string, fallback: string): string {
  return process.env[key] ?? fallback;
}

function envInt(key: string, fallback: number): number {
  const v = process.env[key];
  return v ? parseInt(v, 10) : fallback;
}

function envFloat(key: string, fallback: number): number {
  const v = process.env[key];
  return v ? parseFloat(v) : fallback;
}

// ── App Config ──────────────────────────────────────────────────────────────

export const APP_CONFIG = {
  port: envInt("PORT", 8007),
  env: env("NODE_ENV", "development"),
  serviceName: "batch-engine",
  version: "0.1.0",
  logLevel: env("LOG_LEVEL", "info"),
} as const;

// ── Auth ──────────────────────────────────────────────────────────────────────

const DEFAULT_JWT_SECRET = "changeme-in-production";

export const JWT_CONFIG = {
  secret: env("JWT_SECRET", DEFAULT_JWT_SECRET),
  algorithm: env("JWT_ALGORITHM", "HS256"),
  usingDefaultSecret: !process.env.JWT_SECRET,
} as const;

// ── Database ────────────────────────────────────────────────────────────────

export const DB_CONFIG = {
  connectionString: env(
    "DATABASE_URL",
    "postgresql://bhojango:bhojango_dev@localhost:5432/bhojango"
  ),
  poolMin: envInt("DB_POOL_MIN", 2),
  poolMax: envInt("DB_POOL_MAX", 10),
  idleTimeoutMs: envInt("DB_IDLE_TIMEOUT_MS", 30_000),
} as const;

// ── Redis ───────────────────────────────────────────────────────────────────

export const REDIS_CONFIG = {
  url: env("REDIS_URL", "redis://localhost:6379/6"),
} as const;

// ── AWS / Events ────────────────────────────────────────────────────────────

export const AWS_CONFIG = {
  region: env("AWS_DEFAULT_REGION", "us-east-1"),
  endpoint: env("AWS_ENDPOINT_URL", ""),  // LocalStack in dev
  snsTopicArn: env("SNS_TOPIC_ARN_BATCH", ""),
  sqsOrderEventsUrl: env("SQS_QUEUE_URL_BATCH", ""),
} as const;

// ── Batch Engine Rules ──────────────────────────────────────────────────────

export const ENGINE_CONFIG: BatchEngineConfig = {
  /** How often the engine runs a batch cycle */
  batchCycleSeconds: envInt("BATCH_CYCLE_SECONDS", 30),

  /** Max orders a single driver carries per trip */
  maxOrdersPerBatch: envInt("MAX_ORDERS_PER_BATCH", 3),

  /** Restaurants must be within this radius to be grouped */
  maxPickupRadiusKm: envFloat("MAX_PICKUP_RADIUS_KM", 1.5),

  /** Delivery points must be within this radius of each other */
  maxDeliveryRadiusKm: envFloat("MAX_DELIVERY_RADIUS_KM", 3.0),

  /** Max extra drive time any single order can incur from batching */
  maxDetourMinutes: envFloat("MAX_DETOUR_MINUTES", 8),

  /** Max extra delay to customer's promised time */
  maxExtraDelayMinutes: envFloat("MAX_EXTRA_DELAY_MINUTES", 5),

  /** If an order sits in the pool longer than this, force single-delivery */
  maxWaitInPoolMinutes: envFloat("MAX_WAIT_IN_POOL_MINUTES", 5),

  /** Don't batch unless we save at least this much vs solo deliveries */
  minSavingsPercent: envFloat("MIN_SAVINGS_PERCENT", 15),

  /** Whether priority orders can ever be batched */
  priorityOrderBatchable: env("PRIORITY_ORDER_BATCHABLE", "false") === "true",

  /** Time driver spends at restaurant picking up (minutes) */
  driverPickupDwellMin: envFloat("DRIVER_PICKUP_DWELL_MIN", 2),

  /** Time driver spends at customer door (minutes) */
  driverDeliveryDwellMin: envFloat("DRIVER_DELIVERY_DWELL_MIN", 3),

  /** Average driving speed in city for time estimates */
  averageSpeedKmh: envFloat("AVERAGE_SPEED_KMH", 25),
};

// ── Scoring Weights (sum to ~1.0) ───────────────────────────────────────────

export const SCORING_WEIGHTS: ScoringWeights = {
  distanceSaving: envFloat("SCORE_WEIGHT_DISTANCE", 0.30),
  timeSaving: envFloat("SCORE_WEIGHT_TIME", 0.25),
  detourPenalty: envFloat("SCORE_WEIGHT_DETOUR", 0.20),
  priorityPenalty: envFloat("SCORE_WEIGHT_PRIORITY", 0.15),
  capacityFit: envFloat("SCORE_WEIGHT_CAPACITY", 0.10),
};
