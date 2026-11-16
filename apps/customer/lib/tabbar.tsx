// The room the floating tab bar needs (mobile-core's tabbar.ts, one place).
// R8: the tabs layout ends every tab screen above the band the bar floats in
// (tabBarZone), so nothing sits under the bar at rest; each tab screen still
// ends its scroll with useTabBarSpace() (breathing room, plus floating things
// stacked above the bar: the bag pill on home) in every state (list, empty,
// loading, error).
import { sceneEndSpace, TAB_BAR_GAP, tabBarBottom, tabBarZone } from "@bhojango/mobile-core";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

/** paddingBottom for a tab screen's scroll; `stacked`: heights of floating buttons above the bar. */
export function useTabBarSpace(stacked: readonly number[] = []): number {
  return sceneEndSpace(stacked);
}

/**
 * The tabs layout's numbers: `bar`, the bar's bottom offset in the window; `zone`, the band
 * every tab screen ends above; `above`, a floating button's bottom offset inside a tab screen
 * (just above the bar).
 */
export function useTabBarOffsets(): { bar: number; zone: number; above: number } {
  const insets = useSafeAreaInsets();
  return { bar: tabBarBottom(insets.bottom), zone: tabBarZone(insets.bottom), above: TAB_BAR_GAP };
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
