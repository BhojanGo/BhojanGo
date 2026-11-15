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

module.exports = { LANGUAGES, DEFAULT_LANGUAGE, languageOf, languagesFor, pickLanguage, formatLocale, createTranslator, pluralSelector };
