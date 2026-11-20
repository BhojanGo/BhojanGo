// node --test: the current country, and money, numbers, distances and dates by
// the country's locale (pure logic, no React Native). The countries here are
// test fixtures shaped like GET /api/v1/markets/directory.
import assert from "node:assert/strict";
import test from "node:test";

import { convertDistance, countryForCurrency, e164, filterCities, findCity, formatDate, formatMoney, formatNumber, formatTime,
  liveCityNames, localeForCurrency, partnerCountry, partnerLanguage, regionOf, resolveCountry, type MarketCountry } from "../src/locale.ts";

function country(code: string, currency: string, locales: string[], unit: string, phone: string, cities: string[] = []): MarketCountry {
  return {
    code, slug: code.toLowerCase(), name: `Country ${code}`, currency, locales, timezone: "UTC", distance_unit: unit,
    phone_code: phone, tax_regime: "x", payment_providers: [], payment_methods: ["card"], live: cities.length, soon: 0,
    regions: [{ code: `${code}-R`, name: "Region", cities: cities.map((c, i) => ({
      code: `${code}-R-${c}`, name: c, slug: c.toLowerCase(), path: `/${code}/${c}`, status: i === 0 ? "live" : "soon",
      beta: false, restaurants: 0, waiting: 0, lat: 0, lng: 0 })) }],
  };
}
const AA = country("AA", "INR", ["en-IN", "hi-IN", "te-IN"], "km", "+91", ["Alpha", "Beta"]);
const BB = country("BB", "USD", ["en-US", "es-US"], "mi", "+1", ["Gamma"]);
const ALL = [AA, BB];

test("regionOf reads a locale's region", () => {
  assert.equal(regionOf("en-US"), "US");
  assert.equal(regionOf("hi_IN"), "IN");
  assert.equal(regionOf("zh-Hans-CN"), "CN");
  assert.equal(regionOf("en"), null);
  assert.equal(regionOf(null), null);
});

test("country: address, then the IP hint, then the device's region, then the first live one", () => {
  assert.deepEqual(resolveCountry({ countries: ALL, addressCountry: "BB", ipCountry: "AA", deviceLocale: "en-AA" }), { country: BB, source: "address" });
  assert.deepEqual(resolveCountry({ countries: ALL, addressCountry: "ZZ", ipCountry: "aa", deviceLocale: "en-BB" }), { country: AA, source: "ip" });
  assert.deepEqual(resolveCountry({ countries: ALL, ipCountry: "ZZ", deviceLocale: "es-BB" }), { country: BB, source: "browser" });
  assert.deepEqual(resolveCountry({ countries: ALL, deviceLocale: "fr-FR" }), { country: AA, source: "default" });
  assert.deepEqual(resolveCountry({ countries: ALL, deviceLocale: "es-FR" }), { country: BB, source: "default" }); // speaks the phone's language
  assert.deepEqual(resolveCountry({ countries: [], addressCountry: "AA" }), { country: null, source: "none" });
});

// R20: BhojanGo Kitchen and BhojanGo Delivery offer the partner's own country's languages.
const SOON = country("CC", "EUR", ["es-CC"], "km", "+3"); // no live city yet
const IN_ORDER = [SOON, AA, BB];

test("partner apps: the account's country, else the phone's, else the first live one; never the IP's", () => {
  assert.deepEqual(partnerCountry({ countries: IN_ORDER, accountCountry: "BB", deviceLocale: "en-AA" }), { country: BB, source: "address" });
  assert.deepEqual(partnerCountry({ countries: IN_ORDER, accountCountry: "bb" }), { country: BB, source: "address" });
  // signed out: the phone's region when Markets has it
  assert.deepEqual(partnerCountry({ countries: IN_ORDER, accountCountry: null, deviceLocale: "hi-AA" }), { country: AA, source: "browser" });
  assert.deepEqual(partnerCountry({ countries: IN_ORDER, deviceLocale: "es_CC" }), { country: SOON, source: "browser" });
  // an account country Markets doesn't list, or a phone elsewhere: the first live country (not Markets' first)
  assert.deepEqual(partnerCountry({ countries: IN_ORDER, accountCountry: "ZZ", deviceLocale: "fr-FR" }), { country: AA, source: "default" });
  assert.deepEqual(partnerCountry({ countries: IN_ORDER, deviceLocale: "es-FR" }), { country: AA, source: "default" }); // no language guess
  assert.deepEqual(partnerCountry({ countries: [SOON] }), { country: SOON, source: "default" });
  assert.deepEqual(partnerCountry({ countries: [], accountCountry: "AA" }), { country: null, source: "none" });
});

test("partner apps: the country's languages in Markets order; a saved one it doesn't offer falls back to its first", () => {
  assert.equal(partnerLanguage("te", AA.locales), "te");
  assert.equal(partnerLanguage("es", BB.locales), "es");
  assert.equal(partnerLanguage("es", AA.locales), "en"); // saved Spanish, an Indian kitchen: the country's first
  assert.equal(partnerLanguage("hi", BB.locales), "en");
  assert.equal(partnerLanguage(null, SOON.locales), "es"); // nothing saved: the country's first, even when not English
  assert.equal(partnerLanguage("te", SOON.locales), "es");
  assert.equal(partnerLanguage("te", null), "te"); // Markets not loaded yet: the saved one
  assert.equal(partnerLanguage(null, null), "en");
});

test("money follows the country's locale and the currency, never the language", () => {
  assert.equal(formatMoney(124050, "INR", "en-IN"), "₹1,24,050.00");
  assert.equal(formatMoney("1240.5", "USD", "en-US"), "$1,240.50");
  assert.equal(formatMoney(-50, "INR", "en-IN"), "−₹50.00");
  assert.equal(formatMoney(300, "INR", "en-IN"), "₹300.00"); // one format everywhere (R12)
  assert.equal(formatMoney(29, "USD", "en-US"), "$29.00");
  assert.equal(formatMoney(null, "USD", "en-US"), "$0.00");
});

test("an amount in another country's currency reads the way it does there", () => {
  assert.equal(localeForCurrency("INR", AA, ALL), "en-IN");
  assert.equal(localeForCurrency("USD", AA, ALL), "en-US");
  assert.equal(localeForCurrency(null, BB, ALL), "en-US");
  assert.equal(localeForCurrency("EUR", null, ALL), undefined);
  assert.equal(countryForCurrency(ALL, "USD"), BB);
});

test("numbers, distances, dates", () => {
  assert.equal(formatNumber(124050.55, "en-IN"), "1,24,050.6");
  assert.deepEqual(convertDistance(10, "km"), { value: 10, unit: "km" });
  assert.equal(convertDistance(1.609344, "mi").unit, "mi");
  assert.ok(Math.abs(convertDistance(1.609344, "mi").value - 1) < 1e-9);
  assert.equal(formatDate("2026-11-14", "en-IN"), "14 Nov");
  assert.equal(formatDate("2026-11-14", "en-US"), "Nov 14");
  assert.equal(formatTime("2026-11-14T19:05:00Z", "en-US", { timeZone: "UTC" }), "7:05 pm");
});

test("cities and phone numbers from Markets data", () => {
  assert.equal(findCity(ALL, "BB-R-Gamma")?.country, BB);
  assert.equal(findCity(ALL, "nope"), null);
  assert.deepEqual(liveCityNames(ALL), ["Alpha", "Gamma"]);
  assert.equal(e164("+91", "098480 21234"), "+919848021234");
  assert.equal(e164("+1", "+1 (208) 555-0199"), "+12085550199");
});

test("Change city search: by city or state, accents and case ignored; empty states and countries dropped", () => {
  assert.deepEqual(filterCities(ALL, "").map((k) => k.code), ["AA", "BB"]);
  assert.deepEqual(filterCities(ALL, "  ALPH ").flatMap((k) => k.regions.flatMap((r) => r.cities.map((c) => c.name))), ["Alpha"]);
  assert.deepEqual(filterCities(ALL, "regi").map((k) => k.regions[0]!.cities.length), [2, 1]); // a state's name keeps all its cities
  const accented = { ...BB, regions: [{ ...BB.regions[0]!, cities: [{ ...BB.regions[0]!.cities[0]!, name: "São Paulo" }] }] };
  assert.equal(filterCities([accented], "sao").length, 1);
  assert.deepEqual(filterCities(ALL, "zzz"), []);
});
