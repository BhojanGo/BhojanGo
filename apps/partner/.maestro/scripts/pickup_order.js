// For the partner pickup flow (Maestro runScript, on the host), R32, against `make dev`.
//   STEP=order  a customer (Priya) orders from Spice Route Kitchen for pickup and pays: the tablet rings.
//   STEP=code   the customer's pickup code (they show it at the counter once the order is ready), and a wrong one.
// Hosted QA: maestro test -e QA_CORE=https://... -e QA_PASSWORDS='{"email":"password"}'; locally the defaults below.
var QA_PW = (typeof QA_PASSWORDS !== "undefined" && QA_PASSWORDS) ? JSON.parse(QA_PASSWORDS) : {};
var API = (typeof QA_CORE !== "undefined" && QA_CORE ? QA_CORE : "http://localhost:8001") + "/api/v1";

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

function login(email) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: QA_PW[email] || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return r.body.access_token;
}

var customer = login("customer2.hyd@example.com");
if (STEP === "order") {
  var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];
  var menu = call("GET", API + "/restaurants/" + rest.id + "/menu").body;
  var item = null;
  menu.categories.forEach(function (c) { c.items.forEach(function (i) { if (i.name === "Veg Dum Biryani") item = i; }); });
  var cart = [{ menu_item_id: item.id, quantity: 1 }];
  var q = call("POST", API + "/pricing/quote", customer, { restaurant_id: rest.id, items: cart, fulfillment: "pickup" });
  if (q.status !== 200) throw new Error("quote " + q.status + " " + JSON.stringify(q.body));
  var o = call("POST", API + "/orders", customer, { restaurant_id: rest.id, items: cart, payment_method: "upi", quote_token: q.body.token },
    { "X-Idempotency-Key": uuid4() });
  if (o.status !== 201) throw new Error("order " + o.status + " " + JSON.stringify(o.body));
  call("POST", API + "/payments/initiate", customer, { order_id: o.body.id, payment_method_type: "upi" });
  for (var i = 0; i < 600 && call("GET", API + "/orders/" + o.body.id, customer).body.status !== "placed"; i++) { /* wait */ }
  output.pickupOrder = o.body.id;
} else if (STEP === "code") {
  var code = call("GET", API + "/orders/" + output.pickupOrder, customer).body.pickup_code;
  if (!code) throw new Error("no pickup code yet");
  output.pickupCode = code;
  output.wrongCode = ("000" + ((parseInt(code, 10) + 1) % 10000)).slice(-4);
}
