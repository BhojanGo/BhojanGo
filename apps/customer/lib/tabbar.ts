// The floating tab bar sits 24 px above the bottom edge and is 72 px tall:
// every tab screen leaves this much room at the end of its scroll so nothing
// is ever hidden behind it.
import { useSafeAreaInsets } from "react-native-safe-area-context";

export const TAB_BAR_LIFT = 24;
const TAB_BAR_HEIGHT = 72;

export function useTabBarSpace(): number {
  const insets = useSafeAreaInsets();
  return TAB_BAR_LIFT + TAB_BAR_HEIGHT + insets.bottom + 24;
}
