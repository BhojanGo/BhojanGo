// node --test: with the phone in a US zone, an order in an Indian city reads in
// that city's time and the greeting follows the delivery address's clock, never
// the phone's. Node reads TZ when it is assigned, before any date is formatted.
process.env.TZ = "America/Boise";

import assert from "node:assert/strict";
import test from "node:test";

import { formatDate, formatTime, hourIn, inZone } from "../../../packages/mobile-core/src/locale.ts";
import { greetingZone, partOfDayAt, type Order } from "../lib/contract.ts";

// The fields of GET /orders/{id} the receipt and tracking read (a fixture).
const order = { placed_at: "2026-11-14T13:35:00Z", estimated_delivery_time: "2026-11-14T14:05:00Z", time_zone: "Asia/Kolkata" } as
  Pick<Order, "placed_at" | "estimated_delivery_time" | "time_zone">;

test("the receipt and tracking show the order's city time, not the phone's", () => {
  assert.equal(new Date(order.placed_at!).getHours(), 6); // the phone: 6:35 am
  const tz = inZone(order.time_zone);
  assert.equal(formatTime(order.placed_at!, "en-IN", tz), "7:05 pm");
  assert.equal(formatDate(order.placed_at!, "en-IN", tz), "14 Nov");
  assert.equal(formatTime(order.estimated_delivery_time!, "en-IN", tz), "7:35 pm"); // "Around 7:35 pm"
});

test("the greeting is the delivery address's part of the day", () => {
  const now = new Date(order.placed_at!); // 7:05 pm there, 6:35 am on the phone
  assert.equal(partOfDayAt(hourIn(greetingZone("Asia/Kolkata", "UTC"), now)), "evening");
  // no city yet (no address): the country's zone from Markets, still not the phone's
  assert.equal(partOfDayAt(hourIn(greetingZone(null, "Asia/Kolkata"), now)), "evening");
  assert.equal(greetingZone(undefined, undefined), null);
  assert.equal(partOfDayAt(6), "morning");
  assert.equal(partOfDayAt(13), "afternoon");
  assert.equal(partOfDayAt(23), "night");
});
