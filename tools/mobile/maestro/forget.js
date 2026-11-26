// R44 (Maestro runScript, on the host; local stack only): a sign-up flow deletes the account it made, so a full run leaves
// no test accounts. Signs in with the flow's phone (PHONE, national digits; COUNTRY US|IN) and the local fixed code
// 123456, then DELETE /users/me (the app's own "Delete account": personal data gone, a restaurant owner's restaurant leaves
// every listing). The app has just used this number's code, so a fresh one is sent after the 30 s per-number wait.
var API = "http://localhost:8001/api/v1";
var CC = (typeof COUNTRY !== "undefined" && COUNTRY) || "IN";
var full = (CC === "US" ? "+1" : "+91") + PHONE;
function call(method, url, token, body) {
  var headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  var r = http.request(url, { method: method, headers: headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: r.status, body: r.body && (r.body.charAt(0) === "{" || r.body.charAt(0) === "[") ? json(r.body) : r.body };
}
var v = call("POST", API + "/auth/phone", null, { phone: full, otp: "123456", country: CC });
if (v.status !== 200) {
  var until = Date.now() + 31000;
  while (Date.now() < until) { /* the per-number wait */ }
  call("POST", API + "/auth/send-otp", null, { phone: full, country: CC });
  v = call("POST", API + "/auth/phone", null, { phone: full, otp: "123456", country: CC });
}
if (v.status !== 200) throw new Error("R44 clean-up: sign-in as " + full + " -> " + v.status);
var d = call("DELETE", API + "/users/me", v.body.access_token);
if (d.status !== 200) throw new Error("R44 clean-up: delete " + full + " -> " + d.status + " " + JSON.stringify(d.body).slice(0, 120));
console.log("R44 deleted the test account " + full);
