/**
 * Data Transfer Objects — request/response shapes for the Batch Engine API.
 * All validation happens in the middleware layer using these schemas.
 */

import { GeoPoint, OrderPriority, BatchStatus, PoolStatus } from "../types";

// ── Inbound: Add order to pool ──────────────────────────────────────────────
// POST /api/v1/batch/pool
// Called by order-svc when an order reaches "confirmed" + "preparing" status.

export interface AddToPoolRequest {
  orderId: string;
  restaurantId: string;
  restaurantName: string;
  pickupPoint: GeoPoint;
  deliveryPoint: GeoPoint;
  prepReadyAt: string;            // ISO 8601
  promisedDeliveryAt: string;     // ISO 8601
  priority: OrderPriority;
  itemCount: number;
  estimatedSizeLiters: number;
  currency: "USD" | "INR";
  deliveryFee: number;
}

export interface AddToPoolResponse {
  poolOrderId: string;
  status: PoolStatus;
  estimatedBatchWindow: string;   // "~30 seconds"
}

// ── Get batch details ───────────────────────────────────────────────────────
// GET /api/v1/batch/:batchId

export interface BatchDetailResponse {
  id: string;
  driverId: string | null;
  status: BatchStatus;
  score: number;
  estimatedTotalDistanceKm: number;
  estimatedTotalTimeMin: number;
  maxDetourMin: number;
  savingsPercent: number;
  orders: BatchOrderDetail[];
  route: RouteStopDetail[];
  createdAt: string;
  assignedAt: string | null;
  completedAt: string | null;
}

export interface BatchOrderDetail {
  orderId: string;
  sequence: number;
  estimatedPickupAt: string;
  estimatedDeliveryAt: string;
  detourMinutes: number;
  status: string;
}

export interface RouteStopDetail {
  sequence: number;
  type: "pickup" | "delivery";
  orderId: string;
  point: GeoPoint;
  estimatedArrivalAt: string;
  estimatedDwellMin: number;
}

// ── Driver: accept batch ────────────────────────────────────────────────────
// POST /api/v1/batch/:batchId/accept

export interface AcceptBatchRequest {
  driverId: string;
  currentLocation: GeoPoint;
}

export interface AcceptBatchResponse {
  batchId: string;
  status: "assigned";
  route: RouteStopDetail[];
  estimatedCompletionAt: string;
}

// ── Driver: mark stop complete ──────────────────────────────────────────────
// POST /api/v1/batch/:batchId/stops/:sequence/complete

export interface CompleteStopRequest {
  driverId: string;
  currentLocation: GeoPoint;
  timestamp: string;
}

// ── Remove order from batch (cancellation) ──────────────────────────────────
// POST /api/v1/batch/:batchId/orders/:orderId/remove

export interface RemoveOrderRequest {
  reason: "customer_cancelled" | "restaurant_cancelled" | "admin_override";
}

export interface RemoveOrderResponse {
  batchId: string;
  orderId: string;
  removed: boolean;
  batchCancelled: boolean;        // true if this was the last order
  routeRecalculated: boolean;
}

// ── Engine: manually trigger a batch cycle ──────────────────────────────────
// POST /api/v1/batch/engine/cycle   (admin only)

export interface CycleResponse {
  batchesFormed: number;
  ordersMatched: number;
  ordersExpired: number;
  cycleTimeMs: number;
}

// ── Metrics / dashboard ─────────────────────────────────────────────────────
// GET /api/v1/batch/metrics?date=2026-04-05&city=NYC

export interface MetricsResponse {
  date: string;
  city: string;
  totalBatches: number;
  multiOrderBatches: number;
  avgBatchSize: number;
  avgSavingsPercent: number;
  avgDetourMin: number;
  totalDistanceSavedKm: number;
}

// ── Generic API envelope ────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
  timestamp: string;
}
