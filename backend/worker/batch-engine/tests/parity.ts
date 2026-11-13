/**
 * Reference numbers for the Python port (backend/worker/app/batching/engine.py).
 * Runs this TypeScript engine on fixed Boise and Hyderabad scenarios and prints
 * the inputs and results as JSON; backend/worker/tests/fixtures/batch_parity.json
 * is its output, and test_batching.py requires the Python engine to match it.
 *
 *   docker run --rm -v "$PWD/backend/worker/batch-engine:/e" -w /e node:24-slim \
 *     npx -y tsx@4.19.2 tests/parity.ts > backend/worker/tests/fixtures/batch_parity.json
 *
 * Times are relative to "now" (minutes), because the engine reads the clock.
 */
import { scoreBatch } from "../src/engine/batch-scorer";
import { runBatchCycle } from "../src/engine/batch-builder";
import { GeoPoint, PoolOrder } from "../src/types";

interface In { id: string; rest: string; pickup: [number, number]; drop: [number, number]; readyIn: number; ago: number; priority?: string }

const KITCHENS: Record<string, [number, number]> = {
  bowl: [43.6295, -116.2008], basque: [43.6142, -116.199], tandoor: [43.5905, -116.233],
  pizza: [43.632, -116.211], spud: [43.6145, -116.2035], spice: [17.4483, 78.3915],
};
const START: Record<string, GeoPoint> = { boise: { lat: 43.615, lng: -116.2023 }, hyd: { lat: 17.4486, lng: 78.3908 } };

let seed = 7;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
function order(id: string, rest: string, spread = 0.02, readyIn = 4, ago = 1): In {
  const [lat, lng] = KITCHENS[rest];
  return { id, rest, pickup: [lat, lng], drop: [+(lat + (rnd() - 0.5) * spread).toFixed(5), +(lng + (rnd() - 0.5) * spread).toFixed(5)], readyIn, ago };
}
function toPool(o: In): PoolOrder {
  const now = Date.now();
  return {
    id: `pool-${o.id}`, orderId: o.id, restaurantId: o.rest, restaurantName: o.rest,
    pickupPoint: { lat: o.pickup[0], lng: o.pickup[1] }, deliveryPoint: { lat: o.drop[0], lng: o.drop[1] },
    prepReadyAt: new Date(now + o.readyIn * 60_000), promisedDeliveryAt: new Date(now + 45 * 60_000),
    priority: (o.priority ?? "standard") as PoolOrder["priority"], itemCount: 2, estimatedSizeLiters: 5,
    currency: "USD", deliveryFee: 2.99, createdAt: new Date(now - o.ago * 60_000), status: "waiting", batchId: null,
  };
}

const scoreCases: { name: string; start: string; orders: In[] }[] = [];
for (let i = 0; i < 12; i++) {
  const r = Object.keys(KITCHENS).slice(0, 5)[i % 5];
  const r2 = i % 3 === 0 ? r : Object.keys(KITCHENS).slice(0, 5)[(i + 1) % 5];
  scoreCases.push({ name: `pair-${i}`, start: "boise", orders: [order(`a${i}`, r, 0.01 + i * 0.004, i % 4), order(`b${i}`, r2, 0.01 + i * 0.004, (i * 3) % 7)] });
}
for (let i = 0; i < 4; i++) {
  scoreCases.push({ name: `triple-${i}`, start: "boise", orders: [order(`t${i}a`, "bowl", 0.012), order(`t${i}b`, "pizza", 0.012), order(`t${i}c`, "bowl", 0.012, 6)] });
}
scoreCases.push({ name: "solo", start: "hyd", orders: [order("s1", "spice", 0.03, 3)] });
const pri = order("p2", "spice", 0.008, 2); pri.priority = "priority";
scoreCases.push({ name: "priority-pair", start: "hyd", orders: [order("p1", "spice", 0.008, 2), pri] });

const cycleCases: { name: string; start: string; orders: In[] }[] = [
  { name: "rush-boise", start: "boise", orders: Array.from({ length: 10 }, (_, i) => order(`r${i}`, Object.keys(KITCHENS)[i % 5], 0.02, i % 6, i % 4)) },
  { name: "with-expired", start: "boise", orders: [order("e1", "bowl", 0.01, 2, 9), order("e2", "bowl", 0.01, 2, 1), order("e3", "bowl", 0.01, 3, 1)] },
  { name: "same-kitchen-hyd", start: "hyd", orders: Array.from({ length: 6 }, (_, i) => order(`h${i}`, "spice", 0.015, i % 5, 1)) },
];

const out = {
  scores: scoreCases.map((c) => {
    const r = scoreBatch(c.orders.map(toPool), START[c.start]);
    return { ...c, score: r.score, totalDistanceKm: r.totalDistanceKm, totalTimeMin: r.totalTimeMin,
             maxDetourMin: r.maxDetourMin, savingsPercent: r.savingsPercent, route: r.route.map((s) => `${s.type}:${s.orderId}`) };
  }),
  cycles: cycleCases.map((c) => {
    const r = runBatchCycle(c.orders.map(toPool), START[c.start]);
    return { ...c, expired: r.expiredOrderIds, batches: r.batches.map((b) => ({ orders: b.orders.map((o) => o.orderId), score: b.score })) };
  }),
};
process.stdout.write(JSON.stringify(out, null, 1) + "\n");
