/**
 * Unit tests for batch CREATION (runBatchCycle) — the grouping + selection logic
 * that turns a pool of waiting orders into driver batches. Pure, no DB/network.
 */

import { runBatchCycle } from "../src/engine/batch-builder";
import { PoolOrder, GeoPoint } from "../src/types";

const DRIVER_START: GeoPoint = { lat: 40.758, lng: -73.9855 }; // Times Square

function makeOrder(overrides: Partial<PoolOrder> & { orderId: string }): PoolOrder {
  return {
    id: `pool-${overrides.orderId}`,
    orderId: overrides.orderId,
    restaurantId: overrides.restaurantId ?? "rest-1",
    restaurantName: overrides.restaurantName ?? "Test Restaurant",
    pickupPoint: overrides.pickupPoint ?? { lat: 40.7614, lng: -73.9776 },
    deliveryPoint: overrides.deliveryPoint ?? { lat: 40.7484, lng: -73.9857 },
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

describe("Batch Creation (runBatchCycle)", () => {
  it("returns no batches for an empty pool", () => {
    const result = runBatchCycle([], DRIVER_START);
    expect(result.batches).toHaveLength(0);
    expect(result.expiredOrderIds).toHaveLength(0);
  });

  it("groups two nearby orders into a single multi-order batch", () => {
    const order1 = makeOrder({
      orderId: "order-1",
      pickupPoint: { lat: 40.7614, lng: -73.9776 },
      deliveryPoint: { lat: 40.7484, lng: -73.9857 },
    });
    const order2 = makeOrder({
      orderId: "order-2",
      pickupPoint: { lat: 40.7618, lng: -73.977 }, // ~50 m from order1 pickup
      deliveryPoint: { lat: 40.7488, lng: -73.985 }, // ~50 m from order1 delivery
    });

    const result = runBatchCycle([order1, order2], DRIVER_START);

    const multi = result.batches.find((b) => b.orders.length === 2);
    expect(multi).toBeDefined();
    // One driver per batch -> both orders ride together, no order appears twice
    const ids = result.batches.flatMap((b) => b.orders.map((o) => o.orderId));
    expect(new Set(ids).size).toBe(ids.length);
    // The batch carries an ordered route sequence (pickups + deliveries)
    expect(multi!.route.length).toBe(4);
  });

  it("does not batch orders whose deliveries are far apart", () => {
    const order1 = makeOrder({
      orderId: "order-1",
      deliveryPoint: { lat: 40.7484, lng: -73.9857 }, // midtown
    });
    const order2 = makeOrder({
      orderId: "order-2",
      pickupPoint: { lat: 40.7618, lng: -73.977 },
      deliveryPoint: { lat: 40.6892, lng: -74.0445 }, // far (Statue of Liberty)
    });

    const result = runBatchCycle([order1, order2], DRIVER_START);
    const multi = result.batches.filter((b) => b.orders.length > 1);
    expect(multi).toHaveLength(0);
  });

  it("ships a long-waiting (expired) order solo", () => {
    const stale = makeOrder({
      orderId: "order-stale",
      createdAt: new Date(Date.now() - 60 * 60_000), // an hour ago
    });
    const result = runBatchCycle([stale], DRIVER_START);
    expect(result.expiredOrderIds).toContain("order-stale");
    const solo = result.batches.find(
      (b) => b.orders.length === 1 && b.orders[0].orderId === "order-stale"
    );
    expect(solo).toBeDefined();
  });
});
