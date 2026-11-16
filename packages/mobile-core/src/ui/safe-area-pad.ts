// The padding a safe-area screen adds (R8): pure, so it is tested without React Native.
//
// Why the apps need their own SafeAreaView: react-native-safe-area-context's
// SafeAreaView is a native view that measures the window itself and ignores the
// insets the JS tree provides. WithTestBanner (ui/locale.tsx) gives the status bar
// to the test banner and tells the screens below "no top inset" through
// SafeAreaInsetsContext; the native view never hears it, so every screen padded
// the status bar a second time (a ~70 px empty band under the banner on every
// screen of all three apps). The apps' SafeAreaView reads useSafeAreaInsets(),
// which does follow the context: under the banner the top inset is 0, in
// production (no banner) it is the status bar.

export type Edge = "top" | "right" | "bottom" | "left";
export interface Insets { top: number; right: number; bottom: number; left: number }
export const ALL_EDGES: readonly Edge[] = ["top", "right", "bottom", "left"];

type Pad = Partial<Record<"padding" | "paddingVertical" | "paddingHorizontal" | "paddingTop" | "paddingRight" | "paddingBottom" | "paddingLeft", unknown>>;

const num = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);

/** The style's own padding on each edge plus the inset on the edges asked for (numbers only; a % padding is left as it is). */
export function safePadding(style: Pad | null | undefined, insets: Insets, edges: readonly Edge[] = ALL_EDGES): Partial<Record<"paddingTop" | "paddingRight" | "paddingBottom" | "paddingLeft", number>> {
  const s = style ?? {};
  const own = {
    top: num(s.paddingTop) ?? num(s.paddingVertical) ?? num(s.padding) ?? 0,
    bottom: num(s.paddingBottom) ?? num(s.paddingVertical) ?? num(s.padding) ?? 0,
    left: num(s.paddingLeft) ?? num(s.paddingHorizontal) ?? num(s.padding) ?? 0,
    right: num(s.paddingRight) ?? num(s.paddingHorizontal) ?? num(s.padding) ?? 0,
  };
  const out: Partial<Record<"paddingTop" | "paddingRight" | "paddingBottom" | "paddingLeft", number>> = {};
  for (const e of edges) {
    const key = `padding${e[0]!.toUpperCase()}${e.slice(1)}` as "paddingTop" | "paddingRight" | "paddingBottom" | "paddingLeft";
    out[key] = own[e] + insets[e];
  }
  return out;
}
