/**
 * Batch Builder — the core engine loop.
 *
 * Called every BATCH_CYCLE_SECONDS, it:
 *   1. Pulls all "waiting" orders from the pool
 *   2. Groups orders by pickup proximity (nearby restaurants)
 *   3. Within each group, tries all 2-order and 3-order combos
 *   4. Scores each candidate batch
 *   5. Selects the highest-scoring non-overlapping batches (greedy)
 *   6. Marks unmatched orders as single-delivery if they've waited too long
 *   7. Returns the winning batches for assignment
 *
 * Design decisions:
 *   - Greedy assignment (not global optimum) is acceptable for MVP.
 *     Global optimization (Hungarian algorithm, etc.) is future work.
 *   - Orders are never forced into bad batches. If no good batch exists,
 *     the order ships solo after maxWaitInPoolMinutes.
 */

import { PoolOrder, BatchCandidate, GeoPoint } from "../types";
import { ENGINE_CONFIG } from "../config";
import { isWithinRadius, centroid } from "../utils/geo";
import { scoreBatch } from "./batch-scorer";
import { logger } from "../utils/logger";

export interface CycleResult {
  batches: BatchCandidate[];
  expiredOrderIds: string[];   // orders that exceeded pool wait time
  cycleTimeMs: number;
}

/**
 * Run one batch-formation cycle.
 *
 * @param waitingOrders  All orders currently in "waiting" status
 * @param driverStart    Approximate driver start point (centroid of city, or
 *                       nearest available driver — simplified for MVP)
 */
export function runBatchCycle(
  waitingOrders: PoolOrder[],
  driverStart: GeoPoint
): CycleResult {
  const startTime = Date.now();

  if (waitingOrders.length === 0) {
    return { batches: [], expiredOrderIds: [], cycleTimeMs: Date.now() - startTime };
  }

  // Step 1: Separate expired orders
  const now = new Date();
  const maxWaitMs = ENGINE_CONFIG.maxWaitInPoolMinutes * 60_000;
  const expired: PoolOrder[] = [];
  const eligible: PoolOrder[] = [];

  for (const order of waitingOrders) {
    const waitTime = now.getTime() - order.createdAt.getTime();
    if (waitTime > maxWaitMs) {
      expired.push(order);
    } else {
      eligible.push(order);
    }
  }

  // Step 2: Remove priority orders if batching is disabled for them
  const batchable: PoolOrder[] = [];
  const soloOnly: PoolOrder[] = [];

  for (const order of eligible) {
    if (order.priority === "priority" && !ENGINE_CONFIG.priorityOrderBatchable) {
      soloOnly.push(order);
    } else {
      batchable.push(order);
    }
  }

  // Step 3: Group batchable orders by pickup proximity
  const groups = groupByPickupProximity(batchable);

  logger.info("Batch cycle started", {
    totalWaiting: waitingOrders.length,
    eligible: eligible.length,
    batchable: batchable.length,
    soloOnly: soloOnly.length,
    expired: expired.length,
    pickupGroups: groups.length,
  });

  // Step 4: For each group, generate and score candidate batches
  const allCandidates: BatchCandidate[] = [];

  for (const group of groups) {
    const candidates = generateCandidates(group, driverStart);
    allCandidates.push(...candidates);
  }

  // Step 5: Greedy selection — pick highest-scoring batches,
  // ensuring no order appears in multiple batches
  const selectedBatches = greedySelect(allCandidates);

  // Step 6: Create single-delivery batches for:
  //   - Priority-only orders
  //   - Expired orders
  //   - Unmatched orders (sat through a cycle with no good batch)
  const matchedOrderIds = new Set(
    selectedBatches.flatMap((b) => b.orders.map((o) => o.orderId))
  );

  for (const order of soloOnly) {
    const solo = scoreBatch([order], driverStart);
    selectedBatches.push(solo);
  }

  for (const order of expired) {
    const solo = scoreBatch([order], driverStart);
    selectedBatches.push(solo);
  }

  const cycleTimeMs = Date.now() - startTime;

  logger.info("Batch cycle complete", {
    batchesFormed: selectedBatches.length,
    multiOrderBatches: selectedBatches.filter((b) => b.orders.length > 1).length,
    ordersMatched: selectedBatches.reduce((sum, b) => sum + b.orders.length, 0),
    expiredOrders: expired.length,
    cycleTimeMs,
  });

  return {
    batches: selectedBatches,
    expiredOrderIds: expired.map((o) => o.orderId),
    cycleTimeMs,
  };
}

// ── Grouping ────────────────────────────────────────────────────────────────

/**
 * Cluster orders by pickup proximity.
 * Orders from the same restaurant or restaurants within maxPickupRadiusKm
 * end up in the same group.
 *
 * Uses simple greedy clustering (not DBSCAN) — sufficient for MVP.
 */
function groupByPickupProximity(orders: PoolOrder[]): PoolOrder[][] {
  const groups: PoolOrder[][] = [];
  const assigned = new Set<string>();

  // Sort by restaurant to naturally cluster same-restaurant orders
  const sorted = [...orders].sort((a, b) =>
    a.restaurantId.localeCompare(b.restaurantId)
  );

  for (const order of sorted) {
    if (assigned.has(order.orderId)) continue;

    const group: PoolOrder[] = [order];
    assigned.add(order.orderId);

    // Find other orders with nearby pickup points
    for (const other of sorted) {
      if (assigned.has(other.orderId)) continue;
      if (
        isWithinRadius(
          order.pickupPoint,
          other.pickupPoint,
          ENGINE_CONFIG.maxPickupRadiusKm
        )
      ) {
        group.push(other);
        assigned.add(other.orderId);
      }
    }

    groups.push(group);
  }

  return groups;
}

// ── Candidate Generation ────────────────────────────────────────────────────

/**
 * For a group of nearby-pickup orders, generate all valid batch combinations
 * (pairs and triples) and score each one.
 */
function generateCandidates(
  group: PoolOrder[],
  driverStart: GeoPoint
): BatchCandidate[] {
  const candidates: BatchCandidate[] = [];
  const maxSize = Math.min(group.length, ENGINE_CONFIG.maxOrdersPerBatch);

  // Also check delivery proximity — orders going in opposite directions
  // shouldn't be batched even if pickups are close

  // Generate pairs
  if (maxSize >= 2) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        if (isDeliveryCompatible(group[i], group[j])) {
          const candidate = scoreBatch([group[i], group[j]], driverStart);
          if (candidate.score > 0) {
            candidates.push(candidate);
          }
        }
      }
    }
  }

  // Generate triples
  if (maxSize >= 3) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        for (let k = j + 1; k < group.length; k++) {
          if (
            isDeliveryCompatible(group[i], group[j]) &&
            isDeliveryCompatible(group[j], group[k]) &&
            isDeliveryCompatible(group[i], group[k])
          ) {
            const candidate = scoreBatch(
              [group[i], group[j], group[k]],
              driverStart
            );
            if (candidate.score > 0) {
              candidates.push(candidate);
            }
          }
        }
      }
    }
  }

  return candidates;
}

/**
 * Check if two orders have compatible delivery locations.
 * They must be within maxDeliveryRadiusKm of each other.
 */
function isDeliveryCompatible(a: PoolOrder, b: PoolOrder): boolean {
  return isWithinRadius(
    a.deliveryPoint,
    b.deliveryPoint,
    ENGINE_CONFIG.maxDeliveryRadiusKm
  );
}

// ── Greedy Selection ────────────────────────────────────────────────────────

/**
 * From all scored candidates, greedily pick the highest-scoring batches
 * such that no order appears in more than one batch.
 */
function greedySelect(candidates: BatchCandidate[]): BatchCandidate[] {
  // Sort by score descending, then by order count descending (prefer bigger batches)
  const sorted = [...candidates].sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return b.orders.length - a.orders.length;
  });

  const selected: BatchCandidate[] = [];
  const usedOrderIds = new Set<string>();

  for (const candidate of sorted) {
    const orderIds = candidate.orders.map((o) => o.orderId);
    const conflict = orderIds.some((id) => usedOrderIds.has(id));

    if (!conflict) {
      selected.push(candidate);
      orderIds.forEach((id) => usedOrderIds.add(id));
    }
  }

  return selected;
}
