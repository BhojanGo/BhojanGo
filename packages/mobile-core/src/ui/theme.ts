// Design tokens for the Expo apps (P16), from the one source in @bhojango/ui/tokens.
import { color, dark, radius, space, touch, type } from "@bhojango/ui/tokens";
import type { TextStyle } from "react-native";

export { color, dark, radius, space, touch };

// Fonts are loaded per weight (useBrandFonts); Android ignores fontWeight for custom fonts.
const TEXT = {
  "400": "HankenGrotesk_400Regular",
  "500": "HankenGrotesk_500Medium",
  "600": "HankenGrotesk_600SemiBold",
  "700": "HankenGrotesk_700Bold",
  "800": "HankenGrotesk_800ExtraBold",
} as const;
const DISPLAY = {
  "500": "FamiljenGrotesk_500Medium",
  "600": "FamiljenGrotesk_600SemiBold",
  "700": "FamiljenGrotesk_700Bold",
} as const;

export type Weight = keyof typeof TEXT;

export function textFont(weight: Weight = "400"): TextStyle {
  return { fontFamily: TEXT[weight] };
}

export function displayFont(weight: keyof typeof DISPLAY = "600"): TextStyle {
  return { fontFamily: DISPLAY[weight] };
}

/** A named text style from the type scale (hero, h1, h2, title, body, label, small, tag, eyebrow). */
export function typeStyle(name: keyof typeof type): TextStyle {
  const t = type[name];
  const family = t.family === "display" ? DISPLAY[(t.weight in DISPLAY ? t.weight : "600") as keyof typeof DISPLAY] : TEXT[t.weight];
  return {
    fontFamily: family,
    fontSize: t.size,
    letterSpacing: t.tracking,
    lineHeight: Math.round(t.size * (t.family === "display" ? 1.1 : 1.45)),
    ...(name === "eyebrow" || name === "tag" ? { textTransform: "uppercase" as const } : {}),
  };
}

export const FONT_FILES = { ...TEXT, ...DISPLAY };

/** Shadows (RN has no box-shadow strings): floating cards, the tab bar, sheets. */
export const elevation = {
  float: { shadowColor: "#111418", shadowOpacity: 0.08, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 4 },
  bar: { shadowColor: "#111418", shadowOpacity: 0.28, shadowRadius: 32, shadowOffset: { width: 0, height: 12 }, elevation: 12 },
  sheet: { shadowColor: "#111418", shadowOpacity: 0.12, shadowRadius: 40, shadowOffset: { width: 0, height: -8 }, elevation: 16 },
} as const;
