// The type scale for the Expo apps (round 6): the ONLY font sizes allowed.
// This is the token file: the one place in the apps where a number may be a
// font size (the bhojango-native/no-raw-font-size lint rule exempts it).
//
// The apps use the phone column of the scale everywhere (the partner tablet
// too): display 44 · h1 30 · h2 22 · h3 18 · bodyLg 17 · body 16 · label 15 ·
// small 14 · caption 12 (uppercase labels and badges only; nothing readable
// is smaller than 14). Weights: display/h1/h2/h3/label 600, body/bodyLg/small
// 400, caption 700. Familjen Grotesk for display/h1/h2, Hanken Grotesk for the
// rest, Noto Sans <script> for every role when the UI language is written in an
// Indian script (React Native picks one face per Text, so the face follows the
// language; see setTypeScript, called by I18nProvider).
//
//   <Text style={[type.body, { color: color.muted }]}>…</Text>
//   <Text style={[type.h3, num]}>{money(total)}</Text>      tabular figures for amounts
//   <T variant="label">…</T>                                  the same, as a component
//   const s = textStyles({ name: ["h3", { color: color.kohl }] });   StyleSheet-like, language-aware
//
// Pure TypeScript (no react-native import at runtime) so node --test can load it.
import type { TextStyle } from "react-native";

export type TypeRole = "display" | "h1" | "h2" | "h3" | "bodyLg" | "body" | "label" | "small" | "caption";
export type Script = "latin" | "devanagari" | "telugu" | "tamil" | "kannada" | "bengali";
type Weight = "400" | "600" | "700";

interface Spec { size: number; weight: Weight; display: boolean; lineHeight: number; tracking: number; upper?: boolean }

/** The phone column of the scale (sizes in dp). The desktop column is the web's (packages/ui). */
export const TYPE_SCALE: Readonly<Record<TypeRole, Spec>> = {
  display: { size: 44, weight: "600", display: true, lineHeight: 1.05, tracking: -1.2 },
  h1: { size: 30, weight: "600", display: true, lineHeight: 1.1, tracking: -0.6 },
  h2: { size: 22, weight: "600", display: true, lineHeight: 1.2, tracking: -0.3 },
  h3: { size: 18, weight: "600", display: false, lineHeight: 1.3, tracking: 0 },
  bodyLg: { size: 17, weight: "400", display: false, lineHeight: 1.5, tracking: 0 },
  body: { size: 16, weight: "400", display: false, lineHeight: 1.5, tracking: 0 },
  label: { size: 15, weight: "600", display: false, lineHeight: 1.4, tracking: 0 },
  small: { size: 14, weight: "400", display: false, lineHeight: 1.45, tracking: 0 },
  caption: { size: 12, weight: "700", display: false, lineHeight: 1.3, tracking: 0.72, upper: true },
};

export const TYPE_ROLES = Object.keys(TYPE_SCALE) as TypeRole[];

/** Every size the scale allows (what the font audit and the lint rule check against). */
export const TYPE_SIZES: readonly number[] = [...new Set(TYPE_ROLES.map((r) => TYPE_SCALE[r].size))].sort((a, b) => a - b);

// Loaded faces (useBrandFonts, loadScriptFonts). Android ignores fontWeight for custom fonts, so every weight is its own family.
const LATIN = { "400": "HankenGrotesk_400Regular", "600": "HankenGrotesk_600SemiBold", "700": "HankenGrotesk_700Bold" } as const;
const LATIN_DISPLAY = "FamiljenGrotesk_600SemiBold";
const NOTO: Record<Exclude<Script, "latin">, string> = {
  devanagari: "NotoSansDevanagari", telugu: "NotoSansTelugu", tamil: "NotoSansTamil", kannada: "NotoSansKannada", bengali: "NotoSansBengali",
};
const SUFFIX: Record<Weight, string> = { "400": "_400Regular", "600": "_600SemiBold", "700": "_700Bold" };

/** The font family for a weight in a script ("NotoSansTelugu_600SemiBold"). */
export function familyFor(script: Script, weight: Weight, display = false): string {
  if (script === "latin") return display && weight === "600" ? LATIN_DISPLAY : LATIN[weight];
  return NOTO[script] + SUFFIX[weight];
}

/** The script a UI language is written in (Marathi and Hindi share Devanagari). */
export function scriptFor(language: string | null | undefined): Script {
  switch ((language ?? "").toLowerCase().split(/[-_]/)[0]) {
    case "hi": case "mr": case "ne": return "devanagari";
    case "te": return "telugu";
    case "ta": return "tamil";
    case "kn": return "kannada";
    case "bn": return "bengali";
    default: return "latin";
  }
}

/** The text style for a role in a script: size, line height, the face for the weight, caption's uppercase. */
export function typeStyleFor(role: TypeRole, script: Script = "latin"): TextStyle {
  const s = TYPE_SCALE[role];
  const latin = script === "latin";
  // Indian scripts have tall ascenders and descenders (matras): give them more leading and no negative tracking.
  const lh = latin ? s.lineHeight : s.lineHeight + 0.2;
  return {
    fontFamily: familyFor(script, s.weight, s.display),
    fontSize: s.size,
    lineHeight: Math.round(s.size * lh),
    // Tracking only for Latin: letter spacing breaks Indic conjuncts.
    ...(latin && s.tracking ? { letterSpacing: s.tracking } : {}),
    ...(s.upper ? { textTransform: "uppercase" as const } : {}),
  };
}

const cache = new Map<Script, Readonly<Record<TypeRole, TextStyle>>>();
function stylesFor(script: Script): Readonly<Record<TypeRole, TextStyle>> {
  let s = cache.get(script);
  if (!s) {
    s = Object.freeze(Object.fromEntries(TYPE_ROLES.map((r) => [r, Object.freeze(typeStyleFor(r, script))])) as Record<TypeRole, TextStyle>);
    cache.set(script, s);
  }
  return s;
}

let current: Script = "latin";

/** The script whose faces the tokens use (I18nProvider sets it once the language's fonts are loaded). */
export function setTypeScript(script: Script): void {
  current = script;
}
export function typeScript(): Script {
  return current;
}

// ── font audit (dev only) ────────────────────────────────────────────────────
// EXPO_PUBLIC_FONT_AUDIT=1 records every token size read while a screen renders
// and logs "FONT_AUDIT <route> <sizes>" (see tools/mobile/font_sizes.py). Expo
// inlines EXPO_PUBLIC_* at build time, so with the flag off this is `false` and
// the recording branch is dead code.
const AUDIT = process.env.EXPO_PUBLIC_FONT_AUDIT === "1"; // written out in full so Expo inlines it
let auditRoute = "/";
let auditSizes = new Set<number>();
let auditTimer: ReturnType<typeof setTimeout> | null = null;
let auditLast = "";

function auditFlush() {
  auditTimer = null;
  const line = `FONT_AUDIT ${auditRoute} ${[...auditSizes].sort((a, b) => a - b).join(",")}`;
  if (line !== auditLast) {
    auditLast = line;
    console.log(line);
  }
}

/** Record a rendered size (called by the tokens' getters when the audit is on). */
export function auditSize(size: number | undefined): void {
  if (!AUDIT || size == null) return;
  auditSizes.add(size);
  if (!auditTimer) auditTimer = setTimeout(auditFlush, 800);
}

/** The route now on screen (useFontAudit in each app's root layout). Starts a new size list. */
export function setAuditRoute(route: string): void {
  if (!AUDIT || route === auditRoute) return;
  if (auditTimer) clearTimeout(auditTimer);
  if (auditSizes.size) auditFlush();
  auditRoute = route;
  auditSizes = new Set();
  auditLast = "";
}

export const fontAuditEnabled = AUDIT;

// ── the tokens ──────────────────────────────────────────────────────────────

/**
 * type.display … type.caption: read at render, so they follow the language's face.
 * Don't spread them into StyleSheet.create (that freezes the face at import);
 * use them inline or through textStyles().
 */
export const type: Readonly<Record<TypeRole, TextStyle>> = Object.defineProperties(
  {} as Record<TypeRole, TextStyle>,
  Object.fromEntries(TYPE_ROLES.map((r) => [r, {
    enumerable: true,
    get: () => {
      const s = stylesFor(current)[r];
      if (AUDIT) auditSize(s.fontSize);
      return s;
    },
  }])),
);

/** Tabular figures for amounts (money, totals, prices, counts in columns): style={[type.label, num]}. */
export const num: TextStyle = Object.freeze({ fontVariant: ["tabular-nums"] as TextStyle["fontVariant"] });

/**
 * A StyleSheet-like set of text styles that follow the language's face:
 *   const s = textStyles({ title: ["h3", { color: color.kohl }], amount: ["label", num] });
 *   <Text style={s.title}>…</Text>
 * Each entry is a role plus extra (non-size) style; the result is cached per script.
 */
export function textStyles<K extends string>(defs: Record<K, readonly [TypeRole, TextStyle?]>): Readonly<Record<K, TextStyle>>;
/** The same, added to other (view) styles: textStyles(StyleSheet.create({ card: {...} }), { title: ["h3"] }). */
export function textStyles<B extends object, K extends string>(base: B, defs: Record<K, readonly [TypeRole, TextStyle?]>): Readonly<B & Record<K, TextStyle>>;
export function textStyles(a: object, b?: Record<string, readonly [TypeRole, TextStyle?]>): object {
  const views = b ? a : {};
  const defs = (b ?? a) as Record<string, readonly [TypeRole, TextStyle?]>;
  const built = new Map<Script, Record<string, TextStyle>>();
  const resolve = (): Record<string, TextStyle> => {
    let styles = built.get(current);
    if (!styles) {
      const roles = stylesFor(current);
      styles = Object.fromEntries(Object.entries(defs).map(([k, [role, extra]]) => [k, Object.freeze({ ...roles[role], ...(extra ?? {}) })]));
      built.set(current, styles);
    }
    return styles;
  };
  return Object.defineProperties({ ...views }, Object.fromEntries(Object.keys(defs).map((k) => [k, {
    enumerable: true,
    get: () => {
      const s = resolve()[k] as TextStyle;
      if (AUDIT) auditSize(s.fontSize);
      return s;
    },
  }])));
}

/**
 * Text styles for a TextInput: the role without its line height (an input centres
 * its one line itself; a line height pushes the text off centre on Android).
 *   <TextInput style={[field.body, s.input]} />
 */
export const field = textStyles({
  body: ["body", { lineHeight: undefined }],
  bodyLg: ["bodyLg", { lineHeight: undefined }],
  h3: ["h3", { lineHeight: undefined }],
  h2: ["h2", { lineHeight: undefined }],
  h1: ["h1", { lineHeight: undefined }],
});

/** The family alone for a weight (nested emphasis inside a token-styled Text): <Text style={face("700")}>. */
export function face(weight: Weight = "400", display = false): TextStyle {
  return { fontFamily: familyFor(current, weight, display) };
}
