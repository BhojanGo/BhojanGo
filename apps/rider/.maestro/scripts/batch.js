// Live batching (task 43) for the rider flow `batch.yaml` (Maestro runScript, on the host).
//   STEP=setup    Hyderabad turns live batching on (as an admin would, in Pricing & Rules),
//                 the other Hyderabad riders go offline, and two customers order from
//                 Spice Route Kitchen to two homes a street apart in Jubilee Hills. The
//                 kitchen starts both; the batch engine pairs them and realtime offers the
//                 pair to us. output.first / output.second: the order ids.
//   STEP=ready    the kitchen marks both ready; output.pin1 / output.pin2 for the drop-offs.
//   STEP=cleanup  batching back off; anything left from an earlier run cancelled.
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
  var r = call("POST", API + "/auth/login", null, { email: email, password: password || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  output[key] = r.body.access_token;
  return output[key];
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
    var sub = call("POST", API + "/rules/" + v.body.id + "/submit", cm);  // business rules go live on submit
    if (sub.status >= 300) throw new Error("batching submit " + sub.status + " " + JSON.stringify(sub.body));
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
