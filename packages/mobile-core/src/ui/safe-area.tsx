// The apps' SafeAreaView (R8): the same props as react-native-safe-area-context's
// (edges, style, children, any View prop), but the insets come from
// useSafeAreaInsets(), so a screen under the test banner does not pad the status
// bar again. Why: see safe-area-pad.ts. The apps import SafeAreaView from
// @bhojango/mobile-core; ESLint refuses the native one (eslint/index.js).
import { StyleSheet, View, type ViewProps } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ALL_EDGES, safePadding, type Edge } from "./safe-area-pad";

export type { Edge as SafeAreaEdge };

export function SafeAreaView({ edges = ALL_EDGES, style, ...rest }: ViewProps & { edges?: readonly Edge[] }) {
  const insets = useSafeAreaInsets();
  const flat = StyleSheet.flatten(style) ?? {};
  return <View {...rest} style={[flat, safePadding(flat, insets, edges)]} />;
}
