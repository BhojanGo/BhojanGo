// R43 (r42 gap, Maestro runScript on the host): RIDER has no trips this week: GET /finance/earnings/me says 0 (total,
// deliveries, today's lines); output.zero is the week's total as the Earnings screen must show it ($0.00 / ₹0).
var API = "http://localhost:8001/api/v1";
function must(cond, why) { if (!cond) throw new Error("R43 check failed: " + why); }
var r = http.request(API + "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: RIDER, password: "BhojanGo123" }) });
var tok = json(r.body).access_token;
var w = json(http.request(API + "/finance/earnings/me", { method: "GET", headers: { Authorization: "Bearer " + tok } }).body);
must(Number(w.total) === 0, RIDER + " has " + w.total + " this week");
must(!((w.today && w.today.lines) || []).length, RIDER + " has trips today");
output.zero = w.currency === "INR" ? "₹0(\.00)?" : "\$0\.00";
