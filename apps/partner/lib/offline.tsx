// R27: the red, full-width "Not receiving orders: reconnecting" banner over every Kitchen screen
// while the tablet hears nothing from the server (no socket message and no good poll for 15 s:
// lib/board.ts, lib/liveness.ts). It goes away by itself once updates come back. The alarm that
// goes with it is board.ts's. Like the test-site banner (mobile-core WithTestBanner) it takes the
// status bar's inset, and the screens under it get a top inset of 0.
import { color, type, useI18n } from "@bhojango/mobile-core";
import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaInsetsContext, useSafeAreaInsets } from "react-native-safe-area-context";

import { useBoard } from "./board";

export function WithOfflineBanner({ children, watching }: { children: ReactNode; watching: boolean }) {
  const insets = useSafeAreaInsets();
  const offline = useBoard((s) => s.offline) && watching;
  const { t } = useI18n();
  if (!offline) return <>{children}</>;
  return (
    <View style={{ flex: 1 }}>
      <View testID="offline-banner" accessibilityRole="alert" accessibilityLiveRegion="assertive"
        style={[s.banner, { paddingTop: insets.top + 10, paddingLeft: insets.left + 16, paddingRight: insets.right + 16 }]}>
        <View style={s.dot} />
        <Text style={[type.label, s.text]} maxFontSizeMultiplier={1.6}>{t("partner.offline.banner")}</Text>
      </View>
      <SafeAreaInsetsContext.Provider value={{ ...insets, top: 0 }}>
        <View style={{ flex: 1 }}>{children}</View>
      </SafeAreaInsetsContext.Provider>
    </View>
  );
}

const s = StyleSheet.create({
  banner: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, paddingBottom: 10,
    backgroundColor: color.chili, alignSelf: "stretch",
  },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: color.white },
  text: { color: color.white, textAlign: "center", flexShrink: 1 },
});
