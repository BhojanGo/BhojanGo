// R42 (Maestro runScript, on the host): the amounts the customer app should show, from the API, so the flow can
// assert each one is on screen (numbers checked against the API, not "by other tests").
//   STEP=bill     the quote for the cart the flow builds (DISH x1 at REST, to the customer's default address, the
//                 city's default tip): output.l1..l8 (each non-zero line, formatted as the app does), output.total
//   STEP=receipt  the customer's newest past order: output.paid (what the receipt says was paid), output.code
// MARKET=us|in (customer1.boi / customer1.hyd: the phones the flows sign in with). Local stack only.
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

function must(r, what) {
  if (r.status >= 300) throw new Error(what + " " + r.status + " " + JSON.stringify(r.body));
  return r.body;
}

function fmt(v, cur) {
  var n = Math.abs(Number(v));
  var s = n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return (Number(v) < 0 ? "−" : "") + cur + s;
}

// An amount as a Maestro text regex ("$14.50" would read as end-of-line + any character)
function re(s) { return s.replace(/[$]/g, "[$]").replace(/[.]/g, "[.]"); }

var us = MARKET === "us";
var email = us ? "customer1.boi@example.com" : "customer1.hyd@example.com";
var cur = us ? "$" : "₹";
var token = must(call("POST", API + "/auth/login", null, { email: email, password: "BhojanGo123" }), "login").access_token;

if (STEP === "bill") {
  var rest = must(call("GET", API + "/restaurants?limit=100"), "restaurants").items.filter(function (r) { return r.slug === REST; })[0];
  var menu = must(call("GET", API + "/restaurants/" + rest.id + "/menu"), "menu");
  var item = null;
  for (var c = 0; c < menu.categories.length && !item; c++)
    for (var i = 0; i < menu.categories[c].items.length; i++) if (menu.categories[c].items[i].name === DISH) item = menu.categories[c].items[i];
  var addrs = must(call("GET", API + "/me/addresses", token), "addresses");
  var addr = addrs.filter(function (a) { return a.is_default; })[0] || addrs[0];
  var body = { restaurant_id: rest.id, items: [{ menu_item_id: item.id, quantity: 1 }], deliver_to: { address_id: addr.id } };
  var q = must(call("POST", API + "/pricing/quote", token, body), "quote");
  var presets = q.tip_presets || {};
  var tip = presets.default != null ? presets.default : (presets.amounts && presets.amounts.length > 1 ? presets.amounts[1] : null);
  if (tip != null) { body.tip = String(tip); q = must(call("POST", API + "/pricing/quote", token, body), "quote with tip"); }
  var k = 1;
  for (var j = 0; j < q.lines.length && k <= 8; j++) {
    if (Number(q.lines[j].amount) === 0) continue;
    output["l" + k] = fmt(q.lines[j].amount, cur);
    k++;
  }
  for (; k <= 8; k++) output["l" + k] = "";
  output.total = fmt(q.total, cur);
  output.total_re = re(output.total);
  output.lines = String(q.lines.length);
}

if (STEP === "receipt") {
  // the newest past (delivered) order: the first row under "Past orders", whose receipt the flow opens
  var list = must(call("GET", API + "/orders?limit=50", token), "orders");
  var o = (list.items || list).filter(function (x) { return x.status === "delivered" || x.status === "cancelled"; })[0];
  output.paid = fmt(o.total, cur);
  output.paid_re = re(output.paid);
  output.code = String(o.id).slice(0, 8).toUpperCase();
}
