// Languages and the current country for the Expo apps (round 4).
//
//   <I18nProvider>            in each app's root layout (around the Stack)
//   const { t, money, distance, date, time } = useI18n();
//   const { country, countries, setAddressCountry } = useCountry();
//   <LanguagePill />          the header's globe + "EN" pill: the country's languages (Markets locales)
//   <LanguagePicker />        the same list as radio rows (account/settings screens)
//
// Messages are @bhojango/i18n's (the website's, plus "app", "rider" and "partner"
// keys for the apps). The language is the one remembered on this device when the
// country offers it, else English (chooseLanguage). There is no country selector:
// the country is detected (detectCountry: the delivery address's or the account's,
// else the IP hint, else the phone's region). Money, numbers and dates follow the
// country's first Markets locale, never the language. The language is kept on the
// device in SecureStore.
import { chooseLanguage, createTranslator, formatLocale as countryLocale, LANGUAGES, languageList, languagesFor,
  opensLabel, wallClock, type Language, type Translate } from "@bhojango/i18n";
import MESSAGES from "@bhojango/i18n/all-messages";
import { unwrap } from "@bhojango/api-client";
import * as SecureStore from "expo-secure-store";
import { useEffect, useMemo, type ReactNode } from "react";
import { create } from "zustand";

import { convertDistance, deviceLocale, formatDate, formatMoney, formatNumber, formatTime, localeForCurrency,
  partnerCountry, partnerLanguage, resolveCountry, type CountrySource, type MarketCountry } from "./locale";
import { api } from "./session";
import { loadScriptFonts } from "./ui/fonts";
import { scriptFor, setTypeScript, type Script } from "./ui/type";

const LANGUAGE_KEY = "bg.language";
const COUNTRY_KEY = "bg.country"; // round 4's country choice: no longer used (cleared once at start)

/**
 * Whose rule picks the country and language (R20):
 *   "customer"  the website's: the delivery address, the IP hint, the phone's region, ...; English
 *               when the remembered language isn't offered (resolveCountry, chooseLanguage)
 *   "partner"   BhojanGo Kitchen and Delivery: the account's country, else the phone's region,
 *               else the first live country; the country's first language when the remembered one
 *               isn't offered (partnerCountry, partnerLanguage)
 */
export type LocaleRule = "customer" | "partner";

interface LocaleState {
  /** Stored choices are loaded (the provider renders its children from then on). */
  ready: boolean;
  rule: LocaleRule;
  /** Markets countries (GET /api/v1/markets/directory); empty until loaded or when offline. */
  countries: MarketCountry[];
  directoryError: boolean;
  /** What the directory load threw (LoadError words it: no connection, too slow, ...). */
  directoryFailure: unknown;
  addressCountry: string | null;
  /** The country GET /markets/hint reads from this phone's IP (null when unknown or GeoIP is off). */
  ipCountry: string | null;
  chosenLanguage: string | null;
  device: string | null;
  /** The script whose faces the type tokens use (the language's, once its Noto Sans faces are loaded). */
  script: Script;
  setScript: (script: Script) => void;
  init: (rule?: LocaleRule) => Promise<void>;
  loadDirectory: () => Promise<void>;
  loadHint: () => Promise<void>;
  setLanguage: (language: string) => Promise<void>;
  setAddressCountry: (code: string | null) => void;
}

/** The store behind useI18n/useCountry (read it outside React with useLocaleStore.getState()). */
export const useLocaleStore = create<LocaleState>()((set, get) => ({
  ready: false,
  rule: "customer",
  countries: [],
  directoryError: false,
  directoryFailure: null,
  addressCountry: null,
  ipCountry: null,
  chosenLanguage: null,
  device: deviceLocale(),
  script: "latin",
  setScript: (script) => {
    setTypeScript(script); // before the re-render, so every `type` token read in it has the new face
    set({ script });
  },

  init: async (rule = "customer") => {
    if (get().ready) return;
    const language = await SecureStore.getItemAsync(LANGUAGE_KEY).catch(() => null);
    set({ ready: true, rule, chosenLanguage: language });
    void SecureStore.deleteItemAsync(COUNTRY_KEY).catch(() => undefined);
    void get().loadDirectory();
    void get().loadHint();
  },

  loadHint: async () => {
    if (get().rule === "partner") return; // partners: the account's country or the phone's, never the IP's
    try {
      const h = unwrap(await api.core.GET("/api/v1/markets/hint"));
      set({ ipCountry: h.country ?? null });
    } catch {
      // a hint only: without it the phone's region (or the first live country) decides
    }
  },

  loadDirectory: async () => {
    try {
      const d = unwrap(await api.core.GET("/api/v1/markets/directory"));
      set({ countries: d.countries, directoryError: false, directoryFailure: null });
      if (!get().ipCountry) void get().loadHint(); // the hint failed with it when offline at start
    } catch (e) {
      set({ directoryError: true, directoryFailure: e });
    }
  },

  setLanguage: async (language) => {
    set({ chosenLanguage: language });
    await SecureStore.setItemAsync(LANGUAGE_KEY, language).catch(() => undefined);
  },

  setAddressCountry: (code) => set({ addressCountry: code }),
}));

/**
 * Loads the stored language and country, then Markets' countries. Renders nothing
 * until the stored choices are read (a few milliseconds, behind the splash screen),
 * so the first screen is already in the person's language.
 */
export function I18nProvider({ children, rule = "customer" }: { children: ReactNode; rule?: LocaleRule }) {
  const ready = useLocaleStore((s) => s.ready);
  const init = useLocaleStore((s) => s.init);
  useEffect(() => {
    void init(rule);
  }, [init, rule]);
  // The type tokens follow the language's script: Noto Sans for Devanagari, Telugu, ...
  // (React Native draws a Text in one face). Until the faces load, the brand face.
  const { language } = useI18n();
  const setScript = useLocaleStore((s) => s.setScript);
  const script = scriptFor(language);
  useEffect(() => {
    let live = true;
    if (script === "latin") setScript("latin");
    else void loadScriptFonts(script).then(() => live && setScript(script), () => live && setScript("latin"));
    return () => {
      live = false;
    };
  }, [script, setScript]);
  return ready ? <>{children}</> : null;
}

export interface CountryContext {
  /** The current country (Markets data): detected, else the first live one; null only until Markets loads. */
  country: MarketCountry | null;
  source: CountrySource;
  /** Every Markets country with live or coming-soon cities. */
  countries: MarketCountry[];
  /** True while Markets' countries haven't loaded (or failed: see `reload`). */
  loading: boolean;
  error: boolean;
  /** What the load threw, for <LoadError error={failure} onRetry={reload} />. */
  failure: unknown;
  reload: () => Promise<void>;
  /** The country known for sure: the delivery address's or the account's (strongest source; not stored). See useKnownCountry. */
  setAddressCountry: (code: string | null) => void;
}

/** The current country: the address's (or account's), then the IP hint, then the phone's region, then the first live one. */
export function useCountry(): CountryContext {
  const s = useLocaleStore();
  return useMemo(() => {
    const { country, source } = s.rule === "partner"
      ? partnerCountry({ countries: s.countries, accountCountry: s.addressCountry, deviceLocale: s.device })
      : resolveCountry({ countries: s.countries, addressCountry: s.addressCountry, ipCountry: s.ipCountry, deviceLocale: s.device });
    return {
      country, source, countries: s.countries, loading: !s.countries.length && !s.directoryError, error: s.directoryError,
      failure: s.directoryFailure, reload: s.loadDirectory, setAddressCountry: s.setAddressCountry,
    };
  }, [s.rule, s.countries, s.addressCountry, s.ipCountry, s.device, s.directoryError, s.directoryFailure, s.loadDirectory, s.setAddressCountry]);
}

export interface I18n {
  /** t("app.test_banner"), t("rider.trips", {count: 3}): the language's message, else English, else the key. */
  t: Translate;
  /** The language shown ("hi"). */
  language: Language;
  /** The script the type tokens draw in now ("devanagari" once its Noto Sans faces are loaded). */
  script: Script;
  /** The languages the current country offers, in Markets' order (what LanguagePill and LanguagePicker list). */
  languages: Language[];
  /** The same with each language's own name (languageList): [{code: "te", name: "తెలుగు"}]. */
  options: { code: Language; name: string }[];
  setLanguage: (language: Language) => Promise<void>;
  /** The country's first Markets locale; undefined (the phone's) until a country is known. */
  formatLocale: string | undefined;
  /** money(250, order.currency) in the country's format, always two decimals (29.00). No currency: the country's (Markets). */
  money: (amount: number | string | null | undefined, currency?: string | null) => string;
  /** number(1234.5) -> "1,234.5" (country grouping), `digits` decimals at most (1). */
  number: (n: number, digits?: number) => string;
  /** distance(2.14): kilometres in, the country's unit out (or `unit` as the API sends it), one decimal, translated unit. */
  distance: (km: number | null | undefined, unit?: string | null) => string;
  /** date("2026-11-14") -> "14 Nov"; Intl options (weekday, month: "long", timeZone, ...). */
  date: (iso: string | number | Date, opts?: Intl.DateTimeFormatOptions) => string;
  /** time(iso) -> "7:05 pm"; Intl options (timeZone: the order's city, ...). */
  time: (iso: string | number | Date, opts?: Intl.DateTimeFormatOptions) => string;
  /** R27: opens(kitchen.opens_at, zone) -> "Closed · opens 6:30 am" / "Closed · opens Sat 6:30 am" (the weekday in the
   *  app's language, the time on the kitchen's city clock); other wording with `keys`. Null without a time. */
  opens: (iso: string | null | undefined, timeZone?: string | null, keys?: { today: string; day: string }) => string | null;
  /** wall("08:00") -> "8:00 am": a wall-clock time from the API (a city's delivery hours) in the country's format. */
  wall: (hhmm: string | null | undefined) => string | null;
}

/** Translation and country-aware formatting for a screen. */
export function useI18n(): I18n {
  const { country, countries } = useCountry();
  const chosen = useLocaleStore((s) => s.chosenLanguage);
  const setLanguage = useLocaleStore((s) => s.setLanguage);
  const rule = useLocaleStore((s) => s.rule);
  // Screens re-render when the script's faces arrive (the `type` tokens read it at render).
  const script = useLocaleStore((s) => s.script);
  return useMemo(() => {
    // Until Markets' countries load (a moment, or offline), the remembered language alone.
    const locales = country?.locales ?? (chosen ? [chosen] : null);
    const language = rule === "partner" ? partnerLanguage(chosen, locales) : chooseLanguage(chosen, locales);
    const languages = languagesFor(locales);
    const options = languageList(locales);
    const loc = country ? countryLocale(country.locales) : undefined;
    const t = createTranslator(language, MESSAGES[language], MESSAGES.en);
    return {
      t, language, languages, options, setLanguage, formatLocale: loc, script,
      money: (amount, currency) => {
        const cur = currency || country?.currency;
        if (!cur) return formatNumber(Number(amount ?? 0), loc, 2);
        return formatMoney(amount, cur, localeForCurrency(cur, country, countries));
      },
      number: (n, digits = 1) => formatNumber(n, loc, digits),
      distance: (km, unit) => {
        if (km == null || !Number.isFinite(km)) return "";
        const d = convertDistance(km, unit ?? country?.distance_unit);
        return t(`app.units.${d.unit}`, { value: formatNumber(d.value, loc, 1) });
      },
      date: (iso, opts) => formatDate(iso, loc, opts),
      time: (iso, opts) => formatTime(iso, loc, opts),
      opens: (iso, timeZone, keys) => opensLabel(t, iso, { timeZone, formatLocale: loc, language }, keys),
      wall: (hhmm) => wallClock(hhmm, loc),
    };
  }, [country, countries, chosen, setLanguage, script, rule]);
}

/**
 * Tell the locale store the country we know for sure: the delivery address's
 * (customer app) or the signed-in account's (the delivery partner's; the kitchen's in
 * BhojanGo Kitchen). null clears it (signed out).
 *   useKnownCountry(useSession((s) => s.user?.country));
 */
export function useKnownCountry(code: string | null | undefined) {
  const set = useLocaleStore((s) => s.setAddressCountry);
  useEffect(() => {
    set(code || null);
  }, [code, set]);
}

/** Every language we have messages for, with its own name ("हिन्दी"), for pickers. */
export { LANGUAGES };
export type { Language, Translate };
