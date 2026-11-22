// node --test: R28. Every request carries an X-Request-ID, and a failed one is reported with it
// (onFailure), so the app's log line can be matched to the API's log, or shown never to have arrived.
import assert from "node:assert/strict";
import test from "node:test";

import { type ApiFailure, createApi } from "../src/index.ts";

const BASE = "http://core.test";
const json = (status: number) => new Response("{}", { status, headers: { "content-type": "application/json" } });

function apiWith(fetch: (r: Request) => Promise<Response>, failures: ApiFailure[], token = "t") {
  let current = token;
  return createApi({
    coreUrl: BASE, realtimeUrl: BASE, workerUrl: BASE,
    getAccessToken: () => current,
    refreshAccessToken: async () => { current = "fresh"; return "fresh"; },
    fetch, onFailure: (f) => failures.push(f),
  });
}

test("each request gets its own X-Request-ID; a good answer reports nothing", async () => {
  const ids: string[] = [];
  const failures: ApiFailure[] = [];
  const api = apiWith(async (r) => { ids.push(r.headers.get("X-Request-ID") ?? ""); return json(200); }, failures);
  await api.core.GET("/a" as never);
  await api.core.GET("/a" as never);
  assert.equal(ids.length, 2);
  assert.ok(ids[0].length >= 16 && ids[0] !== ids[1]);
  assert.deepEqual(failures, []);
});

test("no answer at all: reported with the id, the method, the path and the error", async () => {
  const failures: ApiFailure[] = [];
  let sent = "";
  const api = apiWith(async (r) => { sent = r.headers.get("X-Request-ID") ?? ""; throw new TypeError("Network request failed"); }, failures);
  await assert.rejects(api.core.POST("/api/v1/pricing/quote" as never, { body: {} } as never));
  // R28: the quote is safe to send again: one retry ("<id>-n"), which failed too
  assert.equal(failures.length, 2);
  assert.equal(failures[1].id, sent);
  assert.equal(failures[0].id, sent.replace(/-n$/, ""));
  assert.equal(failures[0].method, "POST");
  assert.equal(failures[0].path, "/api/v1/pricing/quote");
  assert.equal(failures[0].error, "TypeError: Network request failed");
  assert.equal(failures[0].status, undefined);
});

test("an error status is reported with it", async () => {
  const failures: ApiFailure[] = [];
  const api = apiWith(async () => json(503), failures);
  await api.core.GET("/api/v1/payments/provider" as never);
  assert.equal(failures[0].status, 503);
});

test("after a 401 the retry is a request of its own (id + '-r'); only its failure is the answer", async () => {
  const ids: string[] = [];
  const failures: ApiFailure[] = [];
  const api = apiWith(async (r) => {
    ids.push(r.headers.get("X-Request-ID") ?? "");
    if (r.headers.get("Authorization") === "Bearer fresh") throw new TypeError("Network request failed");
    return json(401);
  }, failures, "expired");
  await assert.rejects(api.core.POST("/q" as never, { body: {} } as never));
  assert.equal(ids[1], `${ids[0]}-r`);
  assert.equal(failures.at(-1)?.id, `${ids[0]}-r`);
  assert.equal(failures.at(-1)?.error, "TypeError: Network request failed");
});

// R28: a dropped connection on a request that is safe to repeat goes once more; other changes never.
test("no answer: a safe request is sent once more and its answer used; an unsafe change is not", async () => {
  const failures: ApiFailure[] = [];
  let calls = 0;
  const bodies: string[] = [];
  const api = apiWith(async (r) => {
    calls += 1;
    bodies.push(await r.clone().text());
    if (calls === 1) throw new TypeError("Network request failed");
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
  }, failures);
  const r = await api.core.POST("/api/v1/pricing/quote" as never, { body: { restaurant_id: "k1" } } as never);
  assert.equal(r.response.status, 200);
  assert.deepEqual(r.data, { ok: true });
  assert.equal(calls, 2);
  assert.equal(bodies[1], bodies[0], "the retry carries the same body");

  calls = 0;
  const unsafe = apiWith(async () => { calls += 1; throw new TypeError("Network request failed"); }, []);
  await assert.rejects(unsafe.core.POST("/api/v1/orders/x/cancel" as never, { body: {} } as never));
  assert.equal(calls, 1, "a change without an idempotency key is never sent twice");
});
