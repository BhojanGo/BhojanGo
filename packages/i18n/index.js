// Languages for the website and the apps (web v2).
//
// A country's languages come from Markets (countries.locales, e.g. India:
// en-IN, hi-IN, te-IN, ta-IN, kn-IN, mr-IN, bn-IN; United States: en-US, es-US).
// Messages are kept per language ("hi"), not per locale ("hi-IN"): the words are
// the same; money, numbers and dates follow the country (see `formatLocale`), so
// changing the language never changes a price.

/** Every language we have messages for: its own name, and how it is written. */
const LANGUAGES = {
  en: { name: "English", dir: "ltr" },
  hi: { name: "हिन्दी", dir: "ltr" },
  te: { name: "తెలుగు", dir: "ltr" },
  ta: { name: "தமிழ்", dir: "ltr" },
  kn: { name: "ಕನ್ನಡ", dir: "ltr" },
  mr: { name: "मराठी", dir: "ltr" },
  bn: { name: "বাংলা", dir: "ltr" },
  es: { name: "Español", dir: "ltr" },
};

const DEFAULT_LANGUAGE = "en";

/** "hi-IN" -> "hi". */
function languageOf(locale) {
  return String(locale || "").split(/[-_]/)[0].toLowerCase();
}

/** The languages a country offers (its Markets locales), in Markets' order, de-duplicated. */
function languagesFor(locales) {
  const out = [];
  for (const l of locales || []) {
    const lang = languageOf(l);
    if (LANGUAGES[lang] && !out.includes(lang)) out.push(lang);
  }
  return out.length ? out : [DEFAULT_LANGUAGE];
}

/**
 * The language to show: the visitor's choice if the country offers it, else the
 * browser's first offered language (Accept-Language), else English if offered,
 * else the country's first.
 */
function pickLanguage({ chosen, acceptLanguage, locales }) {
  const offered = languagesFor(locales);
  if (chosen && offered.includes(languageOf(chosen))) return languageOf(chosen);
  for (const part of String(acceptLanguage || "").split(",")) {
    const lang = languageOf(part.split(";")[0].trim());
    if (offered.includes(lang)) return lang;
  }
  return offered.includes(DEFAULT_LANGUAGE) ? DEFAULT_LANGUAGE : offered[0];
}

/**
 * The header's language pill list (R6): the country's Markets locales, in Markets'
 * order, each language named in its own script: [{code: "te", name: "తెలుగు"}].
 */
function languageList(locales) {
  return languagesFor(locales).map((code) => ({ code, name: LANGUAGES[code].name }));
}

/**
 * The language to show (R6, website and apps): the visitor's remembered choice if
 * the country offers it, else English (if offered), else the country's first. The
 * browser's or phone's language never picks it: English until the visitor taps one.
 */
function chooseLanguage(chosen, locales) {
  const offered = languagesFor(locales);
  const lang = chosen ? languageOf(chosen) : "";
  if (lang && offered.includes(lang)) return lang;
  return offered.includes(DEFAULT_LANGUAGE) ? DEFAULT_LANGUAGE : offered[0];
}

/** "en-US,en;q=0.9" or ["es-US", "en"] -> ["en-US", "en"] (language tags, best first). */
function browserTags(browser) {
  const list = Array.isArray(browser) ? browser : String(browser || "").split(",");
  return list.map((p) => String(p).split(";")[0].trim()).filter(Boolean);
}

/**
 * Which country the visitor is in (R6), from the strongest evidence that names a
 * country we have (`countries`: Markets' [{code, locales}], directory order):
 *   address  the delivery address (saved, signed-in default, or the area they set)
 *   chosen   a city they picked ("Change city"), as its country code
 *   page     the country of the page itself (a city or kitchen page), website only
 *   ip       the IP hint (GET /markets/hint -> country)
 *   browser  the browser's / phone's locale region (Accept-Language, navigator.languages)
 *   default  a country offering the browser's (non-English) language, else the first
 * Returns {code, source}; {code: null, source: "none"} only when there are no countries.
 */
function detectCountry(evidence, countries) {
  const list = countries || [];
  const byCode = (code) => (code ? list.find((c) => c.code === String(code).toUpperCase()) || null : null);
  const e = evidence || {};
  for (const source of ["address", "chosen", "page", "ip"]) {
    const hit = byCode(e[source]);
    if (hit) return { code: hit.code, source };
  }
  const tags = browserTags(e.browser);
  for (const tag of tags) {
    const hit = byCode(tag.split(/[-_]/)[1]);
    if (hit) return { code: hit.code, source: "browser" };
  }
  if (!list.length) return { code: null, source: "none" };
  const lang = languageOf(tags[0]);
  const speaks = lang && lang !== DEFAULT_LANGUAGE ? list.find((c) => languagesFor(c.locales).includes(lang)) : null;
  return { code: (speaks || list[0]).code, source: "default" };
}

/** Money, numbers and dates follow the country (its first Markets locale), never the language. */
function formatLocale(locales) {
  return (locales && locales[0]) || "en-US";
}

function lookup(messages, key) {
  let node = messages;
  for (const part of key.split(".")) {
    if (node == null || typeof node !== "object") return undefined;
    node = node[part];
  }
  return node;
}

function interpolate(text, vars) {
  return text.replace(/\{(\w+)\}/g, (m, name) => (vars && vars[name] != null ? String(vars[name]) : m));
}

/**
 * The plural category of a count ("one" | "other" | ...). Intl.PluralRules where
 * the engine has it; React Native's Hermes may not, so a small fallback covers our
 * languages: English, Spanish, Telugu, Tamil, Marathi: one for exactly 1; Hindi,
 * Bengali, Kannada: one for 0 and 1 (CLDR).
 */
function pluralSelector(language) {
  try {
    if (typeof Intl !== "undefined" && typeof Intl.PluralRules === "function") {
      const rules = new Intl.PluralRules(language);
      return (n) => rules.select(n);
    }
  } catch {
    // fall through to the built-in rules
  }
  const zeroIsOne = ["hi", "bn", "kn"].includes(languageOf(language));
  return (n) => (n === 1 || (zeroIsOne && n === 0) ? "one" : "other");
}

/**
 * t("home.greeting", {name}) from `messages` (the language's), falling back to
 * `fallback` (English) key by key, then to the key itself (visible, never blank).
 * A message can be plural: {"one": "{count} kitchen", "other": "{count} kitchens"},
 * chosen by vars.count with the language's plural rules.
 */
function createTranslator(language, messages, fallback) {
  const select = pluralSelector(language);
  return function t(key, vars) {
    let msg = lookup(messages, key);
    if (msg == null || msg === "") msg = lookup(fallback, key);
    if (msg == null) return key;
    if (typeof msg === "object") {
      const count = vars && typeof vars.count === "number" ? vars.count : 0;
      msg = msg[select(count)] ?? msg.other ?? key;
    }
    return interpolate(String(msg), vars);
  };
}

module.exports = {
  LANGUAGES, DEFAULT_LANGUAGE, languageOf, languagesFor, languageList, pickLanguage, chooseLanguage, detectCountry,
  formatLocale, createTranslator, pluralSelector,
};
