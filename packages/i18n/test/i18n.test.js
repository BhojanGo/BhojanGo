// node --test: language choice and the translator.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { LANGUAGES, languagesFor, pickLanguage, formatLocale, createTranslator } = require("..");

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
