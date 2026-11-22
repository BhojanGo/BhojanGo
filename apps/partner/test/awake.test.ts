// node --test: R28, the kitchen tablet's screen never sleeps while signed in (lib/awake.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { holdAwake, wantAwake } from "../lib/awakeLogic.ts";

test("wantAwake: only signed in and in the foreground", () => {
  assert.equal(wantAwake(true, "active"), true);
  assert.equal(wantAwake(true, "background"), false);
  assert.equal(wantAwake(false, "active"), false);
});

test("holdAwake: a failed activate is retried, never thrown", async () => {
  let calls = 0;
  const ok = await holdAwake(async () => {
    calls += 1;
    if (calls < 3) throw new Error("The current activity is no longer available");
  }, () => true, 5, 0, async () => undefined);
  assert.equal(ok, true);
  assert.equal(calls, 3);
});

test("holdAwake: gives up after its tries, or when no longer wanted", async () => {
  let calls = 0;
  const fail = async () => { calls += 1; throw new Error("no activity"); };
  assert.equal(await holdAwake(fail, () => true, 3, 0, async () => undefined), false);
  assert.equal(calls, 3);
  calls = 0;
  assert.equal(await holdAwake(fail, () => calls < 1, 5, 0, async () => undefined), false);
  assert.equal(calls, 1);
});
