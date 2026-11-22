// node --test: R27 QA journey. A POST sent with an expired access token got a 401; the retry after the
// refresh rebuilt the request from the one already sent, whose body had been read, so it threw
// ("already used") and the apps said "Can't reach BhojanGo": the bag couldn't price or pay after
// 15 quiet minutes. The retry must carry the same body.
import assert from "node:assert/strict";
import test from "node:test";

import { createApi } from "../src/index.ts";

const BASE = "http://core.test";

test("a POST that got a 401 is sent again after the refresh, with its body", async () => {
  let token = "expired";
  const seen: { auth: string | null; body: string }[] = [];
  const api = createApi({
    coreUrl: BASE, realtimeUrl: BASE, workerUrl: BASE,
    getAccessToken: () => token,
    refreshAccessToken: async () => { token = "fresh"; return "fresh"; },
    // Like the apps' timeoutFetch for the quote: the request is copied (and its body read) before it goes.
    fetch: async (req: Request) => {
      const sent = new Request(req, { signal: new AbortController().signal });
      const body = await sent.text();
      seen.push({ auth: sent.headers.get("Authorization"), body });
      const ok = sent.headers.get("Authorization") === "Bearer fresh";
      return new Response(JSON.stringify(ok ? { got: JSON.parse(body) } : { detail: "expired" }),
        { status: ok ? 200 : 401, headers: { "content-type": "application/json" } });
    },
  });
  const r = await api.core.POST("/api/v1/pricing/quote" as never, { body: { restaurant_id: "k1", items: [1, 2] } } as never);
  assert.equal(r.response.status, 200, "the retry went through");
  assert.deepEqual((r.data as { got: unknown }).got, { restaurant_id: "k1", items: [1, 2] }, "with the same body");
  assert.equal(seen.length, 2);
  assert.equal(seen[1].auth, "Bearer fresh");
  assert.equal(seen[1].body, seen[0].body);
});
