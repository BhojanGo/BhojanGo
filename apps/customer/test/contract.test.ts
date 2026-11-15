// node --test: the website's rules the customer app shows the same way (pure
// logic in lib/contract.ts, no React Native). Kitchens and offers here are test
// fixtures shaped like GET /api/v1/discover.
import assert from "node:assert/strict";
import test from "node:test";

import {
  activeOrder, boundsOf, cuisineTiles, distanceLeft, initials, kmBetween, minutesUntil, nextStop, ofCuisine, offerBadge, offerPayer,
  orderAgain, photoUrl, ratingOf, riderFirstName, type KitchenCard, type Offer, type Order,
} from "../lib/contract.ts";

const WEB = "https://web.example.test/";

test("photos: library paths resolve against the website, absolute URLs pass, the width is the asked one", () => {
  assert.equal(photoUrl("/food/paneer-tikka-800.webp", WEB, 400), "https://web.example.test/food/paneer-tikka-400.webp");
  assert.equal(photoUrl("https://cdn.example.test/a-400.webp", WEB, 1600), "https://cdn.example.test/a-1600.webp");
  assert.equal(photoUrl("https://cdn.example.test/a.jpg", null), "https://cdn.example.test/a.jpg");
  // no photo, or nowhere to resolve it: null (a text row or initials tile, never an empty frame)
  assert.equal(photoUrl(null, WEB), null);
  assert.equal(photoUrl("", WEB), null);
  assert.equal(photoUrl("/food/x-800.webp", ""), null);
  assert.equal(photoUrl("food/x-800.webp", WEB), null);
});

test("initials: letters of the first two words", () => {
  assert.equal(initials("Royal Paneer Kitchen"), "RP");
  assert.equal(initials("  dosa & co "), "DC");
  assert.equal(initials("7 Spices"), "S");
  assert.equal(initials(null), "");
});

test("ratings: New until 5 ratings, then the average and count", () => {
  assert.deepEqual(ratingOf({ rating: 4.8, review_count: 4 }), { new: true });
  assert.deepEqual(ratingOf({ rating: 4.6, review_count: 23 }), { new: false, stars: 4.6, count: 23 });
  assert.deepEqual(ratingOf({ rating_display: { new: true }, rating: 4.9, review_count: 40 }), { new: true });
  assert.deepEqual(ratingOf({ rating_display: { new: false, stars: 4.2, count: 7 } }), { new: false, stars: 4.2, count: 7 });
  assert.deepEqual(ratingOf({ rating: 0, review_count: 10 }), { new: true });
});

const card = (id: string, cuisines: string[], cover: string | null, extra: Partial<KitchenCard> = {}): KitchenCard => ({
  id, name: `Kitchen ${id}`, slug: `k-${id}`, path: `/x/y/k-${id}`, area: null, cover_url: cover, logo_url: null, cuisine_types: cuisines,
  delivery_fee: "30", distance: 1.2, eta_min: 20, eta_max: 30, free_delivery: false, is_new: false, offer: null, open_now: true,
  opens_at: null, rating: 4.5, rating_display: { new: false, stars: 4.5, count: 10 }, review_count: 10, tags: [], ...extra,
});

test("cuisines: the API's photos, one each, never twice; without photos from the API, 2+ kitchens and their covers", () => {
  const fromApi = cuisineTiles([
    { name: "Biryani", count: 3, photo: "/food/biryani-800.webp" },
    { name: "Dosa", count: 2, photo: "/food/biryani-800.webp" }, // the same photo again: left out
    { name: "Thali", count: 2 }, // no photo: left out
  ]);
  assert.deepEqual(fromApi.map((c) => c.name), ["Biryani"]);

  const kitchens = [card("1", ["Pizza"], "/food/a-800.webp"), card("2", ["pizza"], "/food/b-800.webp"), card("3", ["Tacos"], "/food/c-800.webp")];
  const older = cuisineTiles([{ name: "Pizza" }, { name: "Tacos" }], kitchens);
  assert.deepEqual(older, [{ name: "Pizza", count: 2, photo: "/food/a-800.webp" }]);
  assert.deepEqual(ofCuisine(kitchens, "PIZZA").map((k) => k.id), ["1", "2"]);
  assert.equal(ofCuisine(kitchens, null).length, 3);
});

test("offers say who pays", () => {
  const t = (key: string, vars?: Record<string, string | number>) => `${key}${vars ? JSON.stringify(vars) : ""}`;
  const money = (n: unknown) => `M${Number(n)}`;
  const kitchenPays: Offer = { id: "o1", template: "percent_off", percent: "10", funded_by: "restaurant", title: "x" };
  const wePay: Offer = { id: "o2", template: "free_delivery", funded_by: "platform", title: "x" };
  assert.equal(offerBadge(kitchenPays, t, money), 'offers.badge_kitchen_pays{"offer":"offers.percent_off{\\"percent\\":\\"10\\"}"}');
  assert.equal(offerBadge(wePay, t, money), 'offers.badge_we_pay{"offer":"offers.free_delivery"}');
  assert.equal(offerPayer(kitchenPays, t), "common.kitchen_pays_caps");
  assert.equal(offerPayer(wePay, t), "common.bhojango_pays");
});

const order = (id: string, status: string, restaurant: string, extra: Record<string, unknown> = {}) =>
  ({ id, status, restaurant_id: restaurant, restaurant_name: `K${restaurant}`, ...extra }) as unknown as Order;

test("orders: the active one, the rider's first name, order again once per kitchen", () => {
  const orders = [order("a", "delivered", "1"), order("b", "picked_up", "2"), order("c", "delivered", "1"), order("d", "delivered", "3"),
    order("e", "cancelled", "4")];
  assert.equal(activeOrder(orders)?.id, "b");
  assert.equal(activeOrder([order("x", "delivered", "1")]), null);
  assert.deepEqual(orderAgain(orders).map((o) => o.id), ["a", "d"]);
  assert.equal(riderFirstName({ rider_first_name: "Venkat Rao" }), "Venkat");
  assert.equal(riderFirstName({ rider: { first_name: "Ana" } }), "Ana");
  assert.equal(riderFirstName({}), null);
  assert.equal(minutesUntil(new Date(10 * 60000).toISOString(), 0), 10);
  assert.equal(minutesUntil(new Date(0).toISOString(), 60000), 1);
  assert.equal(minutesUntil(null), null);
});

test("tracking: the next stop, distance left from the ETA (else the straight line), the map's bounds", () => {
  const kitchen: [number, number] = [10, 20];
  const home: [number, number] = [10.01, 20.01];
  assert.deepEqual(nextStop("preparing", kitchen, home), kitchen);
  assert.deepEqual(nextStop("picked_up", kitchen, home), home);
  const eta = { to_pickup_minutes: 0, to_customer_minutes: 6, arrives_at: "2026-11-15T10:00:00Z", distance_left: "1.4", distance_unit: "mi" };
  assert.deepEqual(distanceLeft(eta, kitchen, home), { value: 1.4, unit: "mi", km: false });
  const straight = distanceLeft({ ...eta, distance_left: null }, kitchen, home);
  assert.equal(straight?.km, true);
  assert.ok(Math.abs((straight?.value ?? 0) - kmBetween(kitchen, home)) < 1e-9);
  assert.equal(distanceLeft(null, null, home), null);
  assert.deepEqual(boundsOf([kitchen, null, home], 0), [20, 10, 20.01, 10.01]);
  assert.equal(boundsOf([null]), null);
});
