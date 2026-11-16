// Design tokens for the Expo apps (P16), from the one source in @bhojango/ui/tokens.
import { color, dark, radius, space, touch } from "@bhojango/ui/tokens";
import type { TextStyle } from "react-native";

import { face } from "./type";

export { color, dark, radius, space, touch };

/**
 * The face for a weight, in the language's script, with no size: for nested
 * emphasis inside a Text that already has a size from a `type` token.
 * Sizes come only from the type scale (./type.ts): style={[type.label, ...]}.
 */
export function textFont(weight: "400" | "600" | "700" = "400"): TextStyle {
  return face(weight);
}

/** The heading face (Inter 700), no size. Prefer type.display / type.h1 / type.h2. */
export function displayFont(): TextStyle {
  return face("700");
}

/** Shadows (RN has no box-shadow strings): floating cards, the tab bar, sheets. */
export const elevation = {
  float: { shadowColor: "#111418", shadowOpacity: 0.08, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 4 },
  bar: { shadowColor: "#111418", shadowOpacity: 0.28, shadowRadius: 32, shadowOffset: { width: 0, height: 12 }, elevation: 12 },
  sheet: { shadowColor: "#111418", shadowOpacity: 0.12, shadowRadius: 40, shadowOffset: { width: 0, height: -8 }, elevation: 16 },
} as const;
