// node --test: R28, the bag after 15 idle minutes. On a phone the fetch behind the 401 retry returns a
// response that isn't an instance of the global Response; openapi-fetch then threw "onResponse: must return
// new Response()" after the API had answered 200, and the bag said "Can't reach BhojanGo".
import assert from "node:assert/strict";
import test from "node:test";

import { asResponse, createApi } from "../src/index.ts";

const BASE = "http://core.test";

/** A response from another fetch implementation: same shape, not `instanceof Response`. */
class ForeignResponse {
  status: number;
  statusText = "";
  ok: boolean;
  headers: Headers;
  bodyUsed = false;
  private text_: string;
  constructor(body: string, status: number) {
    this.status = status;
    this.ok = status >= 200 && status < 300;
    this.text_ = body;
    this.headers = new Headers({ "content-type": "application/json" });
  }
  async text() { return this.text_; }
  async json() { return JSON.parse(this.text_); }
  async arrayBuffer() { return new TextEncoder().encode(this.text_).buffer; }
  clone() { return new ForeignResponse(this.text_, this.status); }
}

test("the retry after a refresh works when the fetch's responses are another class", async () => {
  let token = "expired";
  const api = createApi({
    coreUrl: BASE, realtimeUrl: BASE, workerUrl: BASE,
    getAccessToken: () => token,
    refreshAccessToken: async () => { token = "fresh"; return "fresh"; },
    fetch: async (req: Request) => {
      const ok = req.headers.get("Authorization") === "Bearer fresh";
      const r = new ForeignResponse(JSON.stringify(ok ? { total: "448.91" } : { detail: "expired" }), ok ? 200 : 401);
      return r as unknown as Response;
    },
  });
  const r = await api.core.POST("/api/v1/pricing/quote" as never, { body: { restaurant_id: "k1" } } as never);
  assert.equal(r.response.status, 200);
  assert.deepEqual(r.data, { total: "448.91" });
});

test("asResponse keeps a real Response and copies a foreign one (status, headers, body; no body for 204)", async () => {
  const real = new Response("x");
  assert.equal(await asResponse(real), real);
  const copied = await asResponse(new ForeignResponse('{"a":1}', 201) as unknown as Response);
  assert.ok(copied instanceof Response);
  assert.equal(copied.status, 201);
  assert.equal(copied.headers.get("content-type"), "application/json");
  assert.deepEqual(await copied.json(), { a: 1 });
  const none = await asResponse(new ForeignResponse("", 204) as unknown as Response);
  assert.equal(none.status, 204);
});
