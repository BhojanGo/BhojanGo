// Dispatch re-offer (P22), the world around the rider (Maestro runScript, on the host).
//   STEP=setup   rider3 goes offline; rider2 goes online a little further from
//                Spice Route Kitchen than us; customer2 orders and pays; the
//                kitchen starts cooking, so dispatch offers it to the nearest
//                rider: us.
//   STEP=check   after we pass, the same order is offered to rider2.
//   STEP=cleanup ops cancels the order; rider2 goes offline.
var API = "http://localhost:8001/api/v1";
var RT = "http://localhost:8004/api/v1";

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

function must(r, what) {
  if (r.status >= 300) throw new Error(what + " " + r.status + " " + JSON.stringify(r.body));
  return r.body;
}

// Tokens are kept across this flow's steps: sign-in is rate limited (10 a minute).
function login(email, password) {
  output.tokens = output.tokens || {};
  if (!output.tokens[email]) {
    output.tokens[email] = must(call("POST", API + "/auth/login", null, { email: email, password: password || "BhojanGo123" }), "login " + email).access_token;
  }
  return output.tokens[email];
}

function uuid4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = Math.floor(Math.random() * 16);
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

var rider2 = login("rider2.hyd@example.com");

if (STEP === "setup") {
  var customer = login("customer2.hyd@example.com");
  var partner = login("partner.hyd@example.com");
  call("POST", RT + "/riders/me/offline", login("rider3.hyd@example.com"));
  call("POST", RT + "/riders/me/offline", rider2);
  must(call("POST", RT + "/riders/me/online", rider2, { lat: 17.4530, lng: 78.3960 }), "rider2 online");
  var rest = call("GET", API + "/restaurants?limit=50").body.items.filter(function (r) { return r.name === "Spice Route Kitchen"; })[0];
  var menu = call("GET", API + "/restaurants/" + rest.id + "/menu").body;
  var item = null;
  menu.categories.forEach(function (c) { c.items.forEach(function (i) { if (i.name === "Veg Dum Biryani") item = i; }); });
  var cart = [{ menu_item_id: item.id, quantity: 1 }];
  var q = must(call("POST", API + "/pricing/quote", customer, { restaurant_id: rest.id, items: cart, deliver_to: { lat: 17.4307, lng: 78.4072 } }), "quote");
  var o = must(call("POST", API + "/orders", customer, {
    restaurant_id: rest.id, items: cart, payment_method: "upi", quote_token: q.token,
    delivery_address: { street: "Road No. 36, Jubilee Hills", city: "Hyderabad", state: "Telangana", zip: "500033", country: "IN", landmark: "Jubilee Hills" },
  }, { "X-Idempotency-Key": uuid4() }), "order");
  var pay = must(call("POST", API + "/payments/initiate", customer, { order_id: o.id, payment_method_type: "upi" }), "pay");
  must(call("POST", API + "/payments/fake/" + pay.payment_intent_id + "/complete", customer, { outcome: "succeeded" }), "complete");
  ["accepted", "preparing", "almost_ready"].forEach(function (s) { must(call("PUT", API + "/orders/" + o.id + "/status", partner, { status: s }), s); });
  output.orderId = o.id;
}

if (STEP === "check") {
  var offered = null;
  for (var i = 0; i < 300 && !offered; i++) {
    var me = call("GET", RT + "/riders/me", rider2).body;
    if (me && me.offer && me.offer.order_id === output.orderId) offered = me.offer;
  }
  if (!offered) throw new Error("the order wasn't re-offered to the next rider after we passed");
}

if (STEP === "cleanup") {
  var ops = login("ops.hyd@example.com", "BhojanGoAdmin1");
  call("POST", API + "/orders/" + output.orderId + "/cancel", ops, { reason: "other", note: "e2e: re-offer test" });
  call("POST", RT + "/riders/me/offline", rider2);
}
