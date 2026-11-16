// node --test: "Add your kitchen" (/partner, R8 F7). The form's checks, the phone
// number it sends, and the commission line built from GET /kitchens/terms.
import assert from "node:assert/strict";
import test from "node:test";

import { apiProblem, applicationState, cityOptions, commissionSummary, defaultCity, e164, splitLinks, validate, type TermsCity } from "../src/lib/kitchenJoin.ts";

const CITIES: TermsCity[] = [
  { code: "AA-BB-SOON", name: "Zeta", region: "R", status: "soon", beta: false, starting_percent: "15" },
  { code: "AA-BB-ONE", name: "Beta", region: "R", status: "live", beta: true, starting_percent: "12" },
  { code: "AA-BB-TWO", name: "Alpha", region: "R", status: "live", beta: false, starting_percent: "15" },
];
const GOOD = { kitchen_name: "Amma's Kitchen", city_code: "AA-BB-ONE", full_name: "Lakshmi", phone: "98480 21234", email: "amma@example.com",
  password: "long enough!", accept_terms: true };

test("a complete form has no problems", () => {
  assert.deepEqual(validate(GOOD, "+91", CITIES), {});
});

test("every field is checked, in the form's order", () => {
  const bad = validate({ kitchen_name: " A ", city_code: "", full_name: "", phone: "12", email: "not-an-email", password: "short", accept_terms: false }, "+91", CITIES);
  assert.deepEqual(Object.keys(bad), ["kitchen_name", "city_code", "full_name", "phone", "email", "password", "accept_terms"]);
  assert.equal(bad.accept_terms, "consent");
  assert.equal(validate({ ...GOOD, password: "123456789" }, "+91", CITIES).password, "password"); // 9 is too short
  assert.deepEqual(validate({ ...GOOD, password: "1234567890" }, "+91", CITIES), {}); // 10 is enough
  assert.equal(validate({ ...GOOD, city_code: "XX-YY-ZZZ" }, "+91", CITIES).city_code, "city"); // not a city we take kitchens in
});

test("the phone number is sent with the country's calling code", () => {
  assert.equal(e164("+91", "98480 21234"), "+919848021234");
  assert.equal(e164("+91", "098480-21234"), "+919848021234"); // a trunk 0
  assert.equal(e164("+91", "+91 98480 21234"), "+919848021234"); // pasted with the code
  assert.equal(e164("+1", "(208) 555-0199"), "+12085550199");
});

test("the API's refusals land on the right field, without saying which account exists", () => {
  assert.deepEqual(apiProblem("ACCOUNT_EXISTS"), { field: "email", key: "exists" });
  assert.deepEqual(apiProblem("PASSWORD"), { field: "password", key: "password" });
  assert.deepEqual(apiProblem("PHONE_COUNTRY_MISMATCH"), { field: "phone", key: "phone" });
  assert.deepEqual(apiProblem(undefined), { key: "generic" });
});

test("commission comes from the live rules: a range, one rate, or not set yet", () => {
  const terms = { commission: { percent_min: "12", percent_max: "18", starting_percent: "15", flat_per_order: null }, cities: CITIES };
  assert.deepEqual(commissionSummary(terms, "AA-BB-ONE"), { kind: "range", min: 12, max: 18, start: 12, city: "Beta", flat: null });
  assert.deepEqual(commissionSummary(terms, null), { kind: "range", min: 12, max: 18, start: 15, city: null, flat: null });
  assert.deepEqual(commissionSummary({ commission: { percent_min: "20", percent_max: "20", flat_per_order: "1.5" }, cities: [] }, null),
    { kind: "one", percent: 20, flat: 1.5 });
  assert.deepEqual(commissionSummary({ commission: null, cities: CITIES }, null), { kind: "unknown" });
  assert.deepEqual(commissionSummary(null, null), { kind: "unknown" });
});

test("cities: live first by name, then coming soon; the visitor's own city is chosen when kitchens can apply there", () => {
  assert.deepEqual(cityOptions(CITIES).map((c) => c.code), ["AA-BB-TWO", "AA-BB-ONE", "AA-BB-SOON"]);
  assert.equal(defaultCity(CITIES, "AA-BB-SOON"), "AA-BB-SOON");
  assert.equal(defaultCity(CITIES, "QQ-RR-SSS"), "");
  assert.equal(defaultCity(CITIES, null), "");
});

test("the consent sentence keeps each language's word order around its links", () => {
  assert.deepEqual(splitLinks("I agree to the {terms} and the {privacy}.", ["terms", "privacy"]),
    [{ text: "I agree to the " }, { link: "terms" }, { text: " and the " }, { link: "privacy" }, { text: "." }]);
  assert.deepEqual(splitLinks("मैं {terms} और {privacy} से सहमत हूँ।", ["terms", "privacy"]).filter((p) => "link" in p), [{ link: "terms" }, { link: "privacy" }]);
});

test("who sees what: a visitor, a customer, a kitchen partner, a delivery partner, an admin", () => {
  assert.equal(applicationState(null), "visitor");
  assert.equal(applicationState("customer"), "customer");
  assert.equal(applicationState("restaurant_owner"), "kitchen");
  assert.equal(applicationState("driver"), "delivery");
  assert.equal(applicationState("admin"), "other");
});
