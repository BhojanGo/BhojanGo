// R42 (brief item c, Maestro runScript on the host): this week's earnings, from the API the app reads
// (GET /finance/earnings/me as rider1.hyd, the phone the flow signs in with). Every trip pays its delivery fee and
// the tip in full (+ a batch bonus when it was a batch): line.total = delivery_fee + tip (+ batch_bonus); throws if not.
// output.total_re: the week's total as a regex the Earnings screen must show (two decimals, or whole rupees).
var API = "http://localhost:8001/api/v1";
function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var opts = { headers: headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  else if (method !== "GET") opts.body = "{}";
  var r = method === "GET" ? http.get(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? json(r.body) : null };
}
var tok = call("POST", API + "/auth/login", null, { email: RIDER || "rider1.hyd@example.com", password: "BhojanGo123" }).body.access_token;
var w = call("GET", API + "/finance/earnings/me", tok).body;
var lines = (w.today && w.today.lines) || [];
var bad = [];
for (var i = 0; i < lines.length; i++) {
  var l = lines[i];
  if (l.delivery_fee === undefined) continue;  // older pay model (base + distance + waiting): not a delivery-fee trip
  var want = Number(l.delivery_fee) + Number(l.tip) + Number(l.batch_bonus || 0);
  if (Math.abs(want - Number(l.total)) > 0.005) bad.push(l.order_id.slice(0, 8) + ": " + l.total + " != " + want);
}
if (bad.length) throw new Error("trips not paid delivery fee + tip: " + bad.join("; "));
var t = Number(w.total), whole = Math.round(t), two = t.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
var wholeS = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
output.total_re = ".*(" + two.replace(/\./g, "[.]") + "|" + wholeS + ")$";
output.trips = String(lines.length);
