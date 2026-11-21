// node --test: R27, the kitchen tablet's silent stall. On a 401 every request waits for one
// shared token refresh; a refresh that never settles must fail those requests on time and
// must not hold the requests that come after it.
import assert from "node:assert/strict";
import test from "node:test";

import { createApi, RefreshWaitError } from "../src/index.ts";

const BASE = "http://core.test";

/** A server whose token is good once `good` is the bearer; everything else is a 401. */
function server(state: { good: string }) {
  return async (req: Request) => {
    if (req.headers.get("Authorization") === `Bearer ${state.good}`) {
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
    }
    return new Response(JSON.stringify({ detail: "expired" }), { status: 401, headers: { "content-type": "application/json" } });
  };
}

test("a hung refresh fails the waiting requests on time, and the next request refreshes afresh", async () => {
  const state = { good: "fresh" };
  let token = "expired";
  let refreshes = 0;
  let refreshUp = false;
  let signedOut = false;
  const api = createApi({
    coreUrl: BASE, realtimeUrl: BASE, workerUrl: BASE,
    getAccessToken: () => token,
    refreshAccessToken: () => {
      refreshes += 1;
      if (!refreshUp) return new Promise<string | null>(() => undefined); // R26: hangs forever
      token = "fresh";
      return Promise.resolve("fresh");
    },
    refreshWaitMs: 40,
    onSignedOut: () => { signedOut = true; },
    fetch: server(state),
  });
  const get = () => api.core.GET("/api/v1/users/me" as never);

  const started = Date.now();
  const waiting = [get(), get(), get()];
  for (const w of waiting) await assert.rejects(w, RefreshWaitError);
  assert.ok(Date.now() - started < 1000, "the requests failed on time");
  assert.equal(refreshes, 1, "one refresh shared by the three requests");
  assert.equal(signedOut, false, "a refresh that timed out is not a sign-out");

  refreshUp = true;
  const r = await get();
  assert.equal(r.response.status, 200, "the next request refreshed and went through");
  assert.equal(refreshes, 2);
});

test("a refused refresh (null) signs out", async () => {
  let signedOut = false;
  const api = createApi({
    coreUrl: BASE, realtimeUrl: BASE, workerUrl: BASE,
    getAccessToken: () => "expired",
    refreshAccessToken: async () => null,
    onSignedOut: () => { signedOut = true; },
    fetch: server({ good: "never" }),
  });
  const r = await api.core.GET("/api/v1/users/me" as never);
  assert.equal(r.response.status, 401);
  assert.equal(signedOut, true);
});
