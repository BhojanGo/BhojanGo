/**
 * Route Optimizer — determines the best stop sequence for a batch.
 *
 * Strategy:
 *   For 2-3 orders (our MVP), we use exhaustive permutation since the
 *   search space is tiny (at most 6! / constraints = ~dozen valid routes).
 *
 *   Constraints:
 *     - All pickups for an order must happen BEFORE its delivery
 *     - Pickup sequence should respect prep_ready_at (don't arrive early)
 *     - Minimize total route time
 *
 *   For future scale (4+ orders, grocery/parcel):
 *     - Swap to Google Routes Optimization API or OR-Tools
 *     - This module is the single place to change
 */

import { GeoPoint, PoolOrder, RouteStop } from "../types";
import { ENGINE_CONFIG } from "../config";
import { roadDistanceKm, driveTimeMin } from "../utils/geo";

interface OptimizedRoute {
  stops: RouteStop[];
  totalDistanceKm: number;
  totalTimeMin: number;
  maxDetourMin: number;       // worst detour vs solo delivery for any order
  perOrderDetour: Map<string, number>;
}

/**
 * Given a set of orders and a driver start point, find the optimal
 * pickup-then-delivery route.
 *
 * For MVP (max 3 orders = 6 stops), we try all valid permutations.
 */
export function optimizeRoute(
  orders: PoolOrder[],
  driverStart: GeoPoint
): OptimizedRoute {
  if (orders.length === 0) {
    return { stops: [], totalDistanceKm: 0, totalTimeMin: 0, maxDetourMin: 0, perOrderDetour: new Map() };
  }

  // Single order — trivial route: pickup → delivery
  if (orders.length === 1) {
    return buildSingleRoute(orders[0], driverStart);
  }

  // Multi-order — try all valid permutations
  const pickups: StopDef[] = orders.map((o) => ({
    orderId: o.orderId,
    type: "pickup" as const,
    point: o.pickupPoint,
    readyAt: o.prepReadyAt,
    dwellMin: ENGINE_CONFIG.driverPickupDwellMin,
  }));

  const deliveries: StopDef[] = orders.map((o) => ({
    orderId: o.orderId,
    type: "delivery" as const,
    point: o.deliveryPoint,
    readyAt: null,
    dwellMin: ENGINE_CONFIG.driverDeliveryDwellMin,
  }));

  // Calculate solo delivery times for detour comparison
  const soloTimes = new Map<string, number>();
  for (const order of orders) {
    const pickupTime = driveTimeMin(driverStart, order.pickupPoint);
    const deliveryTime = driveTimeMin(order.pickupPoint, order.deliveryPoint);
    soloTimes.set(order.orderId, pickupTime + ENGINE_CONFIG.driverPickupDwellMin + deliveryTime);
  }

  // Generate all valid permutations of stops
  // Constraint: pickup(order_i) must come before delivery(order_i)
  const allStops = [...pickups, ...deliveries];
  const validRoutes = generateValidPermutations(allStops, orders.map((o) => o.orderId));

  let bestRoute: OptimizedRoute | null = null;

  for (const perm of validRoutes) {
    const route = evaluatePermutation(perm, driverStart, soloTimes);
    if (!bestRoute || route.totalTimeMin < bestRoute.totalTimeMin) {
      // Check max detour constraint
      if (route.maxDetourMin <= ENGINE_CONFIG.maxDetourMinutes) {
        bestRoute = route;
      }
    }
  }

  // Fallback: if no route meets detour constraint, return best anyway
  // (the scorer will penalize it or the builder will reject it)
  if (!bestRoute) {
    const fallback = evaluatePermutation(
      [...pickups, ...deliveries], // naive: all pickups then all deliveries
      driverStart,
      soloTimes
    );
    return fallback;
  }

  return bestRoute;
}

// ── Internals ───────────────────────────────────────────────────────────────

interface StopDef {
  orderId: string;
  type: "pickup" | "delivery";
  point: GeoPoint;
  readyAt: Date | null;
  dwellMin: number;
}

/**
 * Build trivial single-order route.
 */
function buildSingleRoute(order: PoolOrder, driverStart: GeoPoint): OptimizedRoute {
  const now = new Date();
  const pickupDrive = driveTimeMin(driverStart, order.pickupPoint);
  const deliveryDrive = driveTimeMin(order.pickupPoint, order.deliveryPoint);
  const totalTime = pickupDrive + ENGINE_CONFIG.driverPickupDwellMin + deliveryDrive + ENGINE_CONFIG.driverDeliveryDwellMin;
  const totalDist = roadDistanceKm(driverStart, order.pickupPoint) + roadDistanceKm(order.pickupPoint, order.deliveryPoint);

  const pickupArrival = new Date(now.getTime() + pickupDrive * 60_000);
  const deliveryArrival = new Date(
    pickupArrival.getTime() + (ENGINE_CONFIG.driverPickupDwellMin + deliveryDrive) * 60_000
  );

  const stops: RouteStop[] = [
    {
      sequence: 1,
      type: "pickup",
      orderId: order.orderId,
      point: order.pickupPoint,
      estimatedArrivalAt: pickupArrival,
      estimatedDwellMin: ENGINE_CONFIG.driverPickupDwellMin,
    },
    {
      sequence: 2,
      type: "delivery",
      orderId: order.orderId,
      point: order.deliveryPoint,
      estimatedArrivalAt: deliveryArrival,
      estimatedDwellMin: ENGINE_CONFIG.driverDeliveryDwellMin,
    },
  ];

  return {
    stops,
    totalDistanceKm: Math.round(totalDist * 100) / 100,
    totalTimeMin: Math.round(totalTime * 100) / 100,
    maxDetourMin: 0,
    perOrderDetour: new Map([[order.orderId, 0]]),
  };
}

/**
 * Generate permutations where every pickup comes before its delivery.
 * For N orders (2N stops), this is manageable up to N=3 (720 perms max,
 * ~90 valid after constraint filtering).
 */
function generateValidPermutations(stops: StopDef[], orderIds: string[]): StopDef[][] {
  const results: StopDef[][] = [];

  function permute(current: StopDef[], remaining: StopDef[]) {
    if (remaining.length === 0) {
      results.push([...current]);
      return;
    }

    // Prune early: cap results at 500 to avoid perf issues
    if (results.length >= 500) return;

    for (let i = 0; i < remaining.length; i++) {
      const stop = remaining[i];

      // Constraint: delivery can only happen after its pickup
      if (stop.type === "delivery") {
        const pickupDone = current.some(
          (s) => s.orderId === stop.orderId && s.type === "pickup"
        );
        if (!pickupDone) continue;
      }

      current.push(stop);
      const next = [...remaining.slice(0, i), ...remaining.slice(i + 1)];
      permute(current, next);
      current.pop();
    }
  }

  permute([], stops);
  return results;
}

/**
 * Evaluate a specific stop permutation: compute distance, time, detours.
 */
function evaluatePermutation(
  stops: StopDef[],
  driverStart: GeoPoint,
  soloTimes: Map<string, number>
): OptimizedRoute {
  const now = new Date();
  let currentPoint = driverStart;
  let currentTime = now.getTime();
  let totalDist = 0;

  const routeStops: RouteStop[] = [];
  const deliveryTimes = new Map<string, number>(); // orderId → delivery time from start (min)
  const pickupTimes = new Map<string, number>();

  for (let i = 0; i < stops.length; i++) {
    const stop = stops[i];
    const legDist = roadDistanceKm(currentPoint, stop.point);
    const legTime = driveTimeMin(currentPoint, stop.point);

    totalDist += legDist;
    currentTime += legTime * 60_000;

    // If it's a pickup and food isn't ready, wait
    if (stop.type === "pickup" && stop.readyAt) {
      const readyTime = stop.readyAt.getTime();
      if (currentTime < readyTime) {
        currentTime = readyTime;
      }
    }

    const arrivalAt = new Date(currentTime);

    routeStops.push({
      sequence: i + 1,
      type: stop.type,
      orderId: stop.orderId,
      point: stop.point,
      estimatedArrivalAt: arrivalAt,
      estimatedDwellMin: stop.dwellMin,
    });

    if (stop.type === "pickup") {
      pickupTimes.set(stop.orderId, (currentTime - now.getTime()) / 60_000);
    } else {
      deliveryTimes.set(stop.orderId, (currentTime - now.getTime()) / 60_000);
    }

    currentTime += stop.dwellMin * 60_000;
    currentPoint = stop.point;
  }

  const totalTimeMin = (currentTime - now.getTime()) / 60_000;

  // Calculate per-order detour (how much longer vs solo delivery)
  const perOrderDetour = new Map<string, number>();
  let maxDetour = 0;

  for (const [orderId, batchedTime] of deliveryTimes) {
    const solo = soloTimes.get(orderId) ?? batchedTime;
    const detour = Math.max(0, batchedTime - solo);
    perOrderDetour.set(orderId, Math.round(detour * 100) / 100);
    maxDetour = Math.max(maxDetour, detour);
  }

  return {
    stops: routeStops,
    totalDistanceKm: Math.round(totalDist * 100) / 100,
    totalTimeMin: Math.round(totalTimeMin * 100) / 100,
    maxDetourMin: Math.round(maxDetour * 100) / 100,
    perOrderDetour,
  };
}
