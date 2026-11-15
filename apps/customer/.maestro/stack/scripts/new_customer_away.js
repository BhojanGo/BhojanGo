// A brand-new customer whose only saved address is outside every delivery zone, made
// through the local core API before the app signs in with the same number (code 123456
// for 90000 numbers off production). Runs on the host; throwaway stack only.
var core = "http://localhost:8001/api/v1";
var phone = "90000" + String(Math.floor(10000 + Math.random() * 89999));
var e164 = "+91" + phone;
var asJson = { "Content-Type": "application/json" };
http.post(core + "/auth/send-otp", { headers: asJson, body: JSON.stringify({ phone: e164, country: "IN" }) });
var signedIn = http.post(core + "/auth/phone", {
  headers: asJson,
  body: JSON.stringify({ phone: e164, otp: "123456", country: "IN", full_name: "Asha Patel" }),
});
var token = json(signedIn.body).access_token;
var saved = http.post(core + "/me/addresses", {
  headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
  body: JSON.stringify({
    label: "Home", street: "1203 12th Ave S, Nampa", city: "Nampa", state: "ID", postal_code: "83651",
    country: "US", lat: 43.5654, lng: -116.5638, is_default: true,
  }),
});
if (saved.status >= 300) throw new Error("address not saved: " + saved.status + " " + saved.body);
output.phone = phone;
