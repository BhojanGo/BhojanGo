// node --test: the lines on the tracking map (R8). The fixtures replay what the
// demo simulator sends in Boise: the partner accepts 1.4 km north-east of the
// kitchen, rides to it, picks up, and heads south-west towards home.
import assert from "node:assert/strict";
import test from "node:test";

import { AT_KITCHEN_M, metresBetween, routeLines, sinceKitchen, type Pt } from "../src/lib/route.ts";

const KITCHEN: Pt = [43.6150, -116.2023];
const HOME: Pt = [43.6060, -116.2150];
// The ride to the kitchen: from where they accepted (north-east, in the foothills).
const TO_KITCHEN: Pt[] = [[43.6250, -116.1900], [43.6230, -116.1930], [43.6200, -116.1960], [43.6170, -116.2000], [43.61505, -116.20225]];
// After pickup: towards home.
const TO_HOME: Pt[] = [[43.6140, -116.2040], [43.6125, -116.2060], [43.6110, -116.2080]];
const RIDER: Pt = [43.6100, -116.2095];

const north = (p: Pt) => p[0];

test("before pickup: the ride so far ends at the partner, dashed on to the kitchen", () => {
  const trail = TO_KITCHEN.slice(0, 3);
  const at: Pt = [43.6190, -116.1975];
  const { done, ahead } = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: at, trail, leg: "kitchen" });
  assert.deepEqual(done, [...trail, at]);
  assert.deepEqual(ahead, [at, KITCHEN]);
});

test("after pickup: the solid line starts at the kitchen and never goes back up the ride there", () => {
  const trail = [...TO_KITCHEN, ...TO_HOME];
  const { done, ahead } = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: RIDER, trail, leg: "home" });
  assert.deepEqual(done, [KITCHEN, ...TO_HOME, RIDER]);
  assert.deepEqual(ahead, [RIDER, HOME]);
  // It leaves the kitchen towards home (south here), not north into the foothills.
  assert.ok(north(done[1]!) < north(KITCHEN));
  // Every point is between the kitchen and home: nothing ends in empty map.
  for (const p of done) assert.ok(metresBetween(p, HOME) <= metresBetween(KITCHEN, HOME) + AT_KITCHEN_M);
});

test("after pickup with no fix since: the way home starts at the kitchen", () => {
  const { done, ahead } = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: TO_KITCHEN[4]!, trail: TO_KITCHEN, leg: "home" });
  // The partner is still at the kitchen: the solid line is the few metres from the kitchen pin to them.
  assert.deepEqual(done, [KITCHEN, TO_KITCHEN[4]!]);
  assert.deepEqual(ahead, [TO_KITCHEN[4]!, HOME]);
  const none = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: null, trail: [], leg: "home" });
  assert.deepEqual(none, { done: [], ahead: [KITCHEN, HOME] });
});

test("the oldest fixes trimmed: the line starts at the kitchen and joins the nearest fix", () => {
  const { done } = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: RIDER, trail: TO_HOME, leg: "home" });
  assert.deepEqual(done, [KITCHEN, ...TO_HOME, RIDER]);
});

test("a partner who passes the kitchen twice: only the fixes after the last time there", () => {
  const trail: Pt[] = [...TO_KITCHEN, [43.6160, -116.2010], [43.61502, -116.20232], ...TO_HOME];
  assert.deepEqual(sinceKitchen(trail, KITCHEN), TO_HOME);
});

test("delivered: the ride from the kitchen, nothing ahead, no partner marker needed", () => {
  const trail = [...TO_KITCHEN, ...TO_HOME, HOME];
  const { done, ahead } = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: null, trail, leg: null });
  assert.deepEqual(done, [KITCHEN, ...TO_HOME, HOME]);
  assert.deepEqual(ahead, []);
});

test("repeated and broken fixes are skipped; [lat, lng] is never read as [lng, lat]", () => {
  const trail: Pt[] = [TO_HOME[0]!, TO_HOME[0]!, [Number.NaN, 1], [200, 200], TO_HOME[1]!];
  const { done } = routeLines({ pickup: KITCHEN, dropoff: HOME, rider: TO_HOME[1]!, trail, leg: "home" });
  assert.deepEqual(done, [KITCHEN, TO_HOME[0]!, TO_HOME[1]!]);
  for (const p of done) assert.ok(Math.abs(p[0]) <= 90 && p[0] > 40, "latitude first");
});
