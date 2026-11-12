import { useSession } from "@bhojango/mobile-core";
import { Redirect, router, Tabs, type Href } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon, type IconName } from "../../lib/icons";
import { useLive } from "../../lib/rider";
import { night, textFont } from "../../lib/theme";

const TABS: { name: string; title: string; icon: IconName }[] = [
  { name: "drive", title: "Drive", icon: "drive" },
  { name: "earnings", title: "Earnings", icon: "wallet" },
  { name: "account", title: "Account", icon: "account" },
];

export default function TabsLayout() {
  const status = useSession((s) => s.status);
  const offered = useLive((s) => s.now?.state.status === "offered" && !!s.now.offer);
  const insets = useSafeAreaInsets();
  if (status !== "signed-in") return <Redirect href="/sign-in" />;

  return (
    <Tabs
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: night.ground } }}
      tabBar={({ state }) =>
        offered ? null : (
          <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
            {TABS.map((t, i) => {
              const on = state.index === i;
              return (
                <Pressable key={t.name} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={t.title}
                  onPress={() => router.navigate(`/${t.name}` as Href)} style={styles.tab}>
                  <Icon name={t.icon} stroke={on ? night.kesar : night.muted} />
                  <Text style={[textFont(on ? "800" : "600"), { fontSize: 12, color: on ? night.text : night.muted }]}>{t.title}</Text>
                </Pressable>
              );
            })}
          </View>
        )
      }
    >
      {TABS.map((t) => <Tabs.Screen key={t.name} name={t.name} options={{ title: t.title }} />)}
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: "row", backgroundColor: night.surface, borderTopWidth: 1, borderTopColor: night.line, paddingTop: 8 },
  tab: { flex: 1, alignItems: "center", gap: 2, minHeight: 48, justifyContent: "center" },
});
