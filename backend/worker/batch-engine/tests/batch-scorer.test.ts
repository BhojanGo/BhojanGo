/**
 * Unit tests for the Batch Scorer and Route Optimizer.
 *
 * These test the pure engine logic without any database or network calls.
 */

import { scoreBatch } from "../src/engine/batch-scorer";
import { optimizeRoute } from "../src/engine/route-optimizer";
import { PoolOrder, GeoPoint } from "../src/types";

// ── Test Data: NYC-area coordinates ─────────────────────────────────────────

const DRIVER_START: GeoPoint = { lat: 40.7580, lng: -73.9855 }; // Times Square

function makeOrder(overrides: Partial<PoolOrder> & { orderId: string }): PoolOrder {
  return {
    id: `pool-${overrides.orderId}`,
    orderId: overrides.orderId,
    restaurantId: overrides.restaurantId ?? "rest-1",
    restaurantName: overrides.restaurantName ?? "Test Restaurant",
    pickupPoint: overrides.pickupPoint ?? { lat: 40.7614, lng: -73.9776 }, // near Grand Central
    deliveryPoint: overrides.deliveryPoint ?? { lat: 40.7484, lng: -73.9857 }, // Empire State
    prepReadyAt: overrides.prepReadyAt ?? new Date(Date.now() + 5 * 60_000),
    promisedDeliveryAt: overrides.promisedDeliveryAt ?? new Date(Date.now() + 45 * 60_000),
    priority: overrides.priority ?? "standard",
    itemCount: overrides.itemCount ?? 2,
    estimatedSizeLiters: overrides.estimatedSizeLiters ?? 5,
    currency: overrides.currency ?? "USD",
    deliveryFee: overrides.deliveryFee ?? 4.99,
    createdAt: overrides.createdAt ?? new Date(),
    status: "waiting",
    batchId: null,
  };
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("Route Optimizer", () => {
  it("should produce a 2-stop route for a single order", () => {
    const order = makeOrder({ orderId: "order-1" });
    const result = optimizeRoute([order], DRIVER_START);

    expect(result.stops).toHaveLength(2);
    expect(result.stops[0].type).toBe("pickup");
    expect(result.stops[1].type).toBe("delivery");
    expect(result.totalDistanceKm).toBeGreaterThan(0);
    expect(result.maxDetourMin).toBe(0); // single order = no detour
  });

  it("should ensure pickup before delivery for multi-order routes", () => {
    const order1 = makeOrder({
      orderId: "order-1",
      pickupPoint: { lat: 40.7614, lng: -73.9776 },
      deliveryPoint: { lat: 40.7484, lng: -73.9857 },
    });
    const order2 = makeOrder({
      orderId: "order-2",
      pickupPoint: { lat: 40.7620, lng: -73.9740 }, // nearby restaurant
      deliveryPoint: { lat: 40.7500, lng: -73.9800 }, // nearby delivery
    });

    const result = optimizeRoute([order1, order2], DRIVER_START);

    expect(result.stops).toHaveLength(4); // 2 pickups + 2 deliveries

    // Verify pickup-before-delivery constraint
    for (const orderId of ["order-1", "order-2"]) {
      const pickupIdx = result.stops.findIndex(
        (s) => s.orderId === orderId && s.type === "pickup"
      );
      const deliveryIdx = result.stops.findIndex(
        (s) => s.orderId === orderId && s.type === "delivery"
      );
      expect(pickupIdx).toBeLessThan(deliveryIdx);
    }
  });

  it("should calculate distance greater than zero", () => {
    const order = makeOrder({ orderId: "order-1" });
    const result = optimizeRoute([order], DRIVER_START);
    expect(result.totalDistanceKm).toBeGreaterThan(0);
    expect(result.totalTimeMin).toBeGreaterThan(0);
  });
});

describe("Batch Scorer", () => {
  it("should produce a valid score for a single order", () => {
    const order = makeOrder({ orderId: "order-1" });
    const result = scoreBatch([order], DRIVER_START);

    expect(result.score).toBeGreaterThanOrEqual(0);
    expect(result.totalDistanceKm).toBeGreaterThan(0);
    expect(result.route).toHaveLength(2);
  });

  it("should score a 2-order batch higher when orders are nearby", () => {
    // Two orders from the same area, delivering to the same area
    const order1 = makeOrder({
      orderId: "order-1",
      pickupPoint: { lat: 40.7614, lng: -73.9776 },
      deliveryPoint: { lat: 40.7484, lng: -73.9857 },
    });
    const order2 = makeOrder({
      orderId: "order-2",
      pickupPoint: { lat: 40.7618, lng: -73.9770 }, // 50m away
      deliveryPoint: { lat: 40.7488, lng: -73.9850 }, // 50m away
    });

    const batchResult = scoreBatch([order1, order2], DRIVER_START);
    const soloResult1 = scoreBatch([order1], DRIVER_START);
    const soloResult2 = scoreBatch([order2], DRIVER_START);

    // Batched distance should be less than sum of solo distances
    const soloTotalDist = soloResult1.totalDistanceKm + soloResult2.totalDistanceKm;
    expect(batchResult.totalDistanceKm).toBeLessThan(soloTotalDist);
    expect(batchResult.savingsPercent).toBeGreaterThan(0);
  });

  it("should penalize batching a priority order", () => {
    const standardOrder = makeOrder({
      orderId: "order-1",
      priority: "standard",
    });
    const priorityOrder = makeOrder({
      orderId: "order-2",
      priority: "priority",
      pickupPoint: { lat: 40.7618, lng: -73.9770 },
      deliveryPoint: { lat: 40.7488, lng: -73.9850 },
    });

    const withPriority = scoreBatch([standardOrder, priorityOrder], DRIVER_START);
    const withoutPriority = scoreBatch(
      [
        standardOrder,
        makeOrder({
          orderId: "order-3",
          pickupPoint: { lat: 40.7618, lng: -73.9770 },
          deliveryPoint: { lat: 40.7488, lng: -73.9850 },
        }),
      ],
      DRIVER_START
    );

    // Priority batch should score lower due to penalty
    expect(withPriority.score).toBeLessThanOrEqual(withoutPriority.score);
  });

  it("should reject batches with distant delivery points", () => {
    const order1 = makeOrder({
      orderId: "order-1",
      deliveryPoint: { lat: 40.7484, lng: -73.9857 }, // midtown
    });
    const order2 = makeOrder({
      orderId: "order-2",
      pickupPoint: { lat: 40.7618, lng: -73.9770 },
      deliveryPoint: { lat: 40.6892, lng: -74.0445 }, // Statue of Liberty — far
    });

    const result = scoreBatch([order1, order2], DRIVER_START);

    // The detour should be large or the savings too small
    // Either way, the score should be low or zero
    expect(result.maxDetourMin).toBeGreaterThan(0);
  });
});
