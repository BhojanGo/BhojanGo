// P24: k6 load test at 10× the expected pilot peak, against `make dev`.
// Run: tools/load/run.sh   (k6 in Docker on the compose network; ~6 minutes)
//
// Pilot peak (assumed, docs/load/report.md): ~60 orders an hour at dinner in the
// pilot zone, ~5 quotes per order, 30 riders sending a fix every 5 s, ~20 orders
// being tracked at once. 10× that:
//   place order   10 / minute   (quote + order + payment)
//   quote         1 / second
//   browse        5 / second    (kitchens, a kitchen page, a menu: the apps' API calls)
//   web pages     3 / second    (home, city page, kitchen page on the customer web)
//   rider pings   60 / second   (realtime)
//   tracking      200 WebSockets open at once (realtime)
// Every request is named; the thresholds fail the run if any p95 is over 500 ms.
import { check, sleep } from "k6";
import http from "k6/http";
import ws from "k6/ws";
import { Counter, Trend } from "k6/metrics";

const API = __ENV.API || "http://core-api:8001/api/v1";
const RT = __ENV.RT || "http://realtime:8004";
const WEB = __ENV.WEB || "http://web:3000";
const WS = RT.replace(/^http/, "ws");
const DUR = __ENV.DURATION || "5m";
const JSON_H = { "Content-Type": "application/json" };
// SCALE: 1 = 10× pilot peak (the default), 0.1 = 1× pilot peak (a smoke on a hosted QA).
const SCALE = Number(__ENV.SCALE || "1");
// Per second at SCALE 1 → per minute at this SCALE (k6 rates are whole numbers).
const perMin = (perSecond) => Math.max(1, Math.round(perSecond * 60 * SCALE));
const vus = (n) => Math.max(2, Math.ceil(n * SCALE));
// Hosted QA seeds random passwords: LOGINS is the seed's tab-separated logins file.
const PASSWORDS = {};
if (__ENV.LOGINS) {
  open(__ENV.LOGINS).split("\n").forEach((line) => {
    const f = line.split("\t");
    if (f.length === 4) PASSWORDS[f[2]] = f[3].trim();
  });
}

const wsConnect = new Trend("ws_connect_ms", true);
const wsMessages = new Counter("ws_messages");

const SCENARIOS = {
    web_pages: { executor: "constant-arrival-rate", rate: perMin(3), timeUnit: "1m", duration: DUR, preAllocatedVUs: vus(10), maxVUs: vus(40), exec: "webPages" },
    browse: { executor: "constant-arrival-rate", rate: perMin(5), timeUnit: "1m", duration: DUR, preAllocatedVUs: vus(20), maxVUs: vus(60), exec: "browse" },
    quote: { executor: "constant-arrival-rate", rate: perMin(1), timeUnit: "1m", duration: DUR, preAllocatedVUs: vus(10), maxVUs: vus(30), exec: "quote" },
    place_order: { executor: "constant-arrival-rate", rate: perMin(10 / 60), timeUnit: "1m", duration: DUR, preAllocatedVUs: vus(5), maxVUs: vus(20), exec: "placeOrder" },
    rider_pings: { executor: "constant-arrival-rate", rate: perMin(60), timeUnit: "1m", duration: DUR, preAllocatedVUs: vus(40), maxVUs: vus(150), exec: "ping" },
    // Customers open tracking over time, not all in the same second: 200 open sockets
    // within 30 s, then held for the run.
    tracking: { executor: "ramping-vus", startVUs: 0, stages: [{ duration: "30s", target: vus(200) }, { duration: DUR, target: vus(200) }], exec: "track" },
};
// ONLY=quote,browse runs just those scenarios (to measure one path on its own).
const ONLY = (__ENV.ONLY || "").split(",").filter(Boolean);

export const options = {
  discardResponseBodies: false,
  scenarios: Object.fromEntries(Object.entries(SCENARIOS).filter(([k]) => !ONLY.length || ONLY.includes(k))),
  thresholds: {
    "http_req_duration{name:web_home}": ["p(95)<500"],
    "http_req_duration{name:web_city}": ["p(95)<500"],
    "http_req_duration{name:web_kitchen}": ["p(95)<500"],
    "http_req_duration{name:restaurants}": ["p(95)<500"],
    "http_req_duration{name:restaurant_page}": ["p(95)<500"],
    "http_req_duration{name:menu}": ["p(95)<500"],
    "http_req_duration{name:quote}": ["p(95)<500"],
    "http_req_duration{name:place_order}": ["p(95)<500"],
    "http_req_duration{name:pay}": ["p(95)<500"],
    "http_req_duration{name:order}": ["p(95)<500"],
    "http_req_duration{name:rider_ping}": ["p(95)<500"],
    ws_connect_ms: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

function login(email, password) {
  const r = http.post(`${API}/auth/login`, JSON.stringify({ email, password: PASSWORDS[email] || password || "BhojanGo123" }), { headers: JSON_H });
  if (r.status !== 200) throw new Error(`login ${email}: ${r.status} ${r.body}`);
  return { Authorization: `Bearer ${r.json("access_token")}`, "Content-Type": "application/json" };
}

function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

const DROP = { lat: 17.4483, lng: 78.3915 };
const ADDRESS = { street: "Flat 302", city: "Hyderabad", state: "Telangana", zip: "500081", country: "IN" };

function quoteFor(h, d) {
  return http.post(`${API}/pricing/quote`, JSON.stringify({ restaurant_id: d.rest, items: d.cart, deliver_to: DROP }),
    { headers: h, tags: { name: "quote" } });
}

export function setup() {
  // Sign-in is rate limited (10 a minute): sign in once here and share the tokens.
  const customers = [1, 2, 3, 4, 5].map((i) => login(`customer${i}.hyd@example.com`));
  const riders = [1, 2, 3].map((i) => login(`rider${i}.hyd@example.com`));
  const rest = http.get(`${API}/restaurants?limit=50`).json("items").find((r) => r.name === "Spice Route Kitchen");
  const menu = http.get(`${API}/restaurants/${rest.id}/menu`).json();
  let item = null;
  menu.categories.forEach((c) => c.items.forEach((i) => { if (i.name === "Veg Dum Biryani") item = i; }));
  const d = { rest: rest.id, slug: rest.slug, cart: [{ menu_item_id: item.id, quantity: 2 }] };
  riders.forEach((h) => http.post(`${RT}/api/v1/riders/me/online`, JSON.stringify({ lat: 17.4495, lng: 78.3925 }), { headers: h }));
  // Orders to track: each customer has one paid order on its way.
  const tracked = customers.map((h) => {
    const q = quoteFor(h, d).json();
    const o = http.post(`${API}/orders`, JSON.stringify({ restaurant_id: d.rest, items: d.cart, payment_method: "upi", quote_token: q.token,
      delivery_address: ADDRESS }), { headers: Object.assign({ "X-Idempotency-Key": uuid() }, h) }).json();
    http.post(`${API}/payments/initiate`, JSON.stringify({ order_id: o.id, payment_method_type: "upi" }), { headers: h });
    return { id: o.id, token: h.Authorization.slice(7) };
  });
  return { customers, riders, d, tracked };
}

// The customer web's key screens (server-rendered, cached for 5 minutes).
export function webPages() {
  check(http.get(`${WEB}/`, { tags: { name: "web_home" } }), { "web home 200": (r) => r.status === 200 });
  check(http.get(`${WEB}/hyderabad`, { tags: { name: "web_city" } }), { "web city 200": (r) => r.status === 200 });
  check(http.get(`${WEB}/hyderabad/spice-route-kitchen-madhapur`, { tags: { name: "web_kitchen" } }), { "web kitchen 200": (r) => r.status === 200 });
}

export function browse() {
  const list = http.get(`${API}/restaurants?limit=50`, { tags: { name: "restaurants" } });
  check(list, { "kitchens 200": (r) => r.status === 200 });
  const d = list.json("items").find((r) => r.name === "Spice Route Kitchen");
  check(http.get(`${API}/restaurants/by-slug/${d.slug}`, { tags: { name: "restaurant_page" } }), { "page 200": (r) => r.status === 200 });
  check(http.get(`${API}/restaurants/${d.id}/menu`, { tags: { name: "menu" } }), { "menu 200": (r) => r.status === 200 });
}

export function quote(data) {
  const h = data.customers[Math.floor(Math.random() * data.customers.length)];
  check(quoteFor(h, data.d), { "quote 200": (r) => r.status === 200 });
}

export function placeOrder(data) {
  const h = data.customers[Math.floor(Math.random() * data.customers.length)];
  const q = quoteFor(h, data.d);
  if (!check(q, { "quote for order 200": (r) => r.status === 200 })) return;
  const o = http.post(`${API}/orders`, JSON.stringify({ restaurant_id: data.d.rest, items: data.d.cart, payment_method: "upi",
    quote_token: q.json("token"), delivery_address: ADDRESS }), { headers: Object.assign({ "X-Idempotency-Key": uuid() }, h), tags: { name: "place_order" } });
  if (!check(o, { "order 201": (r) => r.status === 201 })) return;
  const id = o.json("id");
  check(http.post(`${API}/payments/initiate`, JSON.stringify({ order_id: id, payment_method_type: "upi" }), { headers: h, tags: { name: "pay" } }),
    { "pay 201": (r) => r.status === 201 });
  check(http.get(`${API}/orders/${id}`, { headers: h, tags: { name: "order" } }), { "order 200": (r) => r.status === 200 });
}

export function ping(data) {
  const h = data.riders[Math.floor(Math.random() * data.riders.length)];
  const body = { lat: 17.4495 + (Math.random() - 0.5) * 0.01, lng: 78.3925 + (Math.random() - 0.5) * 0.01, speed: 6, accuracy: 8 };
  check(http.post(`${RT}/api/v1/delivery/driver/location`, JSON.stringify(body), { headers: h, tags: { name: "rider_ping" } }),
    { "ping 200": (r) => r.status === 200 });
}

export function track(data) {
  const t = data.tracked[__VU % data.tracked.length];
  const start = Date.now();
  const res = ws.connect(`${WS}/ws/track/${t.id}?token=${t.token}`, {}, (socket) => {
    socket.on("open", () => wsConnect.add(Date.now() - start));
    socket.on("message", () => wsMessages.add(1));
    socket.setTimeout(() => socket.close(), 55000);
  });
  check(res, { "ws 101": (r) => r && r.status === 101 });
  sleep(1);
}

export function teardown(data) {
  data.riders.forEach((h) => http.post(`${RT}/api/v1/riders/me/offline`, null, { headers: h }));
}
