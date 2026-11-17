// node --test: the /deliver page's helpers (R8 F8). The numbers themselves come
// from GET /delivery/terms; these format them and draw the QR code locally.
import assert from "node:assert/strict";
import test from "node:test";

import { ageOn, capitalize, defaultCity, distance, firstName, orList, percent, qrPath, unitName, weekday } from "../src/lib/deliver.ts";

test("the QR code is drawn locally: a square with a quiet zone, dark modules as one path", () => {
  const a = qrPath("https://example.test/deliver/app?country=IN");
  assert.ok(a.size >= 21 + 8 && a.size <= 177 + 8);
  assert.match(a.d, /^(M\d+ \d+h1v1h-1z)+$/);
  // the three finder patterns: the top-left module inside the quiet zone is dark
  assert.ok(a.d.startsWith("M4 4h1v1h-1z"));
  assert.notEqual(qrPath("https://example.test/a").d, qrPath("https://example.test/b").d);
});

test("distances and units follow the country's unit and locale", () => {
  assert.equal(distance("3", "km", "en-IN"), "3 km");
  assert.equal(distance(2, "mi", "en-US"), "2 mi");
  assert.equal(distance("2.5", "mi", "en-US"), "2.5 mi");
  assert.equal(unitName("km", "en-IN"), "km");
  assert.equal(unitName("mi", "en-US"), "mi");
  assert.equal(distance(4, "leagues", "en-US"), "4 leagues");
});

test("payout day, vehicle list and tips share read naturally", () => {
  assert.equal(weekday("mon", "en"), "Monday");
  assert.equal(weekday("fri", "es"), "viernes");
  assert.equal(orList(["motorcycle", "scooter", "electric scooter"], "en"), "motorcycle, scooter, or electric scooter");
  assert.equal(capitalize("car, motorcycle, or scooter"), "Car, motorcycle, or scooter");
  assert.equal(percent(100, "en-US"), "100%");
});

test("the visitor's city is the default when it is live, else the first live city", () => {
  assert.equal(defaultCity(["IN-TG-HYD"], [null, "IN-TG-HYD"]), "IN-TG-HYD");
  assert.equal(defaultCity(["A-B-CD", "A-B-EF"], ["A-B-EF"]), "A-B-EF");
  assert.equal(defaultCity(["A-B-CD", "A-B-EF"], ["Z-Z-ZZ", undefined]), "A-B-CD");
  assert.equal(defaultCity([], ["A-B-CD"]), null);
  assert.equal(firstName("  Kiran  Rao "), "Kiran");
});

test("age on the country's date, as the API counts it (R9)", () => {
  assert.equal(ageOn("2008-11-16", "2026-11-16"), 18); // the birthday itself
  assert.equal(ageOn("2008-11-17", "2026-11-16"), 17); // one day short
  assert.equal(ageOn("2008-02-29", "2026-02-28"), 17); // leap-day births count from 1 March
  assert.equal(ageOn("2008-02-29", "2026-03-01"), 18);
  assert.equal(ageOn("2027-01-01", "2026-11-16"), null); // the future
  assert.equal(ageOn("1900-01-01", "2026-11-16"), null); // a typo
  assert.equal(ageOn("", "2026-11-16"), null);
});
