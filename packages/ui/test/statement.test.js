// node --test: R24, what a kitchen statement below zero says (shared by the Kitchen app and admin).
const test = require("node:test");
const assert = require("node:assert/strict");
const { belowZeroLines } = require("../statement");

const total = (lines) => lines.reduce((s, l) => s + (l.amount ?? 0), 0);

test("this week below zero, nothing carried in: the week line and carried to next week", () => {
  const lines = belowZeroLines(-5000, 0);
  assert.deepEqual(lines, [{ kind: "week", amount: 5000 }, { kind: "carried" }]);
  assert.equal(total(lines), 5000);
  assert.deepEqual(belowZeroLines(-5000, undefined), lines);
});

test("this week at or above zero, the balance still below zero: only the earlier-weeks line, net of the week", () => {
  // carried in -80.00, this week +30.00: still -50.00
  assert.deepEqual(belowZeroLines(-5000, -8000), [{ kind: "earlier", amount: 5000 }]);
  // a week of exactly zero
  assert.deepEqual(belowZeroLines(-8000, -8000), [{ kind: "earlier", amount: 8000 }]);
});

test("this week below zero and a balance carried in: both lines, adding up to the total", () => {
  // carried in -50.00, this week -30.00: -80.00
  const lines = belowZeroLines(-8000, -5000);
  assert.deepEqual(lines, [{ kind: "week", amount: 3000 }, { kind: "earlier", amount: 5000 }]);
  assert.equal(total(lines), 8000);
});

test("at or above zero with a carry: nothing below zero to say", () => {
  assert.deepEqual(belowZeroLines(2000, -7000), []);
  assert.deepEqual(belowZeroLines(0, -7000), []);
  assert.deepEqual(belowZeroLines(48600, 0), []);
});
