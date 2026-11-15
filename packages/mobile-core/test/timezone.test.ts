// node --test: an order's times are shown in its city's time zone (the API's
// `time_zone`), never the phone's. The phone here is set to a US zone and the
// order is in an Indian city, as on an emulator in America/Boise viewing a
// Hyderabad order. Node reads TZ when it is assigned, before any date is formatted.
process.env.TZ = "America/Boise";

import assert from "node:assert/strict";
import test from "node:test";

import { formatDate, formatTime, hourIn, inZone } from "../src/locale.ts";

const ORDER_ZONE = "Asia/Kolkata"; // the order's time_zone from GET /orders/{id}
const PLACED = "2026-11-14T13:35:00Z"; // 7:05 pm in the order's city, 6:35 am on the phone

test("the phone really is in a US zone", () => {
  assert.equal(new Date(PLACED).getHours(), 6);
  assert.equal(formatTime(PLACED, "en-IN"), "6:35 am"); // what the apps showed before: the phone's clock
});

test("an order's time and day are its city's, whatever the phone's zone", () => {
  assert.equal(formatTime(PLACED, "en-IN", inZone(ORDER_ZONE)), "7:05 pm");
  // 8 pm in the city is 7:30 am on the phone, still the 14th; 1 am in the city is the 15th there.
  assert.equal(formatDate("2026-11-14T19:30:00Z", "en-IN", inZone(ORDER_ZONE)), "15 Nov");
  assert.equal(formatDate("2026-11-14T19:30:00Z", "en-IN"), "14 Nov");
});

test("an unknown zone falls back to the format without it; no zone adds nothing", () => {
  assert.deepEqual(inZone(null), {});
  assert.deepEqual(inZone(undefined), {});
  assert.equal(formatTime(PLACED, "en-IN", { timeZone: "Nowhere/Nothing" }), "6:35 am");
});

test("a calendar day from the API is that day in any zone", () => {
  assert.equal(formatDate("2026-11-14", "en-IN"), "14 Nov");
  assert.equal(formatDate("2026-11-14", "en-IN", inZone(ORDER_ZONE)), "14 Nov");
  assert.equal(formatDate("2026-11-16", "en-IN", { weekday: "short", day: undefined, month: undefined }), "Mon");
});

test("the greeting's hour is the delivery city's", () => {
  assert.equal(hourIn(ORDER_ZONE, new Date(PLACED)), 19);
  assert.equal(hourIn(null, new Date(PLACED)), 6); // no zone known at all: the phone's clock
});
