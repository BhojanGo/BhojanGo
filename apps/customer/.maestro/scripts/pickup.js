// The restaurant's side of the customer pickup flow (Maestro runScript, on the host), R32.
//   STEP=ready  Spice Route Kitchen accepts the customer's newest pickup order and marks it ready
//               (the customer's app then shows the 4-digit pickup code).
//   STEP=hand   the restaurant enters the code: the order is collected.
// Hosted QA: maestro test -e QA_CORE=https://... -e QA_PASSWORDS='{"email":"password"}'; locally the defaults below.
var QA_PW = (typeof QA_PASSWORDS !== "undefined" && QA_PASSWORDS) ? JSON.parse(QA_PASSWORDS) : {};
var API = (typeof QA_CORE !== "undefined" && QA_CORE ? QA_CORE : "http://localhost:8001") + "/api/v1";

function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var opts = { headers: headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  else if (method !== "GET") opts.body = "{}";
  var r = method === "GET" ? http.get(url, opts) : method === "PUT" ? http.put(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? json(r.body) : null };
}

function login(email) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: QA_PW[email] || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return r.body.access_token;
}

var partner = login("partner.hyd@example.com");
var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];
var list = call("GET", API + "/orders/restaurant/" + rest.id + "?limit=50", partner).body;
var orders = (list.items || list).filter(function (o) { return o.fulfillment === "pickup"; });
if (!orders.length) throw new Error("no pickup order at Spice Route Kitchen");
var order = orders[0];

if (STEP === "ready") {
  var steps = ["accepted", "preparing", "ready"];
  for (var i = 0; i < steps.length; i++) {
    if (order.status === "ready") break;
    if (order.status === "placed" || i > 0) {
      var r = call("PUT", API + "/orders/" + order.id + "/status", partner, { status: steps[i] });
      if (r.status !== 200) throw new Error(steps[i] + " -> " + r.status + " " + JSON.stringify(r.body));
      order = r.body;
    }
  }
  output.orderId = order.id;
} else if (STEP === "hand") {
  var customer = login("customer1.hyd@example.com");
  var code = call("GET", API + "/orders/" + order.id, customer).body.pickup_code;
  var done = call("POST", API + "/orders/" + order.id + "/pickup", partner, { code: code });
  if (done.status !== 200) throw new Error("pickup -> " + done.status + " " + JSON.stringify(done.body));
}
