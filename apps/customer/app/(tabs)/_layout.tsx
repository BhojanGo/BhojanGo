import { TabBar, useSession } from "@bhojango/mobile-core";
import { Redirect, router, Tabs } from "expo-router";
import { View } from "react-native";

import { Icon, type IconName } from "../../lib/icons";

const ITEMS: { key: string; label: string; icon: IconName }[] = [
  { key: "home", label: "Home", icon: "home" },
  { key: "search", label: "Search", icon: "search" },
  { key: "orders", label: "Orders", icon: "orders" },
  { key: "account", label: "Account", icon: "account" },
];

export default function TabsLayout() {
  const status = useSession((s) => s.status);
  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  return (
    <Tabs
      screenOptions={{ headerShown: false }}
      tabBar={({ state }) => (
        <View pointerEvents="box-none" style={{ position: "absolute", left: 0, right: 0, bottom: 24, alignItems: "center" }}>
          <TabBar
            current={state.routes[state.index]?.name ?? "home"}
            onSelect={(key) => router.navigate(`/${key}` as "/home")}
            items={ITEMS.map((t) => ({ key: t.key, label: t.label, icon: (c: string) => <Icon name={t.icon} stroke={c} /> }))}
          />
        </View>
      )}
    >
      {ITEMS.map((t) => (
        <Tabs.Screen key={t.key} name={t.key} options={{ title: t.label }} />
      ))}
    </Tabs>
  );
}
