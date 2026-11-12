// The rider app's dark theme: the `dark` tokens plus the few extra shades the
// rider screens on the design board use (docs/design/screens/Rider*.html).
import { color, dark, displayFont, radius, space, textFont } from "@bhojango/mobile-core";
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

type Style = ViewStyle & TextStyle;
type Key = "screen" | "muted" | "body" | "bold" | "pill" | "pillText" | "sheet" | "cta" | "ctaText" | "outline" | "stats" | "stat"
  | "statValue" | "statLabel" | "h1";

const sheet: Record<Key, Style> = {
  screen: { flex: 1, backgroundColor: night.ground },
  muted: { color: night.muted, fontSize: 13, ...textFont("400") },
  body: { color: night.text, fontSize: 15, ...textFont("400") },
  bold: { color: night.text, ...textFont("800") },
  pill: {
    height: 44, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: "rgba(20, 34, 37, 0.92)",
    flexDirection: "row", alignItems: "center", gap: 8,
  },
  pillText: { color: night.text, fontSize: 14, ...textFont("700") },
  sheet: { position: "absolute", left: 10, right: 10, bottom: 10, borderRadius: 32, backgroundColor: night.surface },
  cta: {
    height: 64, borderRadius: radius.pill, backgroundColor: night.kesar, alignItems: "center", justifyContent: "center",
    flexDirection: "row", gap: 8,
  },
  ctaText: { color: night.onKesar, fontSize: 19, ...textFont("800") },
  outline: {
    height: 56, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.lineStrong, alignItems: "center",
    justifyContent: "center", flexDirection: "row", gap: 8,
  },
  stats: { flexDirection: "row", borderRadius: 20, backgroundColor: night.raised, paddingVertical: 14 },
  stat: { flex: 1, alignItems: "center" },
  statValue: { color: night.text, fontSize: 20, ...textFont("800") },
  statLabel: { color: night.muted, fontSize: 12, ...textFont("400") },
  h1: { color: night.text, fontSize: 32, letterSpacing: -0.8, lineHeight: 34, ...displayFont("600") },
};

export const ui: Record<Key, Style> = StyleSheet.create(sheet);
