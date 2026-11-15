// node --test: the website shows an order's times in its city's time zone (the
// API's `time_zone`) and greets by the delivery address's clock, never the
// visitor's device. The "device" here is in a US zone and the order is in an
// Indian city. Node reads TZ when it is assigned, before any date is formatted.
process.env.TZ = "America/Boise";

import assert from "node:assert/strict";
import test from "node:test";

import { date, hourIn, partOfDay, time } from "../src/lib/format.ts";

const ORDER_ZONE = "Asia/Kolkata"; // GET /orders/{id} -> time_zone
const PLACED = "2026-11-14T13:35:00Z"; // 7:05 pm in the order's city, 6:35 am on the device

test("the device really is in a US zone", () => {
  assert.equal(new Date(PLACED).getHours(), 6);
});

test("an order's time and day are its city's", () => {
  assert.equal(time(PLACED, "en-IN", ORDER_ZONE), "7:05 pm");
  assert.equal(date("2026-11-14T19:30:00Z", "en-IN", ORDER_ZONE), "15 Nov"); // 1 am the next day there
  assert.equal(time(PLACED, "en-IN", "Nowhere/Nothing"), "6:35 am"); // an unknown zone: still a time
});

test("a calendar day from the API is that day in any zone", () => {
  assert.equal(date("2026-11-14", "en-IN", ORDER_ZONE), "14 Nov");
  assert.equal(date("2026-11-14", "en-IN", null), "14 Nov");
});

test("the greeting is the delivery address's part of the day", () => {
  const now = new Date(PLACED);
  assert.equal(hourIn(ORDER_ZONE, now), 19);
  assert.equal(partOfDay(ORDER_ZONE, now), "evening");
  assert.equal(partOfDay(null, now), "morning"); // no zone known at all: the device's clock
});
