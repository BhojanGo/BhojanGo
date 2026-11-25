// R43 (Maestro runScript, on the host): a restaurant with no orders and no payout account (MARKET=us|in).
//   board    the restaurant (REST) has no orders today: GET /restaurants/{id}/today counts 0 and /orders/restaurant/{id} is empty
//   before   it has no payout account (GET /finance/payout-accounts/... none)
//   after    "Set up payouts" made one with the market's provider, waiting for the restaurant to finish (not ready)
// Local stack only.
var API = "http://localhost:8001/api/v1";
var M = (typeof MARKET !== "undefined" && MARKET) || "in";
var email = M === "us" ? "partner.boi@example.com" : "partner.hyd@example.com";
function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var r = http.request(url, { method: method, headers: headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: r.status, body: r.body && (r.body.charAt(0) === "{" || r.body.charAt(0) === "[") ? json(r.body) : r.body };
}
function must(cond, why) { if (!cond) throw new Error("R43 check failed: " + why); }
var tok = call("POST", API + "/auth/login", null, { email: email, password: "BhojanGo123" }).body.access_token;
var rest = call("GET", API + "/restaurants/mine", tok).body.filter(function (r) { return r.name === REST; })[0];
must(rest, REST + " isn't " + email + "'s");
if (STEP === "board") {
  var list = call("GET", API + "/orders/restaurant/" + rest.id + "?limit=5", tok).body;
  var items = list.items || list;
  must(items.length === 0, REST + " has " + items.length + " orders");
  var today = call("GET", API + "/restaurants/" + rest.id + "/today", tok).body;
  must(Number(today.today_orders) === 0 && Number(today.today_sales) === 0, "today's orders " + JSON.stringify(today).slice(0, 160));
}
if (STEP === "before" || STEP === "after") {
  var setup = call("GET", API + "/finance/payout-accounts/me/setup?payee_type=restaurant&restaurant_id=" + rest.id, tok).body || {};
  if (STEP === "before") must(!setup.account, "already has a payout account: " + JSON.stringify(setup.account));
  else must(setup.account && setup.state !== "ready", "no payout account after Set up: " + JSON.stringify(setup).slice(0, 200));
  output.state = setup.state;
}
