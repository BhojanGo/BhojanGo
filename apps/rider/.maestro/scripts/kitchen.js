// The rest of the world as the rider sees it, for the rider flows (Maestro
// runScript, run on the host): STEP=order  a customer orders from Spice Route
// Kitchen and pays (fake provider), the kitchen accepts and starts cooking, so
// dispatch offers it to the nearest online rider. Other Hyderabad riders go
// offline first, so the offer comes to us.  STEP=ready  the kitchen marks it
// ready.  STEP=pin  after pickup, the customer's PIN for the drop-off (output.pin): the
// customer only sees it once the rider has the food (R27).
// Hosted QA: maestro test -e QA_CORE=https://... -e QA_RT=https://... -e QA_PASSWORDS='{"email":"password"}'
// (tools/railway/maestro-qa.sh); locally the defaults below.
var QA_PW = (typeof QA_PASSWORDS !== "undefined" && QA_PASSWORDS) ? JSON.parse(QA_PASSWORDS) : {};
var API = (typeof QA_CORE !== "undefined" && QA_CORE ? QA_CORE : "http://localhost:8001") + "/api/v1";
var RT = (typeof QA_RT !== "undefined" && QA_RT ? QA_RT : "http://localhost:8004") + "/api/v1";

function call(method, url, token, body, extra) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  if (extra) for (var k in extra) headers[k] = extra[k];
  var opts = { headers: headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  else if (method !== "GET") opts.body = "{}"; // Maestro wants a body on POST and PUT
  var r = method === "GET" ? http.get(url, opts) : method === "PUT" ? http.put(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? json(r.body) : null };
}

function uuid4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = Math.floor(Math.random() * 16);
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// ── Admin two-step sign-in (Round 8): RFC 6238 codes in plain ES5 (Maestro has no crypto).
// Keys: QA_TOTP_KEYS ('{"email":"key"}', tools/railway/maestro-qa.sh) else the seed's
// non-production key (tools/seed/data.py SEED_TOTP_SECRET). A code is never accepted twice,
// so the last step used per email is kept in output.totpLast across the flow's scripts.
var TOTP_KEYS = (typeof QA_TOTP_KEYS !== "undefined" && QA_TOTP_KEYS) ? JSON.parse(QA_TOTP_KEYS) : {};
var SEED_TOTP_KEY = "BHOJANGOSEEDADMINTOTPKEY234567AB";
function sha1(bytes) {
  var h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0], m = bytes.slice(), bits = bytes.length * 8, w = [], i, t;
  m.push(0x80);
  while (m.length % 64 !== 56) m.push(0);
  for (i = 7; i >= 0; i--) m.push(i >= 4 ? 0 : (bits >>> (i * 8)) & 255);
  for (var o = 0; o < m.length; o += 64) {
    for (t = 0; t < 16; t++) w[t] = (m[o + 4 * t] << 24) | (m[o + 4 * t + 1] << 16) | (m[o + 4 * t + 2] << 8) | m[o + 4 * t + 3];
    for (t = 16; t < 80; t++) { var x = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]; w[t] = (x << 1) | (x >>> 31); }
    var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
    for (t = 0; t < 80; t++) {
      var f = t < 20 ? (b & c) | (~b & d) : t < 40 || t >= 60 ? b ^ c ^ d : (b & c) | (b & d) | (c & d);
      var k = t < 20 ? 0x5A827999 : t < 40 ? 0x6ED9EBA1 : t < 60 ? 0x8F1BBCDC : 0xCA62C1D6;
      var tmp = (((a << 5) | (a >>> 27)) + f + e + k + w[t]) | 0;
      e = d; d = c; c = (b << 30) | (b >>> 2); b = a; a = tmp;
    }
    h[0] = (h[0] + a) | 0; h[1] = (h[1] + b) | 0; h[2] = (h[2] + c) | 0; h[3] = (h[3] + d) | 0; h[4] = (h[4] + e) | 0;
  }
  var out = [];
  for (i = 0; i < 5; i++) out.push((h[i] >>> 24) & 255, (h[i] >>> 16) & 255, (h[i] >>> 8) & 255, h[i] & 255);
  return out;
}
function totpAt(key32, step) {
  var A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", key = [], buf = 0, n = 0, i;
  for (i = 0; i < key32.length; i++) { buf = (buf << 5) | A.indexOf(key32.charAt(i)); n += 5; if (n >= 8) { n -= 8; key.push((buf >>> n) & 255); } }
  while (key.length < 64) key.push(0);
  var msg = [0, 0, 0, 0, (step >>> 24) & 255, (step >>> 16) & 255, (step >>> 8) & 255, step & 255];
  var inner = sha1(key.map(function (b) { return b ^ 0x36; }).concat(msg));
  var mac = sha1(key.map(function (b) { return b ^ 0x5c; }).concat(inner));
  var off = mac[19] & 15;
  var num = ((mac[off] & 127) << 24) | (mac[off + 1] << 16) | (mac[off + 2] << 8) | mac[off + 3];
  return ("000000" + (num % 1000000)).slice(-6);
}
function nextTotp(email) {
  var last = (output.totpLast = output.totpLast || {});
  for (;;) {
    var now = Math.floor(Date.now() / 30000), step = Math.max(now - 1, (last[email] === undefined ? -1 : last[email]) + 1);
    if (step <= now + 1) { last[email] = step; return totpAt(TOTP_KEYS[email] || SEED_TOTP_KEY, step); }
    var until = Date.now() + 1000; while (Date.now() < until) { /* wait for the next 30-second step */ }
  }
}
// The sign-in answer -> tokens: an admin's answer asks for a code from the authenticator.
function secondStep(email, body) {
  if (!body || !body.mfa_required) return body;
  // A step another run already used is refused (never twice): try the next one, at most three times.
  for (var i = 0; i < 3; i++) {
    var r = call("POST", API + "/auth/mfa/verify", null, { mfa_token: body.mfa_token, code: nextTotp(email) });
    if (r.status === 200) return r.body;
  }
  throw new Error("second step " + email + " -> " + r.status);
}

function login(email, password) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: QA_PW[email] || password || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return secondStep(email, r.body).access_token;  // an admin answers the second step (R8)
}

function waitFor(check, tries) {
  for (var i = 0; i < (tries || 600); i++) {
    var v = check();
    if (v) return v;
  }
  throw new Error("timed out waiting");
}

var partner = login("partner.hyd@example.com");
var customer = login("customer2.hyd@example.com");

if (STEP === "cleanup") {
  // Leftovers from an earlier run that stopped half-way would be offered first
  // (or keep the rider busy): cancel them before the app starts.
  var ops = login("ops.hyd@example.com", "BhojanGoAdmin1");
  call("GET", API + "/orders?limit=50", customer).body.items.forEach(function (o) {
    if (["placed", "accepted", "preparing", "almost_ready", "ready"].indexOf(o.status) >= 0) {
      call("POST", API + "/orders/" + o.id + "/cancel", ops, { reason: "other", note: "e2e: left over from an earlier run" });
    }
  });
}

if (STEP === "order") {
  ["rider2.hyd@example.com", "rider3.hyd@example.com"].forEach(function (e) {
    call("POST", RT + "/riders/me/offline", login(e));
  });
  var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];
  var menu = call("GET", API + "/restaurants/" + rest.id + "/menu").body;
  var item = null;
  menu.categories.forEach(function (c) { c.items.forEach(function (i) { if (i.name === "Veg Dum Biryani") item = i; }); });
  var cart = [{ menu_item_id: item.id, quantity: 2 }];
  var drop = { lat: 17.4307, lng: 78.4072 }; // Priya's home in Jubilee Hills
  var q = call("POST", API + "/pricing/quote", customer, { restaurant_id: rest.id, items: cart, deliver_to: drop });
  if (q.status !== 200) throw new Error("quote " + q.status + " " + JSON.stringify(q.body));
  var o = call("POST", API + "/orders", customer, {
    restaurant_id: rest.id, items: cart, payment_method: "upi", quote_token: q.body.token,
    special_instructions: "Ring the bell twice. Second floor, flat 2B.",
    delivery_address: { street: "12-2-41, Road No. 36, Jubilee Hills", city: "Hyderabad", state: "Telangana", zip: "500033",
      country: "IN", lat: drop.lat, lng: drop.lng, landmark: "Jubilee Hills" },
  }, { "X-Idempotency-Key": uuid4() });
  if (o.status !== 201) throw new Error("order " + o.status + " " + JSON.stringify(o.body));
  var id = o.body.id;
  call("POST", API + "/payments/initiate", customer, { order_id: id, payment_method_type: "upi" });
  waitFor(function () { return call("GET", API + "/orders/" + id, customer).body.status === "placed"; });
  ["accepted", "preparing", "almost_ready"].forEach(function (s) {
    var r = call("PUT", API + "/orders/" + id + "/status", partner, { status: s });
    if (r.status !== 200) throw new Error(s + " " + r.status + " " + JSON.stringify(r.body));
  });
  output.orderId = id;
}

if (STEP === "ready") {
  var id2 = output.orderId;
  waitFor(function () { return call("GET", API + "/orders/" + id2, customer).body.driver_id; });
  var r2 = call("PUT", API + "/orders/" + id2 + "/status", partner, { status: "ready" });
  if (r2.status !== 200) throw new Error("ready " + r2.status);
}

if (STEP === "pin") {
  var id3 = output.orderId;
  waitFor(function () { return call("GET", API + "/orders/" + id3, customer).body.pin; });
  output.pin = call("GET", API + "/orders/" + id3, customer).body.pin;
}
