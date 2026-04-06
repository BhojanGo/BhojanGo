/**
 * Batch Scorer — assigns a composite score to a batch candidate.
 *
 * Score = weighted sum of:
 *   1. Distance savings (positive: less total km than solo deliveries)
 *   2. Time savings (positive: less total minutes)
 *   3. Detour penalty (negative: extra wait per customer)
 *   4. Priority penalty (negative: batching priority orders is discouraged)
 *   5. Capacity fit (positive: batch fills driver capacity well)
 *
 * Score range: 0–100. Higher is better.
 * A batch below the minimum savings threshold gets score 0 (rejected).
 */

import { PoolOrder, BatchCandidate, ScoringWeights, GeoPoint } from "../types";
import { ENGINE_CONFIG, SCORING_WEIGHTS } from "../config";
import { roadDistanceKm, driveTimeMin } from "../utils/geo";
import { optimizeRoute } from "./route-optimizer";
import { logger } from "../utils/logger";

/**
 * Score a candidate batch of orders.
 * Returns a fully-scored BatchCandidate including the optimized route.
 */
export function scoreBatch(
  orders: PoolOrder[],
  driverStart: GeoPoint
): BatchCandidate {
  const weights = SCORING_WEIGHTS;

  // Step 1: Optimize the route for this batch
  const optimized = optimizeRoute(orders, driverStart);

  // Step 2: Calculate what solo deliveries would cost
  const soloMetrics = calculateSoloMetrics(orders, driverStart);

  // Step 3: Calculate savings
  const distSaved = soloMetrics.totalDistanceKm - optimized.totalDistanceKm;
  const timeSaved = soloMetrics.totalTimeMin - optimized.totalTimeMin;
  const savingsPercent =
    soloMetrics.totalDistanceKm > 0
      ? (distSaved / soloMetrics.totalDistanceKm) * 100
      : 0;

  // Step 4: Check minimum savings threshold
  if (savingsPercent < ENGINE_CONFIG.minSavingsPercent && orders.length > 1) {
    logger.debug("Batch rejected: insufficient savings", {
      savingsPercent,
      minRequired: ENGINE_CONFIG.minSavingsPercent,
      orderCount: orders.length,
    });
    return buildCandidate(orders, optimized, 0, savingsPercent);
  }

  // Step 5: Compute sub-scores (each normalized to 0–100)

  // Distance saving: how much shorter is the batch route?
  const distScore = normalizeScore(savingsPercent, 0, 50); // 50% savings = perfect

  // Time saving: how much faster overall?
  const timeScore =
    soloMetrics.totalTimeMin > 0
      ? normalizeScore(
          (timeSaved / soloMetrics.totalTimeMin) * 100,
          0,
          40
        )
      : 0;

  // Detour penalty: how badly does the worst-affected customer suffer?
  // 0 min detour = score 100, maxDetourMinutes = score 0
  const detourScore =
    100 - normalizeScore(optimized.maxDetourMin, 0, ENGINE_CONFIG.maxDetourMinutes) ;

  // Priority penalty: reduce score if batch contains priority orders
  const hasPriority = orders.some((o) => o.priority === "priority");
  const priorityScore = hasPriority ? 20 : 100; // harsh penalty

  // Capacity fit: closer to max batch size = better utilization
  const capacityScore = normalizeScore(
    orders.length,
    1,
    ENGINE_CONFIG.maxOrdersPerBatch
  );

  // Step 6: Weighted composite score
  const compositeScore = Math.round(
    distScore * weights.distanceSaving +
    timeScore * weights.timeSaving +
    detourScore * weights.detourPenalty +
    priorityScore * weights.priorityPenalty +
    capacityScore * weights.capacityFit
  );

  logger.debug("Batch scored", {
    orderCount: orders.length,
    compositeScore,
    distScore: Math.round(distScore),
    timeScore: Math.round(timeScore),
    detourScore: Math.round(detourScore),
    savingsPercent: Math.round(savingsPercent),
    maxDetourMin: optimized.maxDetourMin,
  });

  return buildCandidate(orders, optimized, compositeScore, savingsPercent);
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Calculate total distance and time if each order were delivered solo.
 */
function calculateSoloMetrics(
  orders: PoolOrder[],
  driverStart: GeoPoint
): { totalDistanceKm: number; totalTimeMin: number } {
  let totalDist = 0;
  let totalTime = 0;

  for (const order of orders) {
    const pickupDist = roadDistanceKm(driverStart, order.pickupPoint);
    const deliveryDist = roadDistanceKm(order.pickupPoint, order.deliveryPoint);
    totalDist += pickupDist + deliveryDist;

    const pickupTime = driveTimeMin(driverStart, order.pickupPoint);
    const deliveryTime = driveTimeMin(order.pickupPoint, order.deliveryPoint);
    totalTime +=
      pickupTime +
      ENGINE_CONFIG.driverPickupDwellMin +
      deliveryTime +
      ENGINE_CONFIG.driverDeliveryDwellMin;
  }

  return { totalDistanceKm: totalDist, totalTimeMin: totalTime };
}

/**
 * Normalize a value to 0–100 scale within a min–max range.
 */
function normalizeScore(value: number, min: number, max: number): number {
  if (max === min) return 50;
  const normalized = ((value - min) / (max - min)) * 100;
  return Math.max(0, Math.min(100, normalized));
}

function buildCandidate(
  orders: PoolOrder[],
  optimized: { stops: any[]; totalDistanceKm: number; totalTimeMin: number; maxDetourMin: number },
  score: number,
  savingsPercent: number
): BatchCandidate {
  return {
    orders,
    route: optimized.stops,
    totalDistanceKm: optimized.totalDistanceKm,
    totalTimeMin: optimized.totalTimeMin,
    maxDetourMin: optimized.maxDetourMin,
    savingsPercent: Math.round(savingsPercent * 100) / 100,
    score,
  };
}
