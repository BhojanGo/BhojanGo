// Languages and the current country for the Expo apps (round 4).
//
//   <I18nProvider>            in each app's root layout (around the Stack)
//   const { t, money, distance, date, time } = useI18n();
//   const { country, countries, chooseCountry, setAddressCountry } = useCountry();
//   <LanguagePicker />        offers exactly the country's languages (Markets locales)
//
// Messages are @bhojango/i18n's (the website's, plus "app", "rider" and "partner"
// keys for the apps). The language is the person's choice when the country offers
// it, else the phone's language when offered, else English (pickLanguage). Money,
// numbers and dates follow the country's first Markets locale, never the language.
// The choices (language, country) are kept on the device in SecureStore.
import { createTranslator, formatLocale as countryLocale, LANGUAGES, languagesFor, pickLanguage,
  type Language, type Translate } from "@bhojango/i18n";
import MESSAGES from "@bhojango/i18n/all-messages";
import { unwrap } from "@bhojango/api-client";
import * as SecureStore from "expo-secure-store";
import { useEffect, useMemo, type ReactNode } from "react";
import { create } from "zustand";

import { convertDistance, deviceLocale, formatDate, formatMoney, formatNumber, formatTime, localeForCurrency,
  resolveCountry, type CountrySource, type MarketCountry } from "./locale";
import { api } from "./session";
import { loadScriptFonts } from "./ui/fonts";
import { scriptFor, setTypeScript, type Script } from "./ui/type";

const LANGUAGE_KEY = "bg.language";
const COUNTRY_KEY = "bg.country";

interface LocaleState {
  /** Stored choices are loaded (the provider renders its children from then on). */
  ready: boolean;
  /** Markets countries (GET /api/v1/markets/directory); empty until loaded or when offline. */
  countries: MarketCountry[];
  directoryError: boolean;
  addressCountry: string | null;
  chosenCountry: string | null;
  chosenLanguage: string | null;
  device: string | null;
  /** The script whose faces the type tokens use (the language's, once its Noto Sans faces are loaded). */
  script: Script;
  setScript: (script: Script) => void;
  init: () => Promise<void>;
  loadDirectory: () => Promise<void>;
  setLanguage: (language: string) => Promise<void>;
  chooseCountry: (code: string | null) => Promise<void>;
  setAddressCountry: (code: string | null) => void;
}

/** The store behind useI18n/useCountry (read it outside React with useLocaleStore.getState()). */
export const useLocaleStore = create<LocaleState>()((set, get) => ({
  ready: false,
  countries: [],
  directoryError: false,
  addressCountry: null,
  chosenCountry: null,
  chosenLanguage: null,
  device: deviceLocale(),
  script: "latin",
  setScript: (script) => {
    setTypeScript(script); // before the re-render, so every `type` token read in it has the new face
    set({ script });
  },

  init: async () => {
    if (get().ready) return;
    const [language, country] = await Promise.all([
      SecureStore.getItemAsync(LANGUAGE_KEY).catch(() => null),
      SecureStore.getItemAsync(COUNTRY_KEY).catch(() => null),
    ]);
    set({ ready: true, chosenLanguage: language, chosenCountry: country });
    void get().loadDirectory();
  },

  loadDirectory: async () => {
    try {
      const d = unwrap(await api.core.GET("/api/v1/markets/directory"));
      set({ countries: d.countries, directoryError: false });
    } catch {
      set({ directoryError: true });
    }
  },

  setLanguage: async (language) => {
    set({ chosenLanguage: language });
    await SecureStore.setItemAsync(LANGUAGE_KEY, language).catch(() => undefined);
  },

  chooseCountry: async (code) => {
    set({ chosenCountry: code });
    if (code) await SecureStore.setItemAsync(COUNTRY_KEY, code).catch(() => undefined);
    else await SecureStore.deleteItemAsync(COUNTRY_KEY).catch(() => undefined);
  },

  setAddressCountry: (code) => set({ addressCountry: code }),
}));

/**
 * Loads the stored language and country, then Markets' countries. Renders nothing
 * until the stored choices are read (a few milliseconds, behind the splash screen),
 * so the first screen is already in the person's language.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const ready = useLocaleStore((s) => s.ready);
  const init = useLocaleStore((s) => s.init);
  useEffect(() => {
    void init();
  }, [init]);
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
  /** The current country (Markets data), or null when unknown: ask with a country choice. */
  country: MarketCountry | null;
  source: CountrySource;
  /** Every Markets country with live or coming-soon cities. */
  countries: MarketCountry[];
  /** True while Markets' countries haven't loaded (or failed: see `reload`). */
  loading: boolean;
  error: boolean;
  reload: () => Promise<void>;
  /** The person picked a country (kept on the device). */
  chooseCountry: (code: string | null) => Promise<void>;
  /** The country known for sure: the delivery address's or the account's (strongest source; not stored). See useKnownCountry. */
  setAddressCountry: (code: string | null) => void;
}

/** The current country: address, then stored choice, then the phone's region, then the only one. */
export function useCountry(): CountryContext {
  const s = useLocaleStore();
  return useMemo(() => {
    const { country, source } = resolveCountry({
      countries: s.countries, addressCountry: s.addressCountry, chosen: s.chosenCountry, deviceLocale: s.device,
    });
    return {
      country, source, countries: s.countries, loading: !s.countries.length && !s.directoryError, error: s.directoryError,
      reload: s.loadDirectory, chooseCountry: s.chooseCountry, setAddressCountry: s.setAddressCountry,
    };
  }, [s.countries, s.addressCountry, s.chosenCountry, s.device, s.directoryError, s.loadDirectory, s.chooseCountry,
      s.setAddressCountry]);
}

export interface I18n {
  /** t("app.test_banner"), t("rider.trips", {count: 3}): the language's message, else English, else the key. */
  t: Translate;
  /** The language shown ("hi"). */
  language: Language;
  /** The script the type tokens draw in now ("devanagari" once its Noto Sans faces are loaded). */
  script: Script;
  /** The languages the current country offers, in Markets' order (what LanguagePicker lists). */
  languages: Language[];
  setLanguage: (language: Language) => Promise<void>;
  /** The country's first Markets locale; undefined (the phone's) until a country is known. */
  formatLocale: string | undefined;
  /** money(250, order.currency) in the country's format; {whole: true} drops ".00". No currency: the country's (Markets). */
  money: (amount: number | string | null | undefined, currency?: string | null, opts?: { whole?: boolean }) => string;
  /** number(1234.5) -> "1,234.5" (country grouping), `digits` decimals at most (1). */
  number: (n: number, digits?: number) => string;
  /** distance(2.14): kilometres in, the country's unit out (or `unit` as the API sends it), one decimal, translated unit. */
  distance: (km: number | null | undefined, unit?: string | null) => string;
  /** date("2026-11-14") -> "14 Nov"; Intl options (weekday, month: "long", timeZone, ...). */
  date: (iso: string | number | Date, opts?: Intl.DateTimeFormatOptions) => string;
  /** time(iso) -> "7:05 pm"; Intl options (timeZone: the order's city, ...). */
  time: (iso: string | number | Date, opts?: Intl.DateTimeFormatOptions) => string;
}

/** Translation and country-aware formatting for a screen. */
export function useI18n(): I18n {
  const { country, countries } = useCountry();
  const chosen = useLocaleStore((s) => s.chosenLanguage);
  const device = useLocaleStore((s) => s.device);
  const setLanguage = useLocaleStore((s) => s.setLanguage);
  // Screens re-render when the script's faces arrive (the `type` tokens read it at render).
  const script = useLocaleStore((s) => s.script);
  return useMemo(() => {
    const locales = country?.locales ?? (chosen ? [chosen] : device ? [device] : null);
    const language = pickLanguage({ chosen, acceptLanguage: device, locales });
    const languages = languagesFor(country?.locales ?? [language]);
    const loc = country ? countryLocale(country.locales) : undefined;
    const t = createTranslator(language, MESSAGES[language], MESSAGES.en);
    return {
      t, language, languages, setLanguage, formatLocale: loc, script,
      money: (amount, currency, opts) => {
        const cur = currency || country?.currency;
        if (!cur) return formatNumber(Number(amount ?? 0), loc, 2);
        return formatMoney(amount, cur, localeForCurrency(cur, country, countries), opts);
      },
      number: (n, digits = 1) => formatNumber(n, loc, digits),
      distance: (km, unit) => {
        if (km == null || !Number.isFinite(km)) return "";
        const d = convertDistance(km, unit ?? country?.distance_unit);
        return t(`app.units.${d.unit}`, { value: formatNumber(d.value, loc, 1) });
      },
      date: (iso, opts) => formatDate(iso, loc, opts),
      time: (iso, opts) => formatTime(iso, loc, opts),
    };
  }, [country, countries, chosen, device, setLanguage, script]);
}

/**
 * Tell the locale store the country we know for sure: the delivery address's
 * (customer app) or the signed-in account's (rider, partner). null clears it.
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
