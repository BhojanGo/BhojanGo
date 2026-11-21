// node --test: R27, the tablet must never miss an order silently (pure logic in lib/liveness.ts).
import assert from "node:assert/strict";
import test from "node:test";

import {
  acceptLeft, clockSkew, isOffline, mayStart, mmss, OFFLINE_AFTER_MS, pollDue, pollEvery, POLL_WITH_SOCKET_MS, POLL_WITHOUT_SOCKET_MS,
  socketAlive, STUCK_AFTER_MS,
} from "../lib/liveness.ts";

const T0 = 1_800_000_000_000;

test("connected while the socket or a poll worked within 15 s; offline after that", () => {
  const fresh = { since: T0, lastPoll: null, lastSocket: null };
  assert.equal(isOffline(fresh, T0 + OFFLINE_AFTER_MS), false, "a fresh start gets 15 s");
  assert.equal(isOffline(fresh, T0 + OFFLINE_AFTER_MS + 1), true);
  const polled = { since: T0, lastPoll: T0 + 60_000, lastSocket: null };
  assert.equal(isOffline(polled, T0 + 70_000), false);
  assert.equal(isOffline(polled, T0 + 76_000), true, "no socket and no good poll for 16 s");
  const socket = { since: T0, lastPoll: T0, lastSocket: T0 + 100_000 };
  assert.equal(isOffline(socket, T0 + 110_000), false, "the socket alone is enough");
  assert.equal(isOffline(socket, T0 + 116_000), true);
});

test("the R26 stall: polls that never come back turn into the banner, not silence", () => {
  // The last good poll at 75 min, then every refresh hangs: the banner shows 15 s later.
  const at75 = T0 + 75 * 60_000;
  const l = { since: T0, lastPoll: at75, lastSocket: null };
  assert.equal(isOffline(l, at75 + 10_000), false);
  assert.equal(isOffline(l, at75 + 16_000), true);
});

test("polls slow down while the socket is alive and speed up when it goes quiet", () => {
  assert.equal(pollEvery({ since: T0, lastPoll: null, lastSocket: T0 }, T0 + 5_000), POLL_WITH_SOCKET_MS);
  assert.equal(pollEvery({ since: T0, lastPoll: null, lastSocket: T0 }, T0 + 20_000), POLL_WITHOUT_SOCKET_MS);
  assert.equal(pollEvery({ since: T0, lastPoll: null, lastSocket: null }, T0), POLL_WITHOUT_SOCKET_MS);
  assert.equal(socketAlive({ since: T0, lastPoll: null, lastSocket: T0 }, T0 + OFFLINE_AFTER_MS), true);
  assert.ok(POLL_WITH_SOCKET_MS >= 10_000 && POLL_WITH_SOCKET_MS <= 15_000);
  assert.ok(pollDue(null, T0, 4000) && !pollDue(T0, T0 + 3999, 4000) && pollDue(T0, T0 + 4000, 4000));
});

test("one refresh at a time, unless the running one is stuck", () => {
  assert.equal(mayStart(null, T0), true);
  assert.equal(mayStart(T0, T0 + 10_000), false, "no second refresh piled behind a slow one");
  assert.equal(mayStart(T0, T0 + STUCK_AFTER_MS + 1), true, "a lost refresh never blocks the board for good");
});

test("server time from the Date header corrects the tablet's clock", () => {
  const server = Date.parse("Sat, 21 Nov 2026 18:00:00 GMT");
  // The tablet's clock is 2 minutes fast; the request took 200 ms.
  const sent = server + 120_000;
  const skew = clockSkew("Sat, 21 Nov 2026 18:00:00 GMT", sent, sent + 200);
  assert.ok(Math.abs(skew - -120_000) <= 600, `skew ${skew}`);
  assert.equal(clockSkew(null, T0, T0), 0);
  assert.equal(clockSkew("not a date", T0, T0), 0);
});

test("the accept timer counts to the server's deadline and never shows 0:00 for an order that can be accepted", () => {
  const placed = Date.parse("2026-11-21T18:00:00Z");
  const due = new Date(placed + 180_000).toISOString(); // accept_due_at: placed + accept_timeout (180 s)
  assert.equal(acceptLeft(due, placed, 0), 180);
  assert.equal(mmss(acceptLeft(due, placed, 0)!), "3:00");
  // R26: a tablet 3 minutes fast showed 0:00 at once; on server time it has the full 3 minutes.
  assert.equal(acceptLeft(due, placed + 180_000, -180_000), 180);
  // 400 ms left is still "0:01", never "0:00".
  assert.equal(acceptLeft(due, placed + 179_600, 0), 1);
  // Past the deadline (until the sweep cancels it, within 10 s) it is 0: the card says "Accept now".
  assert.equal(acceptLeft(due, placed + 185_000, 0), 0);
  assert.equal(acceptLeft(null, placed, 0), null);
});
