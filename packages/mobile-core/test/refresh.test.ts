// node --test: R27, the kitchen tablet's silent stall. A session refresh that hangs must fail on
// time, must not keep later requests waiting, and concurrent callers still share one refresh.
import assert from "node:assert/strict";
import test from "node:test";

import { RefreshTimeoutError, singleFlight } from "../src/refresh.ts";

const hang = () => new Promise<string | null>(() => undefined);

test("a refresh that hangs fails with RefreshTimeoutError after the timeout, and its request is aborted", async () => {
  let signal: AbortSignal | null = null;
  const refresh = singleFlight((s) => {
    signal = s;
    return hang();
  }, 30);
  const started = Date.now();
  await assert.rejects(refresh(), RefreshTimeoutError);
  assert.ok(Date.now() - started < 1000, "gave up on time");
  assert.equal((signal as AbortSignal | null)?.aborted, true);
});

test("a hung refresh no longer blocks later requests: the next call starts a fresh one", async () => {
  let calls = 0;
  let up = false;
  const refresh = singleFlight(async () => {
    calls += 1;
    if (!up) return hang();
    return "new-access-token";
  }, 30);
  // R26: every board request after the hung refresh awaited it forever.
  const waiting = [refresh(), refresh(), refresh()];
  for (const w of waiting) await assert.rejects(w, RefreshTimeoutError);
  assert.equal(calls, 1, "the hung refresh was shared, not repeated");
  up = true;
  assert.equal(await refresh(), "new-access-token");
  assert.equal(calls, 2);
});

test("concurrent callers share one refresh (a refresh token works once)", async () => {
  let calls = 0;
  const refresh = singleFlight(async () => {
    calls += 1;
    await new Promise((r) => setTimeout(r, 10));
    return "t";
  }, 1000);
  assert.deepEqual(await Promise.all([refresh(), refresh(), refresh()]), ["t", "t", "t"]);
  assert.equal(calls, 1);
  assert.equal(await refresh(), "t");
  assert.equal(calls, 2, "a settled refresh is not reused");
});

test("a refresh that throws at once is cleared too", async () => {
  let calls = 0;
  const refresh = singleFlight(() => {
    calls += 1;
    if (calls === 1) throw new Error("boom");
    return Promise.resolve("ok");
  }, 1000);
  await assert.rejects(refresh(), /boom/);
  assert.equal(await refresh(), "ok");
});

test("null (the session is over) passes through: that is the caller's sign-out, not a timeout", async () => {
  const refresh = singleFlight(async () => null, 1000);
  assert.equal(await refresh(), null);
});
