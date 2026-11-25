// R43 (Maestro runScript, on the host): the restaurant app's menu editing checked against the API, US or India
// (MARKET=us|in). Local stack only. Each STEP throws on a mismatch, so the flow fails there.
//   setup      a fresh name for this run's dish / category, the market's prices; old R43 dishes are deleted first
//   dish       the dish (NAME) in GET /menu/manage equals what was typed: PRICE, SPICE, VEG (India), DESC, its category
//   price      the dish's price is PRICE (e.g. unchanged after a refused rule, changed after "Change price")
//   history    the dish's newest history row is a price change OLD -> NEW by the partner; output.line is how the app shows it
//   gone       the dish is off the menu (manage and customers'), still a row with deleted_at (past orders keep it)
//   wrongrole  a customer's token can't edit the menu or read its history (403)
//   cats       the categories: output.last = the new category's index (it's added last), output.count
//   cat        the category CAT has NAME2, hours FROM-UNTIL, is hidden, and is first in the order (after the drag)
//   catback    the categories in their order before the run; the new one stays hidden
//   optdish    a dish of this run's own (over the API) for the options flow
//   options    the dish has the group "Size" (required, 1..1) with its prices and the hours FROM-UNTIL; the quote refuses it
//              outside them, and (hours cleared) adds the Full option's price; then the dish and group are deleted
var API = "http://localhost:8001/api/v1";
var M = (typeof MARKET !== "undefined" && MARKET) || "in";
var P = M === "us" ? { email: "partner.boi@example.com", rest: "Boise Bowl Co.", cur: "$", base: "12.50", bad: "12.999", big: "30.00",
                       full: "3.50", lat: 43.6150, lng: -116.2023, customer: "customer1.boi@example.com", tz: "America/Boise" }
                   : { email: "partner.hyd@example.com", rest: "Spice Route Kitchen", cur: "₹", base: "120", bad: "120.50", big: "300",
                       full: "60", lat: 17.4483, lng: 78.3915, customer: "customer1.hyd@example.com", tz: "Asia/Kolkata" };

function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var r = http.request(url, { method: method, headers: headers, body: body === undefined ? (method === "GET" || method === "DELETE" ? undefined : "{}") : JSON.stringify(body) });
  var b = r.body && (r.body.charAt(0) === "{" || r.body.charAt(0) === "[") ? json(r.body) : r.body;
  return { status: r.status, body: b };
}
function login(email) {
  var r = call("POST", API + "/auth/login", null, { email: email, password: "BhojanGo123" });
  if (r.status !== 200) throw new Error("login " + email + " -> " + r.status);
  return r.body.access_token;
}
function must(cond, why) { if (!cond) throw new Error("R43 check failed: " + why); }
function money(v) {
  var n = Number(v), s = M === "us" ? n.toFixed(2) : n.toFixed(2);
  return P.cur + s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
function re(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

var tok = login(P.email);
var rid = call("GET", API + "/restaurants?limit=100").body.items.filter(function (r) { return r.name === P.rest; })[0].id;
var manage = function () { return call("GET", API + "/restaurants/" + rid + "/menu/manage", tok).body; };
var dishOf = function (name) { return manage().items.filter(function (i) { return i.name === name; })[0]; };

if (STEP === "setup") {
  manage().items.forEach(function (i) { if (i.name.indexOf("R43 ") === 0) call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + i.id, tok); });
  var tag = String(Math.floor(1000 + Math.random() * 8999));
  output.name = "R43 Dish " + tag;
  output.renamed = "R43 Special " + tag;
  output.cat = "R43 Breakfast " + tag;
  output.cat2 = "R43 Morning " + tag;
  output.base = P.base; output.bad = P.bad; output.big = P.big; output.full = P.full;
  output.order = JSON.stringify(manage().categories.map(function (c) { return c.id; }));
}
if (STEP === "dish") {
  var d = dishOf(NAME);
  must(d, NAME + " not in the menu");
  must(Number(d.price) === Number(PRICE), "price " + d.price + " != " + PRICE);
  must(String(d.spice_level) === SPICE, "spice " + d.spice_level + " != " + SPICE);
  must(d.description === DESC, "description " + JSON.stringify(d.description));
  if (M === "in") must(d.is_veg === (VEG === "true"), "veg " + d.is_veg);
  must(d.category_id === manage().categories[0].id, "category " + d.category + " is not the first category");
  output.dishId = d.id;
}
if (STEP === "price") {
  var d2 = dishOf(NAME);
  must(Number(d2.price) === Number(PRICE), "price " + d2.price + " != " + PRICE);
}
if (STEP === "history") {
  var d3 = dishOf(NAME);
  var h = call("GET", API + "/restaurants/" + rid + "/menu/history?item_id=" + d3.id, tok).body.changes;
  var top = h[0], ch = top.changes.filter(function (c) { return c.field === "price"; })[0];
  must(top.action === "changed" && top.who === "you" && ch, "newest history row " + JSON.stringify(top).slice(0, 200));
  must(Number(ch.old) === Number(OLD) && Number(ch.new) === Number(NEW), "price change " + ch.old + " -> " + ch.new);
  must(h[h.length - 1].action === "added", "the first row isn't 'added'");
  output.line = re("Price: " + money(ch.old) + " → " + money(ch.new));
}
if (STEP === "gone") {
  must(!dishOf(NAME), NAME + " still in the editor's menu");
  var pub = call("GET", API + "/restaurants/" + rid + "/menu").body;
  var all = pub.uncategorized_items.concat.apply(pub.uncategorized_items, pub.categories.map(function (c) { return c.items; }));
  must(!all.some(function (i) { return i.name === NAME; }), NAME + " still on customers' menu");
}
if (STEP === "wrongrole") {
  var cust = login(P.customer);
  var any = manage().items[0];
  must(call("PUT", API + "/restaurants/" + rid + "/menu-items/" + any.id, cust, { price: "1" }).status === 403, "a customer edited a dish");
  must(call("GET", API + "/restaurants/" + rid + "/menu/history", cust).status === 403, "a customer read the history");
  must(call("POST", API + "/restaurants/" + rid + "/categories", cust, { name: "nope" }).status === 403, "a customer added a category");
}
if (STEP === "cats") {
  var cs = manage().categories;
  output.count = String(cs.length);
  output.last = String(cs.length - 1);
}
if (STEP === "cat") {
  var c = manage().categories;
  var mine = c.filter(function (x) { return x.name === NAME2; })[0];
  must(mine, NAME2 + " not a category (rename)");
  must(mine.available_from === FROM && mine.available_until === UNTIL, "hours " + mine.available_from + "-" + mine.available_until);
  must(mine.is_active === false, "not hidden");
  must(c[0].id === mine.id, "not first after the drag: " + c.map(function (x) { return x.name; }).join(", "));
  var pub2 = call("GET", API + "/restaurants/" + rid + "/menu").body;
  must(!pub2.categories.some(function (x) { return x.id === mine.id; }), "customers still see the hidden category");
}
if (STEP === "catback") {
  var before = JSON.parse(ORDER), now = manage().categories.map(function (x) { return x.id; });
  var rest = now.filter(function (id) { return before.indexOf(id) < 0; });
  must(call("PUT", API + "/restaurants/" + rid + "/categories-order", tok, { category_ids: before.concat(rest) }).status === 200, "order back");
}
if (STEP === "optdish") {
  manage().items.forEach(function (i) { if (i.name.indexOf("R43 ") === 0) call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + i.id, tok); });
  var name = "R43 Opt " + String(Math.floor(1000 + Math.random() * 8999));
  must(call("POST", API + "/restaurants/" + rid + "/menu-items", tok, { name: name, price: P.base, category: "R43" }).status === 201, "dish");
  output.name = name; output.full = P.full;
  // hours that aren't now (local): from 3 hours ahead, for an hour
  var h0 = Number(call("GET", API + "/restaurants/" + rid + "/availability").body.local_time.slice(11, 13));
  var pad = function (n) { return (n < 10 ? "0" : "") + n + ":00"; };
  output.from = pad((h0 + 3) % 24); output.until = pad((h0 + 4) % 24);
}
if (STEP === "options") {
  var d4 = dishOf(NAME);
  var groups = manage().option_groups;
  var g = groups.filter(function (x) { return d4.option_group_ids.indexOf(x.id) >= 0; })[0];
  must(g && g.name === "Size" && g.min_picks === 1 && g.max_picks === 1, "group " + JSON.stringify(g));
  var full = g.options.filter(function (o) { return o.name === "Full"; })[0], half = g.options.filter(function (o) { return o.name === "Half"; })[0];
  must(full && Number(full.price) === Number(P.full) && half && Number(half.price) === 0, "option prices " + JSON.stringify(g.options));
  must(d4.available_from === FROM && d4.available_until === UNTIL, "hours " + d4.available_from + "-" + d4.available_until);
  var cust2 = login(P.customer);
  var item = { menu_item_id: d4.id, quantity: 4, options: [{ group: g.id, option: full.id }] };
  var q = call("POST", API + "/pricing/quote", cust2, { restaurant_id: rid, items: [item], deliver_to: { lat: P.lat, lng: P.lng } });
  must(q.status === 422 && JSON.stringify(q.body).indexOf("is served") >= 0, "the quote took it outside its hours: " + q.status);
  call("PUT", API + "/restaurants/" + rid + "/menu-items/" + d4.id, tok, { available_from: null, available_until: null });
  q = call("POST", API + "/pricing/quote", cust2, { restaurant_id: rid, items: [item], deliver_to: { lat: P.lat, lng: P.lng } });
  must(q.status === 200, "quote " + q.status + " " + JSON.stringify(q.body).slice(0, 160));
  var food = q.body.lines.filter(function (l) { return l.code === "food"; })[0].amount;
  must(Number(food) === (Number(P.base) + Number(P.full)) * 4, "food " + food + " != (" + P.base + " + " + P.full + ") x 4");
  call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + d4.id, tok);
  call("DELETE", API + "/restaurants/" + rid + "/option-groups/" + g.id, tok);
}
