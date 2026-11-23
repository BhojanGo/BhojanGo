// The rest of the world for the quick-messages flow (Maestro runScript, on the host).
//   STEP=order   customer1 (the phone this flow signs in with) orders from Spice
//                Route Kitchen and pays; the kitchen gets it ready, ops assigns
//                rider3, and the rider says they're at the kitchen.
//   STEP=check   the rider sees the customer's reply.
//   STEP=finish  the rider says they're outside, then picks up and delivers.
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
  else if (method !== "GET") opts.body = "{}";
  var r = method === "GET" ? http.get(url, opts) : method === "PUT" ? http.put(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? json(r.body) : null };
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

function sub(token) {
  var part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  while (part.length % 4) part += "=";
  // Maestro's JS has no atob: decode base64 by hand.
  var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", out = "", buf = 0, bits = 0;
  for (var i = 0; i < part.length && part[i] !== "="; i++) {
    buf = (buf << 6) | chars.indexOf(part[i]);
    bits += 6;
    if (bits >= 8) { bits -= 8; out += String.fromCharCode((buf >> bits) & 255); }
  }
  return json(out).sub;
}

function uuid4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = Math.floor(Math.random() * 16);
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function must(r, what) {
  if (r.status >= 300) throw new Error(what + " " + r.status + " " + JSON.stringify(r.body));
  return r.body;
}

var customer = login("customer1.hyd@example.com");
var rider = login("rider3.hyd@example.com");

if (STEP === "order") {
  var partner = login("partner.hyd@example.com");
  var ops = login("ops.hyd@example.com", "BhojanGoAdmin1");
  var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];
  var menu = call("GET", API + "/restaurants/" + rest.id + "/menu").body;
  var item = null;
  menu.categories.forEach(function (c) { c.items.forEach(function (i) { if (i.name === "Veg Dum Biryani") item = i; }); });
  var cart = [{ menu_item_id: item.id, quantity: 1 }];
  var q = must(call("POST", API + "/pricing/quote", customer, { restaurant_id: rest.id, items: cart, deliver_to: { lat: 17.4483, lng: 78.3915 } }), "quote");
  var o = must(call("POST", API + "/orders", customer, {
    restaurant_id: rest.id, items: cart, payment_method: "upi", quote_token: q.token,
    delivery_address: { street: "Flat 302", city: "Hyderabad", state: "Telangana", zip: "500081", country: "IN" },
  }, { "X-Idempotency-Key": uuid4() }), "order");
  var pay = must(call("POST", API + "/payments/initiate", customer, { order_id: o.id, payment_method_type: "upi" }), "pay");
  must(call("POST", API + "/payments/fake/" + pay.payment_intent_id + "/complete", customer, { outcome: "succeeded" }), "complete");
  ["accepted", "preparing", "ready"].forEach(function (s) { must(call("PUT", API + "/orders/" + o.id + "/status", partner, { status: s }), s); });
  must(call("POST", RT + "/delivery/assign", ops, { order_id: o.id, driver_id: sub(rider) }), "assign");
  must(call("POST", API + "/orders/" + o.id + "/messages", rider, { preset: "at_kitchen" }), "message");
  output.orderId = o.id;
}

if (STEP === "check") {
  var texts = must(call("GET", API + "/orders/" + output.orderId + "/messages", rider), "read").messages.map(function (m) { return m.text; });
  if (texts.indexOf("Please ring the bell.") < 0) throw new Error("rider didn't get the reply: " + JSON.stringify(texts));
  must(call("POST", API + "/orders/" + output.orderId + "/messages", rider, { preset: "outside" }), "outside");
}

if (STEP === "finish") {
  must(call("PUT", API + "/orders/" + output.orderId + "/status", rider, { status: "picked_up" }), "picked_up");
  var pin = call("GET", API + "/orders/" + output.orderId, customer).body.pin; // the customer sees it once picked up
  must(call("PUT", API + "/orders/" + output.orderId + "/status", rider, { status: "delivered", proof: { method: "pin", pin: pin } }), "delivered");
}
