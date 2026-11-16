import { color, TabBar, useI18n, useSession } from "@bhojango/mobile-core";
import { Redirect, router, Tabs } from "expo-router";
import { View } from "react-native";

import { Icon, type IconName } from "../../lib/icons";
import { useTabBarOffsets } from "../../lib/tabbar";

// Labels are the website's tabs.* keys (packages/i18n), in the chosen language.
const ITEMS: { key: "home" | "search" | "orders" | "account"; icon: IconName }[] = [
  { key: "home", icon: "home" },
  { key: "search", icon: "search" },
  { key: "orders", icon: "orders" },
  { key: "account", icon: "account" },
];

export default function TabsLayout() {
  const status = useSession((s) => s.status);
  const { t } = useI18n();
  const { bar, zone } = useTabBarOffsets();
  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  return (
    <Tabs
      // Every tab screen ends above the band the bar floats in (R8: nothing under the bar at rest);
      // each one leaves useTabBarSpace() at the end of its scroll.
      screenOptions={{ headerShown: false, sceneStyle: { paddingBottom: zone, backgroundColor: color.porcelain } }}
      tabBar={({ state }) => (
        <View pointerEvents="box-none" style={{ position: "absolute", left: 0, right: 0, bottom: bar, alignItems: "center" }}>
          <TabBar
            current={state.routes[state.index]?.name ?? "home"}
            onSelect={(key) => router.navigate(`/${key}` as "/home")}
            items={ITEMS.map((i) => ({ key: i.key, label: t(`tabs.${i.key}`), icon: (c: string) => <Icon name={i.icon} stroke={c} /> }))}
          />
        </View>
      )}
    >
      {ITEMS.map((i) => (
        <Tabs.Screen key={i.key} name={i.key} options={{ title: t(`tabs.${i.key}`) }} />
      ))}
    </Tabs>
  );
}
