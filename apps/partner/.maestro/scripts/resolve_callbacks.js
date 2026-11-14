// Start the help flow with no open call-back request for Spice Route Kitchen:
// support resolves any left from an earlier run (Maestro runScript, on the host).
// Hosted QA: maestro test -e QA_CORE=https://... -e QA_RT=https://... -e QA_PASSWORDS='{"email":"password"}'
// (tools/railway/maestro-qa.sh); locally the defaults below.
var QA_PW = (typeof QA_PASSWORDS !== "undefined" && QA_PASSWORDS) ? JSON.parse(QA_PASSWORDS) : {};
var API = (typeof QA_CORE !== "undefined" && QA_CORE ? QA_CORE : "http://localhost:8001") + "/api/v1";

function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var opts = { headers: headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  else if (method !== "GET") opts.body = "{}";
  var r = method === "GET" ? http.get(url, opts) : http.post(url, opts);
  return { status: r.status, body: r.body ? json(r.body) : null };
}

var support = call("POST", API + "/auth/login", null, { email: "support.hyd@example.com", password: QA_PW["support.hyd@example.com"] || "BhojanGoAdmin1" }).body.access_token;
call("GET", API + "/ops/tickets?scope=IN-TG-HYD", support).body.forEach(function (t) {
  if (t.kind === "callback" && t.restaurant_name === "Spice Route Kitchen") {
    call("POST", API + "/ops/tickets/" + t.id + "/resolve", support, { resolution: "e2e: left over from an earlier run" });
  }
});
