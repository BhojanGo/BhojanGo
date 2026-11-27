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
//   tidy       (R44; each flow's onFlowComplete, pass or fail, and before setup) everything a test made on the market's
//              restaurant goes: dishes, option groups and categories named "R4x …" (a test name), so a run leaves none
//   catdel     (R45) a category "R45 Lunch …" with one dish (over the API); output.ai = its row, the website shows it
//   catkept    the category CAT_ID is still there (refused, or "Keep"); with NAME, that dish is still in it
//   catgone    the category CAT_ID is gone: the editor's menu, customers' menu, the website page (polled, at most 60 s from
//              the delete: R45_WEB_SECONDS), and the newest history row is "category NAME deleted" by you
//   optdish    a dish of this run's own (over the API) for the options flow
//   options    the dish has the group "R43 Size" (required, 1..1) with its prices and the hours FROM-UNTIL; the quote refuses it
//              outside them, and (hours cleared) adds the Full option's price; then the dish and group are deleted
var API = "http://localhost:8001/api/v1";
var WEB = "http://localhost:3000";
var M = (typeof MARKET !== "undefined" && MARKET) || "in";
var P = M === "us" ? { email: "partner.boi@example.com", rest: "Boise Bowl Co.", cur: "$", base: "12.50", bad: "12.999", big: "30.00",
                       full: "3.50", page: "/us/boise/boise-bowl-co-hyde-park", lat: 43.6150, lng: -116.2023, customer: "customer1.boi@example.com", tz: "America/Boise" }
                   : { email: "partner.hyd@example.com", rest: "Spice Route Kitchen", cur: "₹", base: "120", bad: "120.50", big: "300",
                       full: "60", page: "/in/hyderabad/spice-route-kitchen-madhapur", lat: 17.4483, lng: 78.3915, customer: "customer1.hyd@example.com", tz: "Asia/Kolkata" };

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

var TEST = /^R4\d( |$)/;  // a test's name: "R43 Dish 1234", "R44 Size"
function tidy() {
  var m = manage();
  m.items.forEach(function (i) { if (TEST.test(i.name) || TEST.test(i.category || "")) must(call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + i.id, tok).status === 204, "delete dish " + i.name); });
  m.option_groups.forEach(function (g) { if (TEST.test(g.name)) must(call("DELETE", API + "/restaurants/" + rid + "/option-groups/" + g.id, tok).status === 204, "delete group " + g.name); });
  m.categories.forEach(function (c) { if (TEST.test(c.name)) must(call("DELETE", API + "/restaurants/" + rid + "/categories/" + c.id, tok).status === 204, "delete category " + c.name); });
}
if (STEP === "tidy") tidy();
if (STEP === "setup") {
  tidy();
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
  tidy();
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
  must(g && g.name === "R43 Size" && g.min_picks === 1 && g.max_picks === 1, "group " + JSON.stringify(g));
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

// R45: Delete category
function webShows(name) {  // the restaurant's website page (server-rendered, no-store menu) names it
  var r = http.request(WEB + P.page, { method: "GET" });
  must(r.status === 200, "website " + P.page + " -> " + r.status);
  return r.body.indexOf(name) >= 0;
}
function waitWeb(name, shown, seconds) {
  var until = Date.now() + seconds * 1000;
  while (webShows(name) !== shown) {
    must(Date.now() < until, "the website still " + (shown ? "doesn't show " : "shows ") + name + " after " + seconds + " s");
    var t = Date.now() + 2000; while (Date.now() < t) { /* wait */ }
  }
}
if (STEP === "catdel") {
  tidy();
  var tg = String(Math.floor(1000 + Math.random() * 8999));
  var cn = "R45 Lunch " + tg, dn = "R45 Dish " + tg;
  var cr = call("POST", API + "/restaurants/" + rid + "/categories", tok, { name: cn });
  must(cr.status === 201, "category " + cr.status);
  var dr = call("POST", API + "/restaurants/" + rid + "/menu-items", tok, { name: dn, price: P.base, category: cn, category_id: cr.body.id });
  must(dr.status === 201 && dr.body.category_id === cr.body.id, "dish " + dr.status);
  var ids = manage().categories.map(function (x) { return x.id; });
  output.cat = cn; output.catId = cr.body.id; output.dish = dn; output.ai = String(ids.indexOf(cr.body.id));
  waitWeb(cn, true, 30);  // before: customers see it on the website
}
if (STEP === "catkept") {
  var mk = manage();
  must(mk.categories.some(function (x) { return x.id === CAT_ID; }), "the category went (it should stay)");
  if (typeof NAME !== "undefined" && NAME) {
    var dk = mk.items.filter(function (i) { return i.name === NAME; })[0];
    must(dk && dk.category_id === CAT_ID, NAME + " left the category");
  }
}
if (STEP === "catgone") {
  must(!manage().categories.some(function (x) { return x.id === CAT_ID; }), NAME + " still in the editor's menu");
  var pm = call("GET", API + "/restaurants/" + rid + "/menu").body;
  must(!pm.categories.some(function (x) { return x.id === CAT_ID; }), NAME + " still on customers' menu");
  var hr = call("GET", API + "/restaurants/" + rid + "/menu/history?limit=5", tok).body.changes[0];
  must(hr.entity === "category" && hr.action === "deleted" && hr.name === NAME && hr.who === "you" && hr.entity_id === CAT_ID,
       "newest history row " + JSON.stringify(hr).slice(0, 200));
  waitWeb(NAME, false, 60);
  var sec = (Date.now() - Date.parse(hr.at)) / 1000;
  console.log("R45_WEB_SECONDS=" + sec.toFixed(1));
  must(sec <= 60, "the website dropped " + NAME + " " + sec.toFixed(1) + " s after the delete (limit 60 s)");
}

// R46: category hours on the tablet
//   cathours  a category "R46 Breakfast …" with one dish (over the API), no hours; output.ci = its row; every category
//             the run starts with (the seed's) has no hours
//   cathrs    the category CAT_ID's hours are FROM-UNTIL ("" = none: All day); customers' menu agrees (listed only inside)
if (STEP === "cathours") {
  tidy();
  var t6 = String(Math.floor(1000 + Math.random() * 8999));
  var cn6 = "R46 Breakfast " + t6;
  var c6 = call("POST", API + "/restaurants/" + rid + "/categories", tok, { name: cn6 });
  must(c6.status === 201, "category " + c6.status);
  must(call("POST", API + "/restaurants/" + rid + "/menu-items", tok, { name: "R46 Poha " + t6, price: P.base, category: cn6, category_id: c6.body.id }).status === 201, "dish");
  var cs6 = manage().categories;
  cs6.forEach(function (x) { if (x.id !== c6.body.id) must(!x.available_from && !x.available_until, x.name + " has hours " + x.available_from + "-" + x.available_until); });
  output.cat = cn6; output.catId = c6.body.id; output.ci = String(cs6.map(function (x) { return x.id; }).indexOf(c6.body.id));
}
if (STEP === "cathrs") {
  var m6 = manage().categories.filter(function (x) { return x.id === CAT_ID; })[0];
  must(m6, "category gone");
  must((m6.available_from || "") === FROM && (m6.available_until || "") === UNTIL, "hours " + m6.available_from + "-" + m6.available_until + " != " + FROM + "-" + UNTIL);
  var pub6 = call("GET", API + "/restaurants/" + rid + "/menu").body;
  var listed = pub6.categories.some(function (x) { return x.id === CAT_ID; });
  if (!FROM) must(listed, "an all-day category isn't on customers' menu");
  else {
    var lt = call("GET", API + "/restaurants/" + rid + "/availability").body.local_time.slice(11, 16);
    var inside = FROM < UNTIL ? (lt >= FROM && lt < UNTIL) : (lt >= FROM || lt < UNTIL);
    must(listed === inside, "listed=" + listed + " at " + lt + " for hours " + FROM + "-" + UNTIL);
  }
}
