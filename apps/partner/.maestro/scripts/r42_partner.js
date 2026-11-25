// R42 (Maestro runScript, on the host), the restaurant app's numbers and effects checked against the API:
//   STEP=rejected  the newest order at Spice Route Kitchen (the one the flow just rejected) is cancelled and refunded
//   STEP=web       the dish (DISH) shows "Sold out" (SOLD=1) or not (SOLD=0) on the website within LIMIT seconds;
//                  output.seconds is how long it took (the website's menu is cached; the API is immediate)
//   STEP=payouts   the restaurant's statements (GET /finance/statements/me): output.s1..s3, their amounts as the app
//                  formats them (the flow asserts each is on screen; tools/sweep/functional/apps.py checks the same
//                  statements equal admin Finance's)
// Local stack only.
var API = "http://localhost:8001/api/v1";
var WEB = "http://localhost:3000";

function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var opts = { headers: headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  else if (method !== "GET") opts.body = "{}";
  var r = method === "GET" ? http.get(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? (r.body.charAt(0) === "{" || r.body.charAt(0) === "[" ? json(r.body) : r.body) : null };
}
function login(email, pw) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: pw || "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return r.body;
}
function fmt(v, cur) {
  var n = Math.abs(Number(v)), s = n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return (Number(v) < 0 ? "−" : "") + cur + s;
}
var partner = login("partner.hyd@example.com").access_token;
var rest = call("GET", API + "/restaurants?limit=100").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];

if (STEP === "rejected") {
  var list = call("GET", API + "/orders/restaurant/" + rest.id + "?limit=5", partner).body;
  var o = (list.items || list)[0];
  if (o.status !== "cancelled") throw new Error("the rejected order is " + o.status);
  if (["refunded", "refund_pending", "partially_refunded"].indexOf(o.payment_status) < 0 && o.payment_status !== "voided")
    throw new Error("the rejected order's payment is " + o.payment_status + ", not refunded");
  output.rejected = o.id.slice(0, 8);
}

if (STEP === "web") {
  var start = Date.now(), want = SOLD === "1", limit = Number(LIMIT || 90) * 1000, seen = null;
  while (Date.now() - start < limit) {
    var page = http.get(WEB + "/in/hyderabad/spice-route-kitchen-madhapur", { headers: { "Cache-Control": "no-cache" } }).body || "";
    var i = page.indexOf(DISH);
    var near = i >= 0 ? page.slice(i, i + 1500) : "";
    seen = near.indexOf("Sold out") >= 0;
    if (seen === want) break;
    var t = Date.now(); while (Date.now() - t < 3000) { /* wait 3 s */ }
  }
  if (seen !== want) throw new Error("the website still shows " + DISH + (want ? " in stock" : " sold out") + " after " + (limit / 1000) + " s");
  output.seconds = String(Math.round((Date.now() - start) / 1000));
}

if (STEP === "payouts") {
  var mine = call("GET", API + "/finance/statements/me", partner).body;
  var items = (mine.items || mine).filter(function (s) { return s.payee_type === "restaurant"; });
  for (var k = 1; k <= 3; k++) output["s" + k] = "";
  for (var j = 0; j < items.length && j < 3; j++) {
    output["s" + (j + 1)] = fmt(items[j].amount, "₹");
  }
  output.count = String(items.length);
}
