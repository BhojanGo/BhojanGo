export type Language = "en" | "hi" | "te" | "ta" | "kn" | "mr" | "bn" | "es";
export type Messages = { [key: string]: string | Messages | { one?: string; few?: string; many?: string; other: string } };
export type Translate = (key: string, vars?: Record<string, string | number>) => string;

export declare const LANGUAGES: Record<Language, { name: string; dir: "ltr" | "rtl" }>;
export declare const DEFAULT_LANGUAGE: Language;
export declare function languageOf(locale: string | null | undefined): string;
export declare function languagesFor(locales: string[] | null | undefined): Language[];
export declare function pickLanguage(opts: { chosen?: string | null; acceptLanguage?: string | null; locales?: string[] | null }): Language;
export declare function formatLocale(locales: string[] | null | undefined): string;
export declare function createTranslator(language: string, messages: Messages, fallback: Messages): Translate;
