// node --test: admin shows an order's times on its city's clock with the zone (R27), not the viewer's.
import assert from "node:assert/strict";
import test from "node:test";

process.env.TZ = "Asia/Kolkata"; // a viewer in India looking at a Boise order

const { cityZone, clockIn, dateTimeIn, zoneLabel } = await import("../src/lib/zone.ts");

test("a Boise order's time is on Boise's clock and says MST/MDT, whatever the browser's zone", () => {
  assert.equal(clockIn("2026-11-21T18:34:00Z", "America/Boise"), "11:34 am MST");
  assert.equal(clockIn("2026-07-01T18:34:00Z", "America/Boise"), "12:34 pm MDT");
  assert.equal(dateTimeIn("2026-11-21T06:34:00Z", "America/Boise"), "20 Nov, 11:34 pm MST");
});

test("India's zone is IST; a zone with no abbreviation shows its city", () => {
  assert.equal(zoneLabel("Asia/Kolkata", new Date("2026-11-21T00:00:00Z")), "IST");
  assert.equal(clockIn("2026-11-21T06:04:00Z", "Asia/Kolkata"), "11:34 am IST");
  assert.equal(zoneLabel("America/Sao_Paulo", new Date("2026-11-21T00:00:00Z")), "(Sao Paulo)");
});

test("no time, or no zone", () => {
  assert.equal(clockIn(null, "America/Boise"), "–");
  assert.equal(clockIn("2026-11-21T06:04:00Z"), "11:34 am"); // the browser's clock (TZ above), unlabelled
  assert.equal(clockIn("2026-11-21T06:04:00Z", "Not/AZone"), "11:34 am");
});

test("a city's zone: its own, else its state's, else its country's", () => {
  const markets = [{ code: "US", timezone: "America/New_York", regions: [
    { timezone: "America/Boise", cities: [{ code: "US-ID-BOI", timezone: "America/Boise" }, { code: "US-ID-NMP", timezone: null }] },
    { timezone: null, cities: [{ code: "US-NY-NYC", timezone: null }] },
  ] }];
  assert.equal(cityZone(markets, "US-ID-BOI"), "America/Boise");
  assert.equal(cityZone(markets, "US-ID-NMP"), "America/Boise");
  assert.equal(cityZone(markets, "US-NY-NYC"), "America/New_York");
  assert.equal(cityZone(markets, "XX"), null);
  assert.equal(cityZone(undefined, "US-ID-BOI"), null);
});
