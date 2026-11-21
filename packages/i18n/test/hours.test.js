// node --test: "Closed · opens 6:30 am" in the country's format, the weekday in the visitor's language (R27).
process.env.TZ = "Asia/Kolkata"; // a device far from the kitchen: never its clock
const test = require("node:test");
const assert = require("node:assert/strict");
const { opensWhen, opensLabel, wallClock, createTranslator } = require("..");
const en = require("../messages/en.json");
const te = require("../messages/te.json");

const BOISE = { timeZone: "America/Boise", formatLocale: "en-US", language: "en" };
const now = new Date("2026-11-21T13:00:00Z"); // Sat 6:00 am in Boise

test("later today: the time alone, on the kitchen's clock, 12-hour in the US", () => {
  assert.deepEqual(opensWhen("2026-11-21T13:30:00Z", { ...BOISE, now }), { time: "6:30 am", day: null });
  assert.deepEqual(opensWhen("2026-11-21T08:00:00-07:00", { ...BOISE, now }), { time: "8:00 am", day: null });
});

test("another day: with the weekday", () => {
  const t = createTranslator("en", en, en);
  assert.equal(opensLabel(t, "2026-11-22T15:00:00Z", { ...BOISE, now }), "Closed · opens Sun 8:00 am");
  assert.equal(opensLabel(t, "2026-11-21T13:30:00Z", { ...BOISE, now }), "Closed · opens 6:30 am");
  assert.equal(opensLabel(t, "2026-11-22T15:00:00Z", { ...BOISE, now }, { today: "kitchen.opens_at", day: "kitchen.opens_at_day" }),
    "Opens Sun 8:00 am");
  assert.equal(opensLabel(t, null, BOISE), null);
});

test("Telugu: the status and weekday in Telugu, the time in India's format", () => {
  const t = createTranslator("te", te, en);
  const hyd = { timeZone: "Asia/Kolkata", formatLocale: "en-IN", language: "te", now: new Date("2026-11-20T18:00:00Z") };
  const label = opensLabel(t, "2026-11-21T13:30:00Z", hyd); // Sat 7:00 pm IST, tomorrow from Fri 11:30 pm
  const sat = new Intl.DateTimeFormat("te", { weekday: "short", timeZone: "Asia/Kolkata" }).format(new Date("2026-11-21T13:30:00Z"));
  assert.equal(label, `మూసి ఉంది · ${sat} 7:00 pmకి తెరుస్తారు`);
  assert.doesNotMatch(label, /Closed|opens|Sat/);
});

test("wall-clock times from the API", () => {
  assert.equal(wallClock("08:00", "en-US"), "8:00 am");
  assert.equal(wallClock("23:00", "en-IN"), "11:00 pm");
  assert.equal(wallClock(null, "en-US"), null);
  assert.equal(opensWhen(null, BOISE), null);
  assert.equal(opensWhen("not a time", BOISE), null);
});
