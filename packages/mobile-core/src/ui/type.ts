// The type scale for the Expo apps (round 8): the ONLY font sizes allowed.
// This is the token file: the one place in the apps where a number may be a
// font size (the bhojango-native/no-raw-font-size lint rule exempts it).
//
// The same scale as the web (packages/ui tokens.js typeScale), fluid by screen
// size: each role runs from its min at a 360 dp screen to its max at 1440 dp,
// linear between, measured on the screen's shorter side (so a phone sits near
// the min, a tablet in between, and turning the tablet does not resize text):
//   display 36-52 · h1 28-36 · h2 22-28 · h3 17-20 · bodyLg 16-18 · body 15-16 ·
//   label 14-15 · small 13-14 · caption 12 (uppercase labels and badges only;
//   nothing readable is under 13).
// Weights: display/h1/h2/caption 700, h3/label 600, body/bodyLg/small 400. Inter
// for Latin; Noto Sans <script> for every role when the UI language is written
// in an Indian script (React Native picks one face per Text, so the face follows
// the language; see setTypeScript, called by I18nProvider).
//
// These are the sizes before the phone's own font setting: Text keeps
// allowFontScaling on, so React Native multiplies them by the system font scale
// (PixelRatio.getFontScale(); fontScale() in ./fonts.ts). Dense UI (tab bars,
// rails) caps it with maxFontSizeMultiplier={DENSE_FONT_SCALE}; never turn it off.
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

interface Spec { min: number; max: number; weight: Weight; lineHeight: number; tracking: number; upper?: boolean }

/** Sizes run from min at a FLUID.minWidth screen to max at FLUID.maxWidth (dp, the shorter side). */
export const FLUID = Object.freeze({ minWidth: 360, maxWidth: 1440 });

/** The scale (sizes and tracking in dp). The web's is packages/ui tokens.js typeScale: the same numbers. */
export const TYPE_SCALE: Readonly<Record<TypeRole, Spec>> = {
  display: { min: 36, max: 52, weight: "700", lineHeight: 1.1, tracking: -0.8 },
  h1: { min: 28, max: 36, weight: "700", lineHeight: 1.15, tracking: -0.4 },
  h2: { min: 22, max: 28, weight: "700", lineHeight: 1.2, tracking: 0 },
  h3: { min: 17, max: 20, weight: "600", lineHeight: 1.3, tracking: 0 },
  bodyLg: { min: 16, max: 18, weight: "400", lineHeight: 1.5, tracking: 0 },
  body: { min: 15, max: 16, weight: "400", lineHeight: 1.5, tracking: 0 },
  label: { min: 14, max: 15, weight: "600", lineHeight: 1.4, tracking: 0 },
  small: { min: 13, max: 14, weight: "400", lineHeight: 1.45, tracking: 0 },
  caption: { min: 12, max: 12, weight: "700", lineHeight: 1.3, tracking: 0.72, upper: true },
};

export const TYPE_ROLES = Object.keys(TYPE_SCALE) as TypeRole[];

/** Each role's [min, max] in dp (what the font audit and the lint rule check against). */
export const TYPE_RANGES: Readonly<Record<TypeRole, readonly [number, number]>> = Object.freeze(
  Object.fromEntries(TYPE_ROLES.map((r) => [r, Object.freeze([TYPE_SCALE[r].min, TYPE_SCALE[r].max] as const)])) as Record<TypeRole, readonly [number, number]>,
);

/** The smallest readable size (the min of small); only the uppercase caption is under it. */
export const MIN_READABLE = TYPE_SCALE.small.min;

/** maxFontSizeMultiplier for dense UI (tab bars, side rails): the phone's font setting still applies, capped. */
export const DENSE_FONT_SCALE = 1.3;

/** The size of a role on a screen of this width (dp): min at 360, max at 1440, linear between, to 0.1 dp. */
export function sizeAt(role: TypeRole, width: number): number {
  const s = TYPE_SCALE[role];
  const k = Math.min(1, Math.max(0, (width - FLUID.minWidth) / (FLUID.maxWidth - FLUID.minWidth)));
  return Math.round((s.min + (s.max - s.min) * k) * 10) / 10;
}

// Loaded faces (useBrandFonts, loadScriptFonts). Android ignores fontWeight for custom fonts, so every weight is its own family.
const LATIN = { "400": "Inter_400Regular", "600": "Inter_600SemiBold", "700": "Inter_700Bold" } as const;
const NOTO: Record<Exclude<Script, "latin">, string> = {
  devanagari: "NotoSansDevanagari", telugu: "NotoSansTelugu", tamil: "NotoSansTamil", kannada: "NotoSansKannada", bengali: "NotoSansBengali",
};
const SUFFIX: Record<Weight, string> = { "400": "_400Regular", "600": "_600SemiBold", "700": "_700Bold" };

/** The font family for a weight in a script ("NotoSansTelugu_600SemiBold"). One family for every role. */
export function familyFor(script: Script, weight: Weight): string {
  if (script === "latin") return LATIN[weight];
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

/** The text style for a role in a script on a screen of this width: size, line height, the face for the weight, caption's uppercase. */
export function typeStyleFor(role: TypeRole, script: Script = "latin", width: number = FLUID.minWidth): TextStyle {
  const s = TYPE_SCALE[role];
  const latin = script === "latin";
  const size = sizeAt(role, width);
  // Indian scripts have tall ascenders and descenders (matras): give them more leading and no negative tracking.
  const lh = latin ? s.lineHeight : s.lineHeight + 0.2;
  return {
    fontFamily: familyFor(script, s.weight),
    fontSize: size,
    lineHeight: Math.round(size * lh),
    // Tracking only for Latin: letter spacing breaks Indic conjuncts.
    ...(latin && s.tracking ? { letterSpacing: s.tracking } : {}),
    ...(s.upper ? { textTransform: "uppercase" as const } : {}),
  };
}

const cache = new Map<string, Readonly<Record<TypeRole, TextStyle>>>();
function stylesFor(script: Script, width: number): Readonly<Record<TypeRole, TextStyle>> {
  const key = `${script}|${width}`;
  let s = cache.get(key);
  if (!s) {
    s = Object.freeze(Object.fromEntries(TYPE_ROLES.map((r) => [r, Object.freeze(typeStyleFor(r, script, width))])) as Record<TypeRole, TextStyle>);
    cache.set(key, s);
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

let currentWidth: number = FLUID.minWidth;

/**
 * The screen size the tokens scale to: the shorter side of the window in dp
 * (useBrandFonts sets it from useWindowDimensions before the app draws).
 * Rounded to whole dp so the style caches stay small.
 */
export function setTypeWidth(width: number): void {
  if (Number.isFinite(width) && width > 0) currentWidth = Math.round(width);
}
export function typeWidth(): number {
  return currentWidth;
}

// ── font audit (dev only) ────────────────────────────────────────────────────
// EXPO_PUBLIC_FONT_AUDIT=1 records every token (role and size) read while a screen
// renders and logs "FONT_AUDIT <route> <role:size,...>", e.g.
//   FONT_AUDIT /orders caption:12,small:13.1,label:14.1,h3:17.3,h1:28.6
// (see tools/mobile/font_sizes.py, which checks each size is in its role's range). Expo
// inlines EXPO_PUBLIC_* at build time, so with the flag off this is `false` and
// the recording branch is dead code.
const AUDIT = process.env.EXPO_PUBLIC_FONT_AUDIT === "1"; // written out in full so Expo inlines it
let auditRoute = "/";
let auditSizes = new Set<string>();
let auditTimer: ReturnType<typeof setTimeout> | null = null;
let auditLast = "";

function auditFlush() {
  auditTimer = null;
  const bySize = (a: string, b: string) => parseFloat(a.split(":")[1] ?? "0") - parseFloat(b.split(":")[1] ?? "0");
  const line = `FONT_AUDIT ${auditRoute} ${[...auditSizes].sort(bySize).join(",")}`;
  if (line !== auditLast) {
    auditLast = line;
    console.log(line);
  }
}

/** Record a rendered role and size (called by the tokens' getters when the audit is on). */
export function auditSize(role: TypeRole, size: number | undefined): void {
  if (!AUDIT || size == null) return;
  auditSizes.add(`${role}:${size}`);
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
      const s = stylesFor(current, currentWidth)[r];
      if (AUDIT) auditSize(r, s.fontSize);
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
 * Each entry is a role plus extra (non-size) style; the result is cached per script and screen size.
 */
export function textStyles<K extends string>(defs: Record<K, readonly [TypeRole, TextStyle?]>): Readonly<Record<K, TextStyle>>;
/** The same, added to other (view) styles: textStyles(StyleSheet.create({ card: {...} }), { title: ["h3"] }). */
export function textStyles<B extends object, K extends string>(base: B, defs: Record<K, readonly [TypeRole, TextStyle?]>): Readonly<B & Record<K, TextStyle>>;
export function textStyles(a: object, b?: Record<string, readonly [TypeRole, TextStyle?]>): object {
  const views = b ? a : {};
  const defs = (b ?? a) as Record<string, readonly [TypeRole, TextStyle?]>;
  const built = new Map<string, Record<string, TextStyle>>();
  const resolve = (): Record<string, TextStyle> => {
    const key = `${current}|${currentWidth}`;
    let styles = built.get(key);
    if (!styles) {
      const roles = stylesFor(current, currentWidth);
      styles = Object.fromEntries(Object.entries(defs).map(([k, [role, extra]]) => [k, Object.freeze({ ...roles[role], ...(extra ?? {}) })]));
      built.set(key, styles);
    }
    return styles;
  };
  return Object.defineProperties({ ...views }, Object.fromEntries(Object.keys(defs).map((k) => [k, {
    enumerable: true,
    get: () => {
      const s = resolve()[k] as TextStyle;
      if (AUDIT) auditSize(defs[k]![0], s.fontSize);
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
export function face(weight: Weight = "400"): TextStyle {
  return { fontFamily: familyFor(current, weight) };
}
