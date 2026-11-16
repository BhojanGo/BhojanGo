// Live batching (task 43) for the rider flow `batch.yaml` (Maestro runScript, on the host).
//   STEP=setup    Hyderabad turns live batching on (as an admin would, in Pricing & Rules),
//                 the other Hyderabad riders go offline, and two customers order from
//                 Spice Route Kitchen to two homes a street apart in Jubilee Hills. The
//                 kitchen starts both; the batch engine pairs them and realtime offers the
//                 pair to us. output.first / output.second: the order ids.
//   STEP=ready    the kitchen marks both ready; output.pin1 / output.pin2 for the drop-offs.
//   STEP=cleanup  batching back off; anything left from an earlier run cancelled.
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

function uuid4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = Math.floor(Math.random() * 16);
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function login(email, password) {
  // Sign-in is limited to 10 a minute: keep each token for the run (output lives across steps).
  var key = "tok_" + email.replace(/[^a-z0-9]/g, "_");
  if (output[key]) return output[key];
  var r = call("POST", API + "/auth/login", null, { email: email, password: QA_PW[email] || password || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  output[key] = secondStep(email, r.body).access_token;
  return output[key];
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
  var r = call("POST", API + "/auth/mfa/verify", null, { mfa_token: body.mfa_token, code: nextTotp(email) });
  if (r.status !== 200) throw new Error("second step " + email + " -> " + r.status);
  return r.body;
}

function waitFor(check, tries) {
  for (var i = 0; i < (tries || 600); i++) {
    var v = check();
    if (v) return v;
  }
  throw new Error("timed out waiting");
}

function batching(live) {
  var cm = login("cm.in@example.com", "BhojanGoAdmin1");
  var rule = call("GET", API + "/rules?family=business", cm).body.filter(function (r) {
    return r.template === "batching" && r.market_scope === "IN-TG-HYD" && r.status === "published" && !r.effective_to;
  })[0];
  if (!!rule.params.live !== live) {
    var v = call("POST", API + "/rules/" + rule.id + "/versions", cm, { params: { live: live } });
    if (v.status >= 300) throw new Error("batching rule " + v.status + " " + JSON.stringify(v.body));
    var sub = call("POST", API + "/rules/" + v.body.id + "/submit", cm);  // batching changes rider pay: maker-checker
    if (sub.status >= 300) throw new Error("batching submit " + sub.status + " " + JSON.stringify(sub.body));
    if (sub.body.status === "pending_approval") {
      var ok = call("POST", API + "/rules/" + v.body.id + "/approve", login("finance.in@example.com", "BhojanGoAdmin1"), { note: "e2e" });
      if (ok.status >= 300) throw new Error("batching approve " + ok.status + " " + JSON.stringify(ok.body));
    }
  }
}

var partner = login("partner.hyd@example.com");
var customers = [login("customer2.hyd@example.com"), login("customer3.hyd@example.com")];
var homes = [
  { street: "8-2-293, Road No. 36, Jubilee Hills", lat: 17.4307, lng: 78.4072 },
  { street: "8-2-310, Road No. 37, Jubilee Hills", lat: 17.4318, lng: 78.4088 },
];

if (STEP === "cleanup") {
  batching(false);
  var ops = login("ops.hyd@example.com", "BhojanGoAdmin1");
  customers.forEach(function (c) {
    call("GET", API + "/orders?limit=50", c).body.items.forEach(function (o) {
      if (["placed", "accepted", "preparing", "almost_ready", "ready", "picked_up"].indexOf(o.status) >= 0) {
        call("POST", API + "/orders/" + o.id + "/cancel", ops, { reason: "other", note: "e2e: left over from an earlier run" });
      }
    });
  });
}

if (STEP === "setup") {
  batching(true);
  // Other Hyderabad riders off the road, so the offer comes to us (best effort: sign-in is rate-limited
  // and after a fresh start they're offline anyway).
  ["rider2.hyd@example.com", "rider3.hyd@example.com"].forEach(function (e) {
    try { call("POST", RT + "/riders/me/offline", login(e)); } catch (err) { /* already offline */ }
  });
  var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];
  var menu = call("GET", API + "/restaurants/" + rest.id + "/menu").body;
  var item = null;
  menu.categories.forEach(function (c) { c.items.forEach(function (i) { if (i.name === "Veg Dum Biryani") item = i; }); });
  var cart = [{ menu_item_id: item.id, quantity: 2 }];
  var ids = [];
  for (var n = 0; n < 2; n++) {
    var drop = { lat: homes[n].lat, lng: homes[n].lng };
    var q = call("POST", API + "/pricing/quote", customers[n], { restaurant_id: rest.id, items: cart, deliver_to: drop });
    if (q.status !== 200) throw new Error("quote " + q.status + " " + JSON.stringify(q.body));
    var o = call("POST", API + "/orders", customers[n], {
      restaurant_id: rest.id, items: cart, payment_method: "upi", quote_token: q.body.token,
      delivery_address: { street: homes[n].street, city: "Hyderabad", state: "Telangana", zip: "500033", country: "IN",
        lat: drop.lat, lng: drop.lng, landmark: "Jubilee Hills" },
    }, { "X-Idempotency-Key": uuid4() });
    if (o.status !== 201) throw new Error("order " + o.status + " " + JSON.stringify(o.body));
    call("POST", API + "/payments/initiate", customers[n], { order_id: o.body.id, payment_method_type: "upi" });
    ids.push(o.body.id);
  }
  ids.forEach(function (id, n) {
    waitFor(function () { return call("GET", API + "/orders/" + id, customers[n]).body.status === "placed"; });
  });
  ["accepted", "preparing", "almost_ready"].forEach(function (s) {
    ids.forEach(function (id) {
      var r = call("PUT", API + "/orders/" + id + "/status", partner, { status: s });
      if (r.status !== 200) throw new Error(s + " " + r.status + " " + JSON.stringify(r.body));
    });
  });
  output.first = ids[0];
  output.second = ids[1];
}

if (STEP === "ready") {
  var pins = [];
  [output.first, output.second].forEach(function (id, n) {
    waitFor(function () { return call("GET", API + "/orders/" + id, customers[n]).body.driver_id; });
    var r = call("PUT", API + "/orders/" + id + "/status", partner, { status: "ready" });
    if (r.status !== 200) throw new Error("ready " + r.status);
  });
  // The drop-offs come in the order the engine chose; read both PINs.
  output.pin1 = call("GET", API + "/orders/" + output.first, customers[0]).body.pin;
  output.pin2 = call("GET", API + "/orders/" + output.second, customers[1]).body.pin;
}

if (STEP === "pin") {
  // The PIN of the order the rider is dropping now (the engine picks the drop-off order).
  var me = call("GET", RT + "/riders/me", login("rider1.hyd@example.com")).body;
  var current = me.state.order_id;
  var who = current === output.first ? customers[0] : customers[1];
  output.pin = call("GET", API + "/orders/" + current, who).body.pin;
}
