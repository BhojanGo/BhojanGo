// The rest of the world for the quick-messages flow (Maestro runScript, on the host).
//   STEP=order   customer1 (the phone this flow signs in with) orders from Spice
//                Route Kitchen and pays; the kitchen gets it ready, ops assigns
//                rider3, and the rider says they're at the kitchen.
//   STEP=check   the rider sees the customer's reply.
//   STEP=finish  the rider says they're outside, then picks up and delivers.
var API = "http://localhost:8001/api/v1";
var RT = "http://localhost:8004/api/v1";

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

function login(email, password) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: password || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return r.body.access_token;
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
  var pin = call("GET", API + "/orders/" + output.orderId, customer).body.pin;
  must(call("PUT", API + "/orders/" + output.orderId + "/status", rider, { status: "picked_up" }), "picked_up");
  must(call("PUT", API + "/orders/" + output.orderId + "/status", rider, { status: "delivered", proof: { method: "pin", pin: pin } }), "delivered");
}
