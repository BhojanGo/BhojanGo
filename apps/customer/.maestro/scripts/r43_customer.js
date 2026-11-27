// R43 (Maestro runScript, on the host), customer app checks against the API (MARKET=us|in). Local stack only.
//   phone    a brand-new phone number in the range the local stack answers with code 123456 (a new customer)
//   empty    that new customer (PHONE) has no orders, addresses or favourites in the API; then the account is deleted
//   setup    on the market's restaurant (as its partner): dish A at BASE, dish B served only at other hours, spice Medium
//   change   dish A's price -> NEW; output.t0 = when (the flow then reopens the restaurant until NEW shows)
//   elapsed  seconds from the change until the app showed it (must be <= 60); printed as R43_SECONDS=<s>
//   catsetup (R45) a category "R45 Brunch …" with one dish on the restaurant (the app shows its heading)
//   catdelete the restaurant deletes the dish, then the (now empty) category, as on the tablet; output.t0 = the delete
//   hrsetup  (R46) "R46 Breakfast …" (a dish; hours that aren't now, the restaurant's clock), "R46 Mains …" (a dish,
//            all day) and "R46 Empty …" (no dishes); customers' menu and the website list only Mains
//   hrnow    Breakfast's hours become the hour around now; output.t0; customers' menu and the website list it
//   cleanup  every test dish and category ("R4x …") deleted, pass or fail
var API = "http://localhost:8001/api/v1";
var M = (typeof MARKET !== "undefined" && MARKET) || "in";
var P = M === "us" ? { partner: "partner.boi@example.com", rest: "Boise Bowl Co.", cur: "\\$", base: "12.57", next: "13.79", cc: "+1" }
                   : { partner: "partner.hyd@example.com", rest: "Spice Route Kitchen", cur: "₹", base: "251", next: "283", cc: "+91" };
function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var r = http.request(url, { method: method, headers: headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: r.status, body: r.body && (r.body.charAt(0) === "{" || r.body.charAt(0) === "[") ? json(r.body) : r.body };
}
function must(cond, why) { if (!cond) throw new Error("R43 check failed: " + why); }
function priceRe(v) {
  var n = Number(v), whole = n === Math.floor(n);
  var s = n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",").replace(".", "\.");
  return ".*" + P.cur + (whole ? s.replace("\.00", "(\.00)?") : s) + ".*";
}
if (STEP === "phone") {
  output.phone = M === "us" ? "2085550" + String(Math.floor(500 + Math.random() * 400)) : "90000" + String(Math.floor(10000 + Math.random() * 89999));
}
if (STEP === "empty") {
  var full = P.cc + PHONE, cc = M === "us" ? "US" : "IN";
  var v = call("POST", API + "/auth/phone", null, { phone: full, otp: "123456", country: cc });
  if (v.status !== 200) {  // the app's code was used: a new one (one per 30 s per number)
    var until = Date.now() + 31000;
    while (Date.now() < until) { /* wait */ }
    must(call("POST", API + "/auth/send-otp", null, { phone: full, country: cc }).status < 300, "send-otp");
    v = call("POST", API + "/auth/phone", null, { phone: full, otp: "123456", country: cc });
  }
  must(v.status === 200, "phone sign-in " + v.status + " " + JSON.stringify(v.body).slice(0, 120));
  var tok = v.body.access_token;
  var o = call("GET", API + "/orders?limit=5", tok).body;
  must(((o && o.items) || o || []).length === 0, "orders " + JSON.stringify(o).slice(0, 100));
  must(call("GET", API + "/me/addresses", tok).body.length === 0, "addresses");
  var f = call("GET", API + "/me/favourites", tok).body;
  must(f.restaurants.length === 0 && f.items.length === 0, "favourites " + JSON.stringify(f).slice(0, 100));
  // R44: the test account goes again (the app's own Delete account), so a run leaves no test accounts
  must(call("DELETE", API + "/users/me", tok).status === 200, "deleting the test account");
}
var ptok = call("POST", API + "/auth/login", null, { email: P.partner, password: "BhojanGo123" }).body.access_token;
var rid = call("GET", API + "/restaurants?limit=100").body.items.filter(function (r) { return r.name === P.rest; })[0].id;
if (STEP === "setup") {
  var manage = call("GET", API + "/restaurants/" + rid + "/menu/manage", ptok).body;
  manage.items.forEach(function (i) { if (/^R4\d( |$)/.test(i.name)) call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + i.id, ptok); });
  var tag = String(Math.floor(1000 + Math.random() * 8999));
  var h0 = Number(call("GET", API + "/restaurants/" + rid + "/availability").body.local_time.slice(11, 13));
  var pad = function (n) { return (n < 10 ? "0" : "") + n + ":00"; };
  var cat = manage.categories[0].id;
  var a = call("POST", API + "/restaurants/" + rid + "/menu-items", ptok, { name: "R43 Aa " + tag, price: P.base, category: "R43", category_id: cat });
  var b = call("POST", API + "/restaurants/" + rid + "/menu-items", ptok, { name: "R43 Ab " + tag, price: P.base, category: "R43", category_id: cat,
    spice_level: 2, available_from: pad((h0 + 3) % 24), available_until: pad((h0 + 5) % 24) });
  must(a.status === 201 && b.status === 201, "dishes " + a.status + "/" + b.status);
  output.rid = rid; output.a = a.body.name; output.aid = a.body.id; output.b = b.body.name; output.bid = b.body.id;
  output.base = priceRe(P.base); output.next = priceRe(P.next);
}
if (STEP === "change") {
  must(call("PUT", API + "/restaurants/" + rid + "/menu-items/" + AID, ptok, { price: P.next }).status === 200, "price change");
  output.t0 = String(Date.now());
}
if (STEP === "elapsed") {
  var s = (Date.now() - Number(T0)) / 1000;
  console.log("R43_SECONDS=" + s.toFixed(1));
  output.seconds = s.toFixed(1);
  must(s <= 60, "the app showed the change " + s.toFixed(1) + " s after it was made (limit 60 s)");
}
if (STEP === "cleanup") {  // R44: every test dish on the restaurant ("R4x …"), pass or fail (the flows' onFlowComplete)
  call("GET", API + "/restaurants/" + rid + "/menu/manage", ptok).body.items.forEach(function (i) {
    if (/^R4\d( |$)/.test(i.name)) must(call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + i.id, ptok).status === 204, "delete " + i.name);
  });
  call("GET", API + "/restaurants/" + rid + "/menu/manage", ptok).body.categories.forEach(function (c) {
    if (/^R4\d( |$)/.test(c.name)) must(call("DELETE", API + "/restaurants/" + rid + "/categories/" + c.id, ptok).status === 204, "delete " + c.name);
  });
}
if (STEP === "catsetup") {
  var cn = "R45 Brunch " + String(Math.floor(1000 + Math.random() * 8999));
  var cr = call("POST", API + "/restaurants/" + rid + "/categories", ptok, { name: cn });
  must(cr.status === 201, "category " + cr.status);
  var dr = call("POST", API + "/restaurants/" + rid + "/menu-items", ptok, { name: "R45 Toast " + cn.slice(-4), price: P.base, category: cn, category_id: cr.body.id });
  must(dr.status === 201, "dish " + dr.status);
  output.rid = rid; output.cat = cn; output.catId = cr.body.id; output.dishId = dr.body.id;
}
if (STEP === "catdelete") {
  must(call("DELETE", API + "/restaurants/" + rid + "/menu-items/" + DISH_ID, ptok).status === 204, "delete the dish");
  must(call("DELETE", API + "/restaurants/" + rid + "/categories/" + CAT_ID, ptok).status === 204, "delete category");
  output.t0 = String(Date.now());
}

// R46: category hours, on the restaurant's clock
var WEB = "http://localhost:3000", PAGE = M === "us" ? "/us/boise/boise-bowl-co-hyde-park" : "/in/hyderabad/spice-route-kitchen-madhapur";
function listed() {  // category names on customers' menu (the API the app and website read)
  return call("GET", API + "/restaurants/" + rid + "/menu").body.categories.map(function (c) { return c.name; });
}
function onWeb() { var r = http.request(WEB + PAGE, { method: "GET" }); must(r.status === 200, "website " + r.status); return r.body; }
function pad(n) { return (n < 10 ? "0" : "") + n + ":00"; }
if (STEP === "hrsetup") {
  var tg = String(Math.floor(1000 + Math.random() * 8999));
  var h0 = Number(call("GET", API + "/restaurants/" + rid + "/availability").body.local_time.slice(11, 13));
  var made = {};
  [["Breakfast", { available_from: pad((h0 + 2) % 24), available_until: pad((h0 + 3) % 24) }, true], ["Mains", null, true], ["Empty", null, false]].forEach(function (k) {
    var name = "R46 " + k[0] + " " + tg;
    var c = call("POST", API + "/restaurants/" + rid + "/categories", ptok, { name: name });
    must(c.status === 201, "category " + name);
    if (k[1]) must(call("PUT", API + "/restaurants/" + rid + "/categories/" + c.body.id, ptok, k[1]).status === 200, "hours");
    if (k[2]) must(call("POST", API + "/restaurants/" + rid + "/menu-items", ptok, { name: "R46 " + k[0] + " dish " + tg, price: P.base, category: name, category_id: c.body.id }).status === 201, "dish");
    made[k[0]] = { name: name, id: c.body.id };
  });
  var names = listed(), page = onWeb();
  must(names.indexOf(made.Mains.name) >= 0 && names.indexOf(made.Breakfast.name) < 0, "customers' menu: " + names.join(", "));
  must(page.indexOf(made.Mains.name) >= 0, "the website doesn't show the all-day category");
  must(page.indexOf(made.Breakfast.name) < 0, "the website shows the category outside its hours");
  must(page.indexOf(made.Empty.name) < 0, "the website shows the empty category");
  output.rid = rid; output.bf = made.Breakfast.name; output.bfId = made.Breakfast.id; output.mains = made.Mains.name; output.empty = made.Empty.name;
  output.hours = pad((h0 + 2) % 24) + "-" + pad((h0 + 3) % 24);
}
if (STEP === "hrnow") {
  var h1 = Number(call("GET", API + "/restaurants/" + rid + "/availability").body.local_time.slice(11, 13));
  must(call("PUT", API + "/restaurants/" + rid + "/categories/" + BF_ID, ptok, { available_from: pad(h1), available_until: pad((h1 + 1) % 24) }).status === 200, "hours now");
  output.t0 = String(Date.now());
  output.hours = pad(h1) + "-" + pad((h1 + 1) % 24);
  must(listed().indexOf(BF) >= 0, "customers' menu doesn't list it inside its hours");
  var until = Date.now() + 60000;
  while (onWeb().indexOf(BF) < 0) { must(Date.now() < until, "the website doesn't show it inside its hours after 60 s"); var w = Date.now() + 2000; while (Date.now() < w) { /* wait */ } }
  console.log("R46_WEB_SECONDS=" + ((Date.now() - Number(output.t0)) / 1000).toFixed(1));
}
