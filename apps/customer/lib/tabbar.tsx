// The room the floating tab bar needs (one shared value, from mobile-core's
// tabBarClearance): every tab screen (home, search, orders, account) ends its
// scroll with this much paddingBottom in every state (list, empty, loading,
// error), so nothing is ever hidden behind the bar. Floating things stacked
// above the bar (the bag pill on home) add their height.
import { aboveTabBar, tabBarBottom, tabBarClearance } from "@bhojango/mobile-core";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

/** paddingBottom for a tab screen's scroll; `stacked`: heights of floating buttons above the bar. */
export function useTabBarSpace(stacked: readonly number[] = []): number {
  const insets = useSafeAreaInsets();
  return tabBarClearance(insets.bottom, stacked);
}

/** The bar's own bottom offset (the tabs layout) and a floating button's, just above it. */
export function useTabBarOffsets(): { bar: number; above: number } {
  const insets = useSafeAreaInsets();
  return { bar: tabBarBottom(insets.bottom), above: aboveTabBar(insets.bottom) };
}

/**
 * An empty strip right under a tab screen's last item, before the clearance: its
 * top edge is at (or below) the last item's bottom edge. The Maestro check
 * (.maestro/tabbar-clearance.yaml) asserts this strip is above the tab bar
 * once the screen is scrolled to the end, which proves the last item is not covered.
 */
export function TabEnd({ tab }: { tab: "home" | "search" | "orders" | "account" }) {
  return <View testID={`${tab}-end`} collapsable={false} style={{ height: 8, alignSelf: "stretch" }} />;
}
