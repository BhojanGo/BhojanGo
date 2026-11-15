import { TabBar, useI18n, useSession } from "@bhojango/mobile-core";
import { Redirect, router, Tabs } from "expo-router";
import { View } from "react-native";

import { Icon, type IconName } from "../../lib/icons";

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
  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  return (
    <Tabs
      screenOptions={{ headerShown: false }}
      tabBar={({ state }) => (
        <View pointerEvents="box-none" style={{ position: "absolute", left: 0, right: 0, bottom: 24, alignItems: "center" }}>
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
