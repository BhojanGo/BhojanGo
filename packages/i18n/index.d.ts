export type Language = "en" | "hi" | "te" | "ta" | "kn" | "mr" | "bn" | "es";
export type Messages = { [key: string]: string | Messages | { one?: string; few?: string; many?: string; other: string } };
export type Translate = (key: string, vars?: Record<string, string | number>) => string;

export declare const LANGUAGES: Record<Language, { name: string; dir: "ltr" | "rtl" }>;
export declare const DEFAULT_LANGUAGE: Language;
export declare function languageOf(locale: string | null | undefined): string;
export declare function languagesFor(locales: string[] | null | undefined): Language[];
export declare function pickLanguage(opts: { chosen?: string | null; acceptLanguage?: string | null; locales?: string[] | null }): Language;
export declare function languageList(locales: string[] | null | undefined): { code: Language; name: string }[];
export declare function chooseLanguage(chosen: string | null | undefined, locales: string[] | null | undefined): Language;
export type CountrySource = "address" | "chosen" | "page" | "ip" | "browser" | "default" | "none";
export declare function detectCountry(
  evidence: { address?: string | null; chosen?: string | null; page?: string | null; ip?: string | null; browser?: string | readonly string[] | null },
  countries: readonly { code: string; locales?: readonly string[] | null }[] | null | undefined,
): { code: string | null; source: CountrySource };
export declare function formatLocale(locales: string[] | null | undefined): string;
export declare function createTranslator(language: string, messages: Messages, fallback: Messages): Translate;
export declare function pluralSelector(language: string): (count: number) => string;
