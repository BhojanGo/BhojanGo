import { DENSE_FONT_SCALE, type, useI18n, useSession } from "@bhojango/mobile-core";
import { Redirect, router, Tabs, type Href } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon, type IconName } from "../../lib/icons";
import { useLive } from "../../lib/rider";
import { night } from "../../lib/theme";

const TABS: { name: "drive" | "earnings" | "account"; icon: IconName }[] = [
  { name: "drive", icon: "drive" },
  { name: "earnings", icon: "wallet" },
  { name: "account", icon: "account" },
];

export default function TabsLayout() {
  const status = useSession((s) => s.status);
  const offered = useLive((s) => s.now?.state.status === "offered" && !!s.now.offer);
  const insets = useSafeAreaInsets();
  const { t: tr } = useI18n();
  if (status !== "signed-in") return <Redirect href="/sign-in" />;

  return (
    <Tabs
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: night.ground } }}
      tabBar={({ state }) =>
        offered ? null : (
          <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
            {TABS.map((t, i) => {
              const on = state.index === i;
              const title = tr(`rider.tabs.${t.name}`);
              return (
                <Pressable key={t.name} testID={`tab-${t.name}`} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={title}
                  onPress={() => router.navigate(`/${t.name}` as Href)} style={styles.tab}>
                  <Icon name={t.icon} stroke={on ? night.kesar : night.muted} />
                  <Text numberOfLines={1} maxFontSizeMultiplier={DENSE_FONT_SCALE} style={[type.small, { color: on ? night.text : night.muted }]}>{title}</Text>
                </Pressable>
              );
            })}
          </View>
        )
      }
    >
      {TABS.map((t) => <Tabs.Screen key={t.name} name={t.name} options={{ title: tr(`rider.tabs.${t.name}`) }} />)}
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: "row", backgroundColor: night.surface, borderTopWidth: 1, borderTopColor: night.line, paddingTop: 8 },
  tab: { flex: 1, alignItems: "center", gap: 2, minHeight: 48, justifyContent: "center" },
});
