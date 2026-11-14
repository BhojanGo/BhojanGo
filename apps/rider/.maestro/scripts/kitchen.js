// The rest of the world as the rider sees it, for the rider flows (Maestro
// runScript, run on the host): STEP=order  a customer orders from Spice Route
// Kitchen and pays (fake provider), the kitchen accepts and starts cooking, so
// dispatch offers it to the nearest online rider. Other Hyderabad riders go
// offline first, so the offer comes to us.  STEP=ready  the kitchen marks it
// ready, and the customer's PIN is read for the drop-off (output.pin).
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

function login(email, password) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: QA_PW[email] || password || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return r.body.access_token;
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
  output.pin = call("GET", API + "/orders/" + id2, customer).body.pin;
}
