// A delivered order to report a problem with (Maestro runScript, on the host):
// customer1 (the phone this flow signs in with) orders four Irani chai from
// Charminar Chai House and pays; the kitchen gets it ready, ops gives it to
// rider3, who picks it up and delivers it with the customer's PIN.
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

function must(r, what) {
  if (r.status >= 300) throw new Error(what + " " + r.status + " " + JSON.stringify(r.body));
  return r.body;
}

function login(email, password) {
  return must(call("POST", API + "/auth/login", null, { email: email, password: QA_PW[email] || password || "BhojanGo123" }), "login " + email).access_token;
}

function sub(token) {
  var part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
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

var customer = login("customer1.hyd@example.com");
var partner = login("partner.hyd@example.com");
var ops = login("ops.hyd@example.com", "BhojanGoAdmin1");
var rider = login("rider3.hyd@example.com");
var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Charminar Chai House"; })[0];
var menu = call("GET", API + "/restaurants/" + rest.id + "/menu").body;
var chai = null;
menu.categories.forEach(function (c) { c.items.forEach(function (i) { if (i.name === "Irani Chai") chai = i; }); });
var cart = [{ menu_item_id: chai.id, quantity: 4 }]; // Old City has a Rs 99 minimum order
var q = must(call("POST", API + "/pricing/quote", customer, { restaurant_id: rest.id, items: cart, deliver_to: { lat: 17.365, lng: 78.47 } }), "quote");
var o = must(call("POST", API + "/orders", customer, {
  restaurant_id: rest.id, items: cart, payment_method: "upi", quote_token: q.token,
  delivery_address: { street: "Lane 4", city: "Hyderabad", state: "Telangana", zip: "500002", country: "IN" },
}, { "X-Idempotency-Key": uuid4() }), "order");
var pay = must(call("POST", API + "/payments/initiate", customer, { order_id: o.id, payment_method_type: "upi" }), "pay");
must(call("POST", API + "/payments/fake/" + pay.payment_intent_id + "/complete", customer, { outcome: "succeeded" }), "complete");
["accepted", "preparing", "ready"].forEach(function (s) { must(call("PUT", API + "/orders/" + o.id + "/status", partner, { status: s }), s); });
must(call("POST", RT + "/delivery/assign", ops, { order_id: o.id, driver_id: sub(rider) }), "assign");
var pin = call("GET", API + "/orders/" + o.id, customer).body.pin;
must(call("PUT", API + "/orders/" + o.id + "/status", rider, { status: "picked_up" }), "picked_up");
must(call("PUT", API + "/orders/" + o.id + "/status", rider, { status: "delivered", proof: { method: "pin", pin: pin } }), "delivered");
output.orderId = o.id;
