// R21: a Boise dinner rush at 3x the launch estimate, on a throwaway stack
// (.github/workflows/load-test.yml; never QA or production). Results: docs/launch/load-test.md.
//
// Who is on the stack at once (3x launch; docs/launch/load-test.md says where each number comes from):
//   browsing     2,000 people on the customer app (home for their address, then two menus,
//                5-15 s reading between screens; anonymous, each at their own address)
//   orders       300 an hour: quote, place, pay (start + confirm), then the tracking screen
//                (WebSocket + the app's 15 s status poll) until it's delivered
//   quotes       20 a minute more (people changing their bag), 25 a minute in all
//   riders       75 online (3x the 25 planned for Boise): GPS every 5 s, offers over /ws/rider
//                plus the app's 5 s poll; they accept, ride, pick up and hand over with the PIN
//   tablets      45 kitchen tablets (3x 15 pilot kitchens) polling the board every 4 s, as the
//                partner app does; the first tablet of each kitchen accepts and cooks
//
// Realtime is counted, not only timed: every published update and every received one is
// logged as an `RT|...` console line (no tokens) and tools/load/rush_report.py matches them.
import { check, sleep } from "k6";
import encoding from "k6/encoding";
import exec from "k6/execution";
import http from "k6/http";
import ws from "k6/ws";
import { Counter, Trend } from "k6/metrics";

const API = __ENV.API || "http://core-api:8001/api/v1";
const RT = __ENV.RT || "http://realtime:8004";
const WS = RT.replace(/^http/, "ws");
const WINDOW = Number(__ENV.WINDOW || "20"); // minutes of orders at the peak rate
const SCALE = Number(__ENV.SCALE || "1"); // 1 = 3x launch
const BROWSERS = Math.max(1, Math.round(2000 * SCALE));
const ORDERS_PER_HOUR = 300 * SCALE;
const EXTRA_QUOTES_PER_MIN = Math.max(1, Math.round(20 * SCALE));
const RIDERS = Math.max(2, Math.round(75 * SCALE));
const TABLETS = Math.max(2, Math.round(45 * SCALE));
const CUSTOMERS = Number(__ENV.CUSTOMERS || "60");
const LEAD_MIN = 2; // riders and tablets settle in before the first order
const DRAIN_MIN = 16; // orders placed at the end of the window still get delivered
const PASSWORD = "BhojanGo123";
const JSON_H = { "Content-Type": "application/json" };

// Per-request trends (ms), named for the report.
const T = {};
["discover", "menu", "quote", "place_order", "pay_initiate", "pay_confirm", "order_status", "board", "today",
  "rider_ping", "rider_me", "offer_accept", "kitchen_status", "rider_status"].forEach((n) => { T[n] = new Trend(`t_${n}`, true); });
const rtLocation = new Trend("rt_location_ms", true); // rider fix stored -> on the tracking socket
const rtStatus = new Trend("rt_status_ms", true); // status event published -> on the tracking socket
const wsConnect = new Trend("ws_connect_ms", true);
const placedToConfirmed = new Trend("placed_visible_ms", true); // confirm returned -> GET says placed
const errors = new Counter("errors"); // unexpected status, by step
const wsErrors = new Counter("ws_errors");
const delivered = new Counter("orders_delivered");
const placed = new Counter("orders_placed");

const minutes = (m) => `${Math.round(m * 60)}s`;

export const options = {
  setupTimeout: "10m",
  teardownTimeout: "2m",
  discardResponseBodies: false,
  scenarios: {
    browse: {
      executor: "ramping-vus", exec: "browse", startVUs: 0,
      stages: [{ duration: "3m", target: BROWSERS }, { duration: minutes(WINDOW + LEAD_MIN - 3), target: BROWSERS },
        { duration: "1m", target: 0 }],
      gracefulRampDown: "30s",
    },
    orders: {
      executor: "constant-arrival-rate", exec: "order", startTime: `${LEAD_MIN}m`, duration: minutes(WINDOW),
      rate: Math.max(1, Math.round(ORDERS_PER_HOUR)), timeUnit: "1h", preAllocatedVUs: 40, maxVUs: 250,
      gracefulStop: `${DRAIN_MIN}m`,
    },
    quotes: {
      executor: "constant-arrival-rate", exec: "quote", startTime: `${LEAD_MIN}m`, duration: minutes(WINDOW),
      rate: EXTRA_QUOTES_PER_MIN, timeUnit: "1m", preAllocatedVUs: 5, maxVUs: 30,
    },
    riders: {
      executor: "per-vu-iterations", exec: "rider", vus: RIDERS, iterations: 1,
      maxDuration: minutes(WINDOW + LEAD_MIN + DRAIN_MIN + 2), gracefulStop: "1m",
    },
    tablets: {
      executor: "per-vu-iterations", exec: "tablet", vus: TABLETS, iterations: 1,
      maxDuration: minutes(WINDOW + LEAD_MIN + DRAIN_MIN + 2), gracefulStop: "1m",
    },
  },
  // The targets (R21): API reads p95 < 500 ms, placing an order p95 < 1.5 s. Lost realtime
  // updates (target 0) are counted by rush_report.py from the RT lines.
  thresholds: {
    t_discover: ["p(95)<500"], t_menu: ["p(95)<500"], t_quote: ["p(95)<500"], t_order_status: ["p(95)<500"],
    t_board: ["p(95)<500"], t_today: ["p(95)<500"], t_rider_me: ["p(95)<500"], t_rider_ping: ["p(95)<500"],
    t_place_order: ["p(95)<1500"], t_pay_initiate: ["p(95)<1500"], t_pay_confirm: ["p(95)<1500"],
    ws_connect_ms: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

// ── helpers ──────────────────────────────────────────────────────────────────
const rand = (a, b) => a + Math.random() * (b - a);
const pick = (xs) => xs[Math.floor(Math.random() * xs.length)];
const now = () => Date.now();
function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}
// ISO time from Python (microseconds, +00:00) -> ms since epoch.
function isoMs(s) {
  if (!s) return NaN;
  return Date.parse(String(s).replace(/(\.\d{3})\d+/, "$1").replace(/\+00:00$/, "Z"));
}
// One console line per realtime event, for rush_report.py. Ids and times only.
function rt(...parts) { console.log(["RT", ...parts].join("|")); }

function timed(name, res, ok) {
  T[name].add(res.timings.duration);
  if (!ok) {
    errors.add(1, { step: name });
    console.warn(`ERR|${name}|${res.status}|${String(res.body || "").slice(0, 160).replace(/\s+/g, " ")}`);
  }
  return ok;
}
const auth = (token) => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" });

let ipSeq = 0;
function login(email) {
  // Each person signs in from their own address (X-Real-IP, as Railway's edge sets it;
  // CLIENT_IP_HEADER in infra/docker/load.compose.yaml), so the per-address sign-in limit
  // sees people, not the load generator.
  ipSeq += 1;
  const ip = `10.${(ipSeq >> 16) & 255}.${(ipSeq >> 8) & 255}.${ipSeq & 255}`;
  const r = http.post(`${API}/auth/login`, JSON.stringify({ email, password: PASSWORD }),
    { headers: { "Content-Type": "application/json", "X-Real-IP": ip }, tags: { name: "login" } });
  if (r.status !== 200) throw new Error(`login ${email}: ${r.status}`);
  const token = r.json("access_token");
  const claims = JSON.parse(encoding.b64decode(token.split(".")[1], "rawurl", "s"));
  return { token, id: claims.sub };
}

// Tests never write to QA or production (the rule in tools/target_guard.py; the workflow
// also runs target_guard.py itself before k6).
const PROTECTED = ["qa", "production", "prod"];
function refuseQaAndProduction() {
  for (const base of [API.replace(/\/api\/v1\/?$/, ""), RT]) {
    const r = http.get(`${base}/health`);
    const env = String((r.status === 200 && r.json("environment")) || "").trim().toLowerCase();
    const host = base.replace(/^https?:\/\//, "").split(/[:/]/)[0];
    const local = host === "localhost" || host === "127.0.0.1" || !host.includes(".");
    if (r.status !== 200 || PROTECTED.includes(env) || (!env && !local) || !local) {
      exec.test.abort(`REFUSED (tools/target_guard.py rule): ${base} reports '${env}' (HTTP ${r.status}); load tests run on a throwaway stack only`);
    }
  }
}

// Boise's delivery zones (tools/seed/data.py, demo_data.py): where the browsing people are.
const ZONES = [[43.580, -116.250, 43.605, -116.215], [43.598, -116.290, 43.620, -116.250], [43.590, -116.215, 43.605, -116.185],
  [43.600, -116.185, 43.625, -116.150], [43.555, -116.215, 43.590, -116.160]];

// ── setup: sign-ins, kitchens, menus, who delivers where ─────────────────────
export function setup() {
  refuseQaAndProduction();
  const partners = ["partner.boi@example.com", "partner.demo.boi@example.com"].map(login);
  const owner = {};
  partners.forEach((p) => {
    const mine = http.get(`${API}/restaurants/mine`, { headers: auth(p.token) }).json();
    mine.forEach((k) => { owner[k.id] = p.token; });
  });
  // Open every Boise kitchen around the clock for the run (hours.py opens the city and the
  // seed partner's kitchens; the demo partner's are opened here). Today and tomorrow, Boise time.
  const days = [0, 1, -1].map((d) => new Date(now() - 7 * 3600e3 + d * 86400e3).toISOString().slice(0, 10));
  const list = http.get(`${API}/restaurants?limit=100`).json("items").filter((k) => k.city === "Boise" && owner[k.id]);
  list.forEach((k) => days.forEach((d) => http.put(`${API}/restaurants/${k.id}/hours/overrides/${d}`,
    JSON.stringify({ closed: false, opens: "00:00", closes: "00:00", note: "load test" }), { headers: auth(owner[k.id]) })));
  const kitchens = {};
  list.forEach((k) => {
    const menu = http.get(`${API}/restaurants/${k.id}/menu`).json();
    const items = [];
    (menu.categories || []).forEach((c) => (c.items || []).forEach((i) => {
      if (i.is_available && !i.sold_out_today && !(i.option_groups || []).some((g) => (g.min_picks || 0) > 0)) {
        items.push([i.id, Number(i.price)]);
      }
    }));
    if (items.length) kitchens[k.id] = { id: k.id, lat: k.lat, lng: k.lng, min: Number(k.minimum_order_amount || 0), items };
  });
  const customers = [];
  for (let i = 1; i <= CUSTOMERS; i++) {
    const c = login(`customer${i}.boi@example.com`);
    const home = (http.get(`${API}/me/addresses`, { headers: auth(c.token) }).json() || [])[0];
    if (!home) continue;
    const near = http.get(`${API}/discover?lat=${home.lat}&lng=${home.lng}`).json("restaurants") || [];
    const ks = near.filter((r) => r.open_now && kitchens[r.id]).map((r) => r.id);
    if (ks.length) customers.push({ token: c.token, id: c.id, address: home.id, street: home.street || "1 Main St",
      zip: home.postal_code || "83702", kitchens: ks });
  }
  const riders = [];
  for (let i = 1; i <= RIDERS; i++) riders.push(login(`rider${i}.boi@example.com`).token);
  const tabletKitchens = Object.keys(kitchens);
  if (!customers.length || !tabletKitchens.length) exec.test.abort("setup: no open Boise kitchens or customers (seed, demo, tools/soak/setup.py, hours.py open)");
  const pins = {};
  customers.forEach((c) => { pins[c.id] = c.token; });
  console.log(`setup: ${tabletKitchens.length} kitchens, ${customers.length} customers, ${riders.length} riders, ${TABLETS} tablets`);
  return { kitchens, customers, riders, owner, tabletKitchens, pins, end: now() + (LEAD_MIN + WINDOW + DRAIN_MIN) * 60e3 };
}

// ── browsing: home for their address, then two menus ─────────────────────────
export function browse(data) {
  const vu = exec.vu.idInTest;
  // A fixed home per person (same seed per VU), so the per-address cache behaves as it would.
  const z = ZONES[vu % ZONES.length];
  const f = ((vu * 7919) % 1000) / 1000;
  const g = ((vu * 104729) % 1000) / 1000;
  const lat = (z[0] + f * (z[2] - z[0])).toFixed(4);
  const lng = (z[1] + g * (z[3] - z[1])).toFixed(4);
  const d = http.get(`${API}/discover?lat=${lat}&lng=${lng}`, { tags: { name: "discover" } });
  if (!timed("discover", d, d.status === 200)) { sleep(rand(5, 15)); return; }
  const ks = (d.json("restaurants") || []).map((r) => r.id);
  sleep(rand(5, 15));
  for (let i = 0; i < 2 && ks.length; i++) {
    const m = http.get(`${API}/restaurants/${pick(ks)}/menu`, { tags: { name: "menu" } });
    timed("menu", m, m.status === 200);
    sleep(rand(5, 15));
  }
}

// ── quotes and orders ────────────────────────────────────────────────────────
function cart(k) {
  const want = Math.max(k.min, 20) + rand(5, 20); // over the kitchen's and the zone's minimum
  const lines = {};
  let total = 0;
  for (let n = 0; total < want && n < 30; n++) {
    const [id, price] = pick(k.items);
    lines[id] = (lines[id] || 0) + 1;
    total += price;
  }
  return Object.keys(lines).map((id) => ({ menu_item_id: id, quantity: lines[id] }));
}

function quoteFor(c, k, items) {
  const r = http.post(`${API}/pricing/quote`, JSON.stringify({ restaurant_id: k.id, items, deliver_to: { address_id: c.address } }),
    { headers: auth(c.token), tags: { name: "quote" } });
  timed("quote", r, r.status === 200);
  return r;
}

export function quote(data) {
  const c = pick(data.customers);
  const k = data.kitchens[pick(c.kitchens)];
  quoteFor(c, k, cart(k));
}

export function order(data) {
  const c = pick(data.customers);
  const k = data.kitchens[pick(c.kitchens)];
  const items = cart(k);
  const q = quoteFor(c, k, items);
  if (q.status !== 200) return;
  const h = auth(c.token);
  const o = http.post(`${API}/orders`, JSON.stringify({ restaurant_id: k.id, items, payment_method: "card", quote_token: q.json("token"),
    delivery_address: { street: c.street, city: "Boise", state: "ID", zip: c.zip, country: "US" } }),
  { headers: Object.assign({ "X-Idempotency-Key": uuid() }, h), tags: { name: "place_order" } });
  if (!timed("place_order", o, o.status === 201)) return;
  const id = o.json("id");
  const p = http.post(`${API}/payments/initiate`, JSON.stringify({ order_id: id, payment_method_type: "card" }), { headers: h, tags: { name: "pay_initiate" } });
  if (!timed("pay_initiate", p, p.status === 201)) return;
  // The app's checkout "pays" (the fake gateway's complete path): the same signed event a
  // real gateway's webhook applies. FAKE_PAYMENT_AUTO_COMPLETE_SECONDS is 0 for this run.
  const cf = http.post(`${API}/payments/fake/${p.json("payment_intent_id")}/complete`, JSON.stringify({ outcome: "succeeded" }),
    { headers: h, tags: { name: "pay_confirm" } });
  if (!timed("pay_confirm", cf, cf.status === 200)) return;
  const confirmed = now();
  let st = "";
  for (let i = 0; i < 30 && st !== "placed"; i++) {
    const g = http.get(`${API}/orders/${id}`, { headers: h, tags: { name: "order_status" } });
    timed("order_status", g, g.status === 200);
    st = g.status === 200 ? g.json("status") : "";
    if (st !== "placed") sleep(1);
  }
  if (st !== "placed") { errors.add(1, { step: "never_placed" }); return; }
  placedToConfirmed.add(now() - confirmed);
  placed.add(1);
  rt("kplaced", k.id, id, confirmed);
  track(data, c, id);
}

// The tracking screen: a WebSocket (reconnecting like the app) and the 15 s status poll,
// until the order is delivered (then 15 s more, for late messages) or 20 minutes.
function track(data, c, id) {
  const hardEnd = now() + 20 * 60e3;
  let doneAt = 0;
  let session = 0;
  while (now() < hardEnd && !(doneAt && now() > doneAt)) {
    session += 1;
    const sess = `${id.slice(0, 8)}-${session}`;
    const start = now();
    let opened = false;
    const res = ws.connect(`${WS}/ws/track/${id}`, { headers: { Authorization: `Bearer ${c.token}` }, tags: { name: "ws_track" } }, (socket) => {
      socket.on("message", (raw) => {
        let m;
        try { m = JSON.parse(raw); } catch (e) { return; }
        const t = now();
        if (m.type === "connected") {
          opened = true;
          wsConnect.add(t - start);
          rt("open", id, sess, t);
        } else if (m.type === "location_update") {
          rtLocation.add(t - isoMs(m.payload.timestamp));
          rt("loc", id, sess, m.payload.timestamp, t);
        } else if (m.type === "status_change") {
          rtStatus.add(t - isoMs(m.timestamp));
          rt("st", id, sess, m.payload.status, t);
          if (m.payload.status === "delivered" && !doneAt) doneAt = t + 15000;
        }
      });
      socket.on("error", () => wsErrors.add(1));
      socket.setInterval(() => {
        const g = http.get(`${API}/orders/${id}`, { headers: auth(c.token), tags: { name: "order_status" } });
        timed("order_status", g, g.status === 200);
        const st = g.status === 200 ? g.json("status") : "";
        if ((st === "delivered" || st === "cancelled") && !doneAt) doneAt = now() + 15000;
        if (doneAt && now() >= doneAt) socket.close();
      }, 15000);
      socket.setInterval(() => { if ((doneAt && now() >= doneAt) || now() >= hardEnd) socket.close(); }, 1000);
    });
    if (opened) rt("close", id, sess, now());
    if (!res || res.status !== 101) { wsErrors.add(1); sleep(3); }
  }
  if (doneAt) delivered.add(1);
}

// ── riders ───────────────────────────────────────────────────────────────────
export function rider(data) {
  const i = exec.scenario.iterationInTest;
  const token = data.riders[i % data.riders.length];
  const h = auth(token);
  const ks = Object.values(data.kitchens);
  const home = ks[i % ks.length];
  let lat = home.lat + rand(-0.01, 0.01);
  let lng = home.lng + rand(-0.01, 0.01);
  const on = http.post(`${RT}/api/v1/riders/me/online`, JSON.stringify({ lat, lng }), { headers: h, tags: { name: "rider_online" } });
  if (on.status !== 200) { errors.add(1, { step: "rider_online" }); console.warn(`ERR|rider_online|${on.status}`); return; }
  const seen = {};
  let job = null; // { orders: [...], phase: to_kitchen|wait_ready|to_customer, until }

  function ping() {
    lat += rand(-0.0008, 0.0008);
    lng += rand(-0.0008, 0.0008);
    const t0 = now();
    const r = http.post(`${RT}/api/v1/delivery/driver/location`, JSON.stringify({ lat, lng, speed: 7.5, heading: 90, accuracy: 8 }),
      { headers: h, tags: { name: "rider_ping" } });
    if (timed("rider_ping", r, r.status === 200)) {
      const o = r.json("order_id");
      if (o) rt("pub", o, r.json("timestamp"), t0, now());
    }
  }

  function accept(oid, via) {
    if (job || seen[oid]) return;
    seen[oid] = true;
    rt(`offer_${via}`, i, oid, now());
    const a = http.post(`${RT}/api/v1/offers/${oid}/accept`, null, { headers: h, tags: { name: "offer_accept" } });
    // 404/409: the offer was withdrawn or went elsewhere a moment ago (the app shows the same).
    if (!timed("offer_accept", a, a.status === 200 || a.status === 404 || a.status === 409) || a.status !== 200) return;
    const batch = (a.json("batch") || []).map((b) => (typeof b === "string" ? b : b.order_id)).filter(Boolean);
    job = { orders: batch.length ? batch : [oid], phase: "to_kitchen", until: now() + rand(60, 120) * 1000 };
  }

  function setStatus(oid, status, body) {
    const t0 = now();
    const r = http.put(`${API}/orders/${oid}/status`, JSON.stringify(Object.assign({ status }, body || {})), { headers: h, tags: { name: "rider_status" } });
    if (timed("rider_status", r, r.status === 200)) rt("put", oid, status, t0, now());
    return r.status === 200;
  }

  function step() {
    const me = http.get(`${RT}/api/v1/riders/me`, { headers: h, tags: { name: "rider_me" } });
    if (timed("rider_me", me, me.status === 200)) {
      const offer = me.json("offer");
      if (offer && offer.order_id && !seen[offer.order_id]) accept(offer.order_id, "poll");
    }
    if (!job || now() < job.until) return;
    if (job.phase === "to_kitchen") {
      job.phase = "wait_ready";
    }
    if (job.phase === "wait_ready") {
      let ready = true;
      job.orders.forEach((o) => {
        const g = http.get(`${API}/orders/${o}`, { headers: h, tags: { name: "rider_order" } });
        const st = g.status === 200 ? g.json("status") : "";
        if (st === "cancelled") job.orders = job.orders.filter((x) => x !== o);
        else if (st !== "ready") ready = false;
      });
      if (!job.orders.length) { job = null; return; }
      if (!ready) return;
      job.orders.forEach((o) => setStatus(o, "picked_up"));
      job.phase = "to_customer";
      job.until = now() + rand(90, 180) * 1000;
      return;
    }
    if (job.phase === "to_customer") {
      const o = job.orders.shift();
      const g = http.get(`${API}/orders/${o}`, { headers: h, tags: { name: "rider_order" } });
      const cust = g.status === 200 ? data.pins[g.json("customer_id")] : null;
      // The customer reads out the PIN on their order screen.
      const pin = cust ? http.get(`${API}/orders/${o}`, { headers: auth(cust), tags: { name: "order_pin" } }).json("pin") : "";
      setStatus(o, "delivered", { proof: { method: "pin", pin: pin || "" } });
      if (job.orders.length) job.until = now() + rand(45, 90) * 1000;
      else job = null;
    }
  }

  while (now() < data.end) {
    ws.connect(`${WS}/ws/rider`, { headers: { Authorization: `Bearer ${token}` }, tags: { name: "ws_rider" } }, (socket) => {
      socket.on("message", (raw) => {
        let m;
        try { m = JSON.parse(raw); } catch (e) { return; }
        if (m.type === "offer" && m.payload && m.payload.order_id) accept(m.payload.order_id, "ws");
      });
      socket.on("error", () => wsErrors.add(1));
      socket.setInterval(() => { ping(); step(); }, 5000);
      socket.setTimeout(() => socket.close(), Math.max(1000, data.end - now()));
    });
  }
  http.post(`${RT}/api/v1/riders/me/offline`, null, { headers: h, tags: { name: "rider_offline" } });
}

// ── kitchen tablets: the board every 4 s ─────────────────────────────────────
export function tablet(data) {
  const i = exec.scenario.iterationInTest;
  const kid = data.tabletKitchens[i % data.tabletKitchens.length];
  const actor = i < data.tabletKitchens.length; // one tablet per kitchen moves the orders
  const h = auth(data.owner[kid]);
  const seen = {};
  const plan = {}; // order -> { accept, almost, ready, done: [] }
  rt("tablet", i, kid, now());

  function move(oid, status) {
    const t0 = now();
    const r = http.put(`${API}/orders/${oid}/status`, JSON.stringify({ status }), { headers: h, tags: { name: "kitchen_status" } });
    if (timed("kitchen_status", r, r.status === 200)) rt("put", oid, status, t0, now());
    return r.status === 200;
  }

  while (now() < data.end) {
    const t0 = now();
    const b = http.get(`${API}/orders/restaurant/${kid}?limit=100`, { headers: h, tags: { name: "board" } });
    const d = http.get(`${API}/restaurants/${kid}/today`, { headers: h, tags: { name: "today" } });
    timed("today", d, d.status === 200);
    if (timed("board", b, b.status === 200)) {
      (b.json("items") || []).forEach((o) => {
        if (!seen[o.id]) {
          seen[o.id] = true;
          rt("kseen", i, kid, o.id, now());
        }
        if (actor && o.status === "placed" && !plan[o.id]) {
          const acc = now() + rand(5, 20) * 1000;
          const prep = rand(180, 300) * 1000;
          plan[o.id] = { accept: acc, almost: acc + prep * 0.6, ready: acc + prep, step: 0 };
        }
      });
    }
    if (actor) {
      Object.keys(plan).forEach((oid) => {
        const p = plan[oid];
        if (p.step === 0 && now() >= p.accept) p.step = move(oid, "accepted") && move(oid, "preparing") ? 1 : 9;
        if (p.step === 1 && now() >= p.almost) p.step = move(oid, "almost_ready") ? 2 : 9;
        if (p.step === 2 && now() >= p.ready) p.step = move(oid, "ready") ? 3 : 9;
      });
    }
    sleep(Math.max(0.1, 4 - (now() - t0) / 1000));
  }
  rt("tablet_end", i, kid, now());
}

export function teardown() {}
