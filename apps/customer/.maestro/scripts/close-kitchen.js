// R36: close one restaurant for today and tomorrow (its own day), or open it again (Maestro runScript, local).
//   SLUG=charminar-chai-house-old-city PARTNER=partner.hyd@example.com UTC_OFFSET_MIN=330 STATE=closed|open
// Hosted QA: maestro test -e QA_CORE=https://... -e QA_PASSWORDS='{"email":"password"}'; locally the defaults below.
var QA_PW = (typeof QA_PASSWORDS !== "undefined" && QA_PASSWORDS) ? JSON.parse(QA_PASSWORDS) : {};
var API = (typeof QA_CORE !== "undefined" && QA_CORE ? QA_CORE : "http://localhost:8001") + "/api/v1";

function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var opts = { headers: headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  var r = method === "GET" ? http.get(url, opts) : method === "PUT" ? http.put(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? json(r.body) : null };
}

var login = call("POST", API + "/auth/login", null, { email: PARTNER, password: QA_PW[PARTNER] || "BhojanGo123" });
if (login.status !== 200) throw new Error("login " + PARTNER + " -> " + login.status);
var token = login.body.access_token;
var rest = call("GET", API + "/restaurants?limit=100").body.items.filter(function (r) { return r.slug === SLUG; })[0];
if (!rest) throw new Error("no restaurant " + SLUG);
var local = new Date(Date.now() + Number(UTC_OFFSET_MIN) * 60000);
for (var d = 0; d < 2; d++) {
  var day = new Date(local.getTime() + d * 86400000).toISOString().slice(0, 10);
  var body = STATE === "closed" ? { closed: true, note: "R36 test" } : { closed: false, opens: "00:00", closes: "00:00", note: "E2E" };
  var r = call("PUT", API + "/restaurants/" + rest.id + "/hours/overrides/" + day, token, body);
  if (r.status !== 200) throw new Error("override " + day + " -> " + r.status + " " + JSON.stringify(r.body));
}
