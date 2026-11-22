// R28: "Start a new bag? Your bag from <kitchen> will be cleared." with Cancel and Start new bag,
// before anything replaces a bag from another kitchen (adding a dish, Order again).
import { useBag } from "@bhojango/mobile-core";
import { Alert } from "react-native";

import { bagConflict } from "./ordering";

type T = (key: string, values?: Record<string, string>) => string;

/** True when the dish may go in the bag: nothing would be lost, or the person chose Start new bag. */
export function okToReplaceBag(restaurantId: string, t: T): Promise<boolean> {
  const kitchen = bagConflict(useBag.getState(), restaurantId);
  if (kitchen === null) return Promise.resolve(true);
  return new Promise((resolve) => {
    Alert.alert(t("kitchen.new_bag_title"), t("kitchen.new_bag_cleared", { kitchen }), [
      { text: t("common.cancel"), style: "cancel", onPress: () => resolve(false) },
      { text: t("kitchen.start_new_bag"), style: "destructive", onPress: () => resolve(true) },
    ], { cancelable: true, onDismiss: () => resolve(false) });
  });
}
