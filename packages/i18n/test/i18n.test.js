// node --test: language choice and the translator.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { LANGUAGES, languagesFor, languageList, pickLanguage, chooseLanguage, detectCountry, formatLocale, createTranslator } = require("..");

const INDIA = ["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN", "bn-IN"];
const US = ["en-US", "es-US"];

test("a country's languages come from its Markets locales", () => {
  assert.deepEqual(languagesFor(INDIA), ["en", "hi", "te", "ta", "kn", "mr", "bn"]);
  assert.deepEqual(languagesFor(US), ["en", "es"]);
  assert.deepEqual(languagesFor(["xx-YY"]), ["en"]);
});

test("choice, then browser, then English", () => {
  assert.equal(pickLanguage({ chosen: "te", locales: INDIA }), "te");
  assert.equal(pickLanguage({ chosen: "te", acceptLanguage: "es-ES,es;q=0.9", locales: US }), "es"); // te isn't offered in the US
  assert.equal(pickLanguage({ acceptLanguage: "fr-FR, hi;q=0.8", locales: INDIA }), "hi");
  assert.equal(pickLanguage({ locales: US }), "en");
});

test("the language pill's list: the country's languages, each in its own script, in Markets order", () => {
  assert.deepEqual(languageList(INDIA).map((l) => l.code), ["en", "hi", "te", "ta", "kn", "mr", "bn"]);
  assert.deepEqual(languageList(INDIA).map((l) => l.name), ["English", "हिन्दी", "తెలుగు", "தமிழ்", "ಕನ್ನಡ", "मराठी", "বাংলা"]);
  assert.deepEqual(languageList(US), [{ code: "en", name: "English" }, { code: "es", name: "Español" }]);
  assert.deepEqual(languageList(null), [{ code: "en", name: "English" }]);
});

test("remembered language: kept when the country offers it, else English; the browser never decides", () => {
  assert.equal(chooseLanguage("te", INDIA), "te");
  assert.equal(chooseLanguage("te-IN", INDIA), "te");
  assert.equal(chooseLanguage("te", US), "en"); // moved to a US city: Telugu isn't offered there
  assert.equal(chooseLanguage("es", US), "es");
  assert.equal(chooseLanguage(null, US), "en");
  assert.equal(chooseLanguage("", INDIA), "en");
  assert.equal(chooseLanguage("hi", ["hi-IN"]), "hi");
  assert.equal(chooseLanguage(null, ["es-MX"]), "es"); // no English offered: the country's first
});

test("country: address, then a chosen city, then the page, then IP, then the browser, then a default", () => {
  const C = [{ code: "IN", locales: INDIA }, { code: "US", locales: US }];
  assert.deepEqual(detectCountry({ address: "us", chosen: "IN", ip: "IN", browser: "en-IN" }, C), { code: "US", source: "address" });
  assert.deepEqual(detectCountry({ address: "FR", chosen: "US", ip: "IN" }, C), { code: "US", source: "chosen" });
  assert.deepEqual(detectCountry({ page: "IN", ip: "US" }, C), { code: "IN", source: "page" });
  assert.deepEqual(detectCountry({ ip: "US", browser: "en-IN" }, C), { code: "US", source: "ip" });
  assert.deepEqual(detectCountry({ ip: "DE", browser: "de-DE, en-US;q=0.8" }, C), { code: "US", source: "browser" });
  assert.deepEqual(detectCountry({ browser: ["es", "en-IN"] }, C), { code: "IN", source: "browser" });
  assert.deepEqual(detectCountry({ browser: "es" }, C), { code: "US", source: "default" }); // a country that speaks it
  assert.deepEqual(detectCountry({ browser: "en" }, C), { code: "IN", source: "default" }); // the directory's first
  assert.deepEqual(detectCountry({}, C), { code: "IN", source: "default" });
  assert.deepEqual(detectCountry({ address: "IN" }, []), { code: null, source: "none" });
});

test("money and dates follow the country, not the language", () => {
  assert.equal(formatLocale(INDIA), "en-IN");
  assert.equal(formatLocale(US), "en-US");
});

test("translator: fallback, variables, plurals", () => {
  const en = { home: { greet: "Hello, {name}", kitchens: { one: "{count} kitchen", other: "{count} kitchens" }, only_en: "English only" } };
  const hi = { home: { greet: "नमस्ते, {name}", kitchens: { one: "{count} रसोई", other: "{count} रसोइयाँ" } } };
  const t = createTranslator("hi", hi, en);
  assert.equal(t("home.greet", { name: "Srini" }), "नमस्ते, Srini");
  assert.equal(t("home.kitchens", { count: 1 }), "1 रसोई");
  assert.equal(t("home.kitchens", { count: 42 }), "42 रसोइयाँ");
  assert.equal(t("home.only_en"), "English only");
  assert.equal(t("home.missing"), "home.missing");
});

test("every language has every English key (machine translations are listed in REVIEW.md)", () => {
  const dir = path.join(__dirname, "..", "messages");
  const keys = (o, p = "") => Object.entries(o).flatMap(([k, v]) =>
    v && typeof v === "object" && !("other" in v) ? keys(v, `${p}${k}.`) : [`${p}${k}`]);
  const en = keys(JSON.parse(fs.readFileSync(path.join(dir, "en.json"), "utf8")));
  for (const lang of Object.keys(LANGUAGES)) {
    const other = new Set(keys(JSON.parse(fs.readFileSync(path.join(dir, `${lang}.json`), "utf8"))));
    const missing = en.filter((k) => !other.has(k));
    assert.deepEqual(missing, [], `${lang}.json is missing ${missing.length} keys`);
  }
});

test("plurals work without Intl.PluralRules (React Native's Hermes may not have it)", () => {
  const saved = Intl.PluralRules;
  try {
    Intl.PluralRules = undefined;
    const en = { k: { one: "{count} kitchen", other: "{count} kitchens" } };
    assert.equal(createTranslator("en", en, en)("k", { count: 1 }), "1 kitchen");
    assert.equal(createTranslator("en", en, en)("k", { count: 0 }), "0 kitchens");
    assert.equal(createTranslator("hi", en, en)("k", { count: 0 }), "0 kitchen"); // Hindi: 0 and 1 are "one"
    assert.equal(createTranslator("es", en, en)("k", { count: 2 }), "2 kitchens");
  } finally {
    Intl.PluralRules = saved;
  }
});

test("the apps' bundle has every language, and the apps' keys exist", () => {
  const all = require("../all-messages");
  assert.deepEqual(Object.keys(all).sort(), Object.keys(LANGUAGES).sort());
  for (const lang of Object.keys(LANGUAGES)) {
    const t = createTranslator(lang, all[lang], all.en);
    assert.notEqual(t("app.test_banner"), "app.test_banner", lang);
    assert.match(t("app.units.km", { value: "2.1" }), /2\.1/, lang);
  }
});
