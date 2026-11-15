// The rider app's dark theme: the `dark` tokens plus the few extra shades the
// rider screens on the design board use (docs/design/screens/Rider*.html).
import { color, dark, displayFont, radius, space, textFont, textStyles } from "@bhojango/mobile-core";
import { StyleSheet, type TextStyle, type ViewStyle } from "react-native";

export const night = {
  ...dark,
  kesar: color.kesarBright, // the rider's action colour
  onKesar: color.kohl,
  doneBg: "#1D4F53", // tick circles, info card border
  info: "#0F2A2C", // "How pay works", the floor card
  needed: "#F6DFA8", // "Needed now"
  noteBg: "#2A2310", // "Leave at door"
  map: "#0F1B1D",
  road: "#1A2A2D",
  divider: "#2A3E41",
  dashed: "#3A5256",
  online: "#5FD39A", // status dot only
  sosBorder: "#6B2A26",
  sosText: "#FF9A8F",
  chili: color.chili,
};

export { displayFont, radius, space, textFont };

type ViewKey = "screen" | "pill" | "sheet" | "cta" | "outline" | "stats" | "stat";
type TextKey = "muted" | "body" | "note" | "bold" | "pillText" | "ctaText" | "statValue" | "statLabel" | "caption" | "display" | "h1" | "h2";

const views: Record<ViewKey, ViewStyle> = {
  screen: { flex: 1, backgroundColor: night.ground },
  pill: {
    height: 44, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: "rgba(20, 34, 37, 0.92)",
    flexDirection: "row", alignItems: "center", gap: 8,
  },
  sheet: { position: "absolute", left: 10, right: 10, bottom: 10, borderRadius: 32, backgroundColor: night.surface },
  cta: {
    height: 64, borderRadius: radius.pill, backgroundColor: night.kesar, alignItems: "center", justifyContent: "center",
    flexDirection: "row", gap: 8,
  },
  outline: {
    height: 56, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.lineStrong, alignItems: "center",
    justifyContent: "center", flexDirection: "row", gap: 8,
  },
  stats: { flexDirection: "row", borderRadius: 20, backgroundColor: night.raised, paddingVertical: 14 },
  stat: { flex: 1, alignItems: "center" },
};

/** The rider screens' styles; text in the type scale, in the language's face (read at render). */
export const ui: Readonly<Record<ViewKey, ViewStyle> & Record<TextKey, TextStyle>> = textStyles(StyleSheet.create(views), {
  muted: ["small", { color: night.muted }],
  body: ["body", { color: night.text }],
  note: ["small", { color: night.text }],
  bold: ["label", { color: night.text }],
  pillText: ["label", { color: night.text }],
  ctaText: ["h3", { color: night.onKesar }],
  statValue: ["h3", { color: night.text, fontVariant: ["tabular-nums"] }],
  statLabel: ["caption", { color: night.muted }],
  caption: ["caption", { color: night.muted }],
  display: ["display", { color: night.text }],
  h1: ["h1", { color: night.text }],
  h2: ["h2", { color: night.text }],
});
