// The sign-in frame: a Peacock panel on the left, the form on the right; on a
// phone (portrait) the panel is a band across the top and the form below it.
import { LanguagePill, type, useI18n } from "@bhojango/mobile-core";
import type { ReactNode } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useLayout } from "./layout";
import { color, Mark } from "./ui";

/** On a tablet (PartnerOnboarding.html, 1194 × 834) the brand panel sits beside the
 * form; on a phone held sideways the panel shrinks and the form scrolls; on a phone
 * held upright (lib/layout.ts: narrow) the panel becomes a band above the form. */
export function Split({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { width, height, narrow } = useLayout();
  if (narrow) {
    return (
      <SafeAreaView style={[s.screen, { flexDirection: "column" }]} edges={["left", "right", "bottom"]}>
        <SafeAreaView testID="split-band" edges={["top"]} style={s.band}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Mark size={32} />
            <Text style={[type.label, { color: color.white, flex: 1 }]}>{t("partner.brand")}</Text>
            <LanguagePill />
          </View>
          <Text style={[type.h2, s.hero]}>{t("partner.split.hero")}</Text>
        </SafeAreaView>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={[s.form, { paddingHorizontal: 20, paddingVertical: 24, justifyContent: "flex-start" }]}
          keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
      </SafeAreaView>
    );
  }
  const compact = width < 1000 || height < 600;
  return (
    <SafeAreaView style={s.screen} edges={["left", "right"]}>
      <View style={[s.brand, compact && s.brandCompact]}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Mark size={compact ? 36 : 44} />
          <Text style={[compact ? type.label : type.h3, { color: color.white, flex: 1 }]}>{t("partner.brand")}</Text>
          <LanguagePill />
        </View>
        <Text style={[compact ? type.h1 : type.display, s.hero]}>{t("partner.split.hero")}</Text>
        {compact ? null : (
          <Text style={[type.body, { color: "#CFE3E5" }]}>{t("partner.split.sub")}</Text>
        )}
      </View>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={[s.form, compact && { paddingHorizontal: 32, paddingVertical: 24 }]}
        keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, flexDirection: "row", backgroundColor: color.white },
  brand: { width: "42%", backgroundColor: color.peacock, padding: 48, gap: 32, justifyContent: "center" },
  band: { backgroundColor: color.peacock, paddingHorizontal: 20, paddingBottom: 20, paddingTop: 16, gap: 12 },
  hero: { color: color.white },
  brandCompact: { width: "36%", padding: 28, gap: 16 },
  form: { flexGrow: 1, paddingHorizontal: 72, justifyContent: "center", gap: 16 },
});
