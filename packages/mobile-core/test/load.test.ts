// node --test: when the API can't be reached (R9). A GET that hangs fails on time,
// the screen's first load turns into the error state, and Retry loads again and
// recovers (pure logic, no React Native).
import assert from "node:assert/strict";
import test from "node:test";

import { createFirstLoad, loadFailure, RequestTimeoutError, timeoutFetch, type LoadState } from "../src/load.ts";

const hang = () => new Promise<Response>(() => undefined);

test("a GET that hangs fails with RequestTimeoutError after the timeout", async () => {
  const fetch = timeoutFetch(30, () => hang);
  const started = Date.now();
  await assert.rejects(fetch(new Request("http://10.0.2.2:9/api/v1/markets/directory")), RequestTimeoutError);
  assert.ok(Date.now() - started < 1000, "gave up on time");
});

test("the timeout aborts the request's signal", async () => {
  let seen: AbortSignal | null = null;
  const fetch = timeoutFetch(20, () => (req: Request) => {
    seen = req.signal;
    return hang();
  });
  await assert.rejects(fetch(new Request("http://example.test/x")));
  assert.equal((seen as AbortSignal | null)?.aborted, true);
});

test("an answer in time passes through; other methods are never given up", async () => {
  const ok = timeoutFetch(50, () => async () => new Response("{}", { status: 200 }));
  assert.equal((await ok(new Request("http://example.test/x"))).status, 200);
  let posted = false;
  const slowPost = timeoutFetch(10, () => async (req: Request) => {
    await new Promise((r) => setTimeout(r, 40));
    posted = req.method === "POST";
    return new Response(null, { status: 201 });
  });
  assert.equal((await slowPost(new Request("http://example.test/orders", { method: "POST", body: "{}" }))).status, 201);
  assert.equal(posted, true);
});

test("the reason: no connection, too slow, our servers, or the API's refusal", () => {
  assert.equal(loadFailure(new TypeError("Network request failed")), "offline");
  assert.equal(loadFailure(new RequestTimeoutError(8000)), "timeout");
  assert.equal(loadFailure({ status: 503, message: "down" }), "server");
  assert.equal(loadFailure({ status: 404, message: "Not found" }), "refused");
});

test("timeout -> error state; Retry re-fetches and recovers", async () => {
  let apiUp = false;
  let calls = 0;
  const get = timeoutFetch(20, () => (apiUp ? async () => new Response(JSON.stringify({ countries: ["IN"] })) : hang));
  const states: LoadState<{ countries: string[] }>[] = [];
  const load = createFirstLoad(async () => {
    calls += 1;
    return (await (await get(new Request("http://10.0.2.2:9/api/v1/markets/directory"))).json()) as { countries: string[] };
  }, (s) => states.push(s));

  await load.run();
  assert.equal(load.state.status, "error");
  assert.equal(loadFailure(load.state.error), "timeout");
  assert.deepEqual(states.map((s) => s.status), ["loading", "error"]);

  // Retry while the API is still down: the error state again.
  await load.run();
  assert.equal(load.state.status, "error");

  // The API is back: Retry loads.
  apiUp = true;
  await load.run();
  assert.equal(load.state.status, "ready");
  assert.deepEqual(load.state.data, { countries: ["IN"] });
  assert.equal(calls, 3);
});

test("an older, slower load never overwrites a newer one", async () => {
  let n = 0;
  const load = createFirstLoad(async () => {
    const mine = ++n;
    await new Promise((r) => setTimeout(r, mine === 1 ? 40 : 5));
    if (mine === 1) throw new TypeError("Network request failed");
    return "fresh";
  }, () => undefined);
  const first = load.run();
  await load.run();
  await first;
  assert.equal(load.state.status, "ready");
  assert.equal(load.state.data, "fresh");
});
