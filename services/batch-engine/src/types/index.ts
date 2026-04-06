/**
 * Batch Delivery Engine — Core Type Definitions
 *
 * Architecture overview:
 *   Orders enter the "pool" when confirmed + preparing.
 *   The engine runs every BATCH_CYCLE_SECONDS (default 30s) and:
 *     1. Pulls eligible orders from the pool
 *     2. Groups them by pickup proximity (same/nearby restaurants)
 *     3. Scores candidate batches on cost, time, distance
 *     4. Assigns the winning batch to the best-fit driver
 *     5. Publishes batch.created / batch.assigned events
 *
 *   A batch is 1–N orders carried by 1 driver in 1 trip.
 *   Single-order deliveries are just a batch of size 1.
 */

// ── Geo ─────────────────────────────────────────────────────────────────────

export interface GeoPoint {
  lat: number;
  lng: number;
}

// ── Order Pool ──────────────────────────────────────────────────────────────

export type PoolStatus =
  | "waiting"        // order confirmed, waiting for batch assignment
  | "batched"        // assigned to a batch
  | "expired"        // exceeded max wait time, escalate to single delivery
  | "cancelled";     // customer cancelled before pickup

export interface PoolOrder {
  id: string;
  orderId: string;
  restaurantId: string;
  restaurantName: string;
  pickupPoint: GeoPoint;
  deliveryPoint: GeoPoint;
  prepReadyAt: Date;            // estimated time food will be ready
  promisedDeliveryAt: Date;     // SLA promise to customer
  priority: OrderPriority;
  itemCount: number;
  estimatedSizeLiters: number;  // volume estimate for capacity check
  currency: "USD" | "INR";
  deliveryFee: number;
  createdAt: Date;
  status: PoolStatus;
  batchId: string | null;
}

export type OrderPriority = "standard" | "priority" | "scheduled";

// ── Batch ───────────────────────────────────────────────────────────────────

export type BatchStatus =
  | "forming"        // engine is building this batch
  | "pending"        // batch ready, looking for driver
  | "assigned"       // driver accepted
  | "in_progress"    // driver picking up
  | "completed"      // all orders delivered
  | "failed";        // batch couldn't be completed

export interface Batch {
  id: string;
  driverId: string | null;
  status: BatchStatus;
  orders: BatchOrder[];
  route: RouteStop[];
  score: number;                // composite score (higher = better)
  estimatedTotalDistanceKm: number;
  estimatedTotalTimeMin: number;
  maxDetourMin: number;         // worst-case extra time for any order
  savingsPercent: number;       // cost savings vs individual deliveries
  createdAt: Date;
  assignedAt: Date | null;
  completedAt: Date | null;
}

export interface BatchOrder {
  orderId: string;
  poolOrderId: string;
  sequence: number;             // position in pickup/delivery route
  estimatedPickupAt: Date;
  estimatedDeliveryAt: Date;
  actualPickupAt: Date | null;
  actualDeliveryAt: Date | null;
  detourMinutes: number;        // extra time vs solo delivery
  status: "pending" | "picked_up" | "delivered" | "cancelled";
}

// ── Route ───────────────────────────────────────────────────────────────────

export type StopType = "pickup" | "delivery";

export interface RouteStop {
  sequence: number;
  type: StopType;
  orderId: string;
  point: GeoPoint;
  estimatedArrivalAt: Date;
  estimatedDwellMin: number;    // time spent at stop (loading / handoff)
}

// ── Driver ──────────────────────────────────────────────────────────────────

export interface DriverCandidate {
  driverId: string;
  currentLocation: GeoPoint;
  capacityLiters: number;       // bag/vehicle capacity
  maxConcurrentOrders: number;  // driver's batch limit (default 3)
  currentBatchSize: number;     // orders already carrying
  rating: number;
  isAvailable: boolean;
  vehicleType: "bike" | "scooter" | "car";
}

// ── Scoring ─────────────────────────────────────────────────────────────────

export interface BatchCandidate {
  orders: PoolOrder[];
  route: RouteStop[];
  totalDistanceKm: number;
  totalTimeMin: number;
  maxDetourMin: number;
  savingsPercent: number;
  score: number;
}

export interface ScoringWeights {
  distanceSaving: number;   // weight for distance reduction (0-1)
  timeSaving: number;       // weight for time efficiency (0-1)
  detourPenalty: number;    // penalty for customer wait (0-1)
  priorityPenalty: number;  // penalty for batching priority orders (0-1)
  capacityFit: number;     // how well batch fills driver capacity (0-1)
}

// ── Config ──────────────────────────────────────────────────────────────────

export interface BatchEngineConfig {
  batchCycleSeconds: number;
  maxOrdersPerBatch: number;
  maxPickupRadiusKm: number;
  maxDeliveryRadiusKm: number;
  maxDetourMinutes: number;
  maxExtraDelayMinutes: number;
  maxWaitInPoolMinutes: number;
  minSavingsPercent: number;
  priorityOrderBatchable: boolean;
  driverPickupDwellMin: number;
  driverDeliveryDwellMin: number;
  averageSpeedKmh: number;
}

// ── Events ──────────────────────────────────────────────────────────────────

export type BatchEventType =
  | "batch.formed"
  | "batch.assigned"
  | "batch.pickup_complete"
  | "batch.order_delivered"
  | "batch.completed"
  | "batch.failed"
  | "batch.order_removed";

export interface BatchEvent {
  type: BatchEventType;
  batchId: string;
  driverId?: string;
  orderId?: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}
