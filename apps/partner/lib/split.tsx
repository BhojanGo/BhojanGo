// Landscape sign-in frame: a Peacock panel on the left, the form on the right.
import { useI18n } from "@bhojango/mobile-core";
import type { ReactNode } from "react";
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { color, displayFont, Mark, textFont } from "./ui";

/** On a tablet (PartnerOnboarding.html, 1194 × 834) the brand panel sits beside the
 * form; on a phone held sideways the panel shrinks and the form scrolls. */
export function Split({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { width, height } = useWindowDimensions();
  const compact = width < 1000 || height < 600;
  return (
    <SafeAreaView style={s.screen} edges={["left", "right"]}>
      <View style={[s.brand, compact && s.brandCompact]}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Mark size={compact ? 36 : 44} />
          <Text style={[textFont("800"), { color: color.white, fontSize: compact ? 16 : 18 }]}>{t("partner.brand")}</Text>
        </View>
        <Text style={[displayFont("600"), s.hero, compact && { fontSize: 28, lineHeight: 32 }]}>{t("partner.split.hero")}</Text>
        {compact ? null : (
          <Text style={[textFont("400"), { color: "#CFE3E5", fontSize: 16, lineHeight: 24 }]}>{t("partner.split.sub")}</Text>
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
  hero: { color: color.white, fontSize: 44, lineHeight: 48, letterSpacing: -1.2 },
  brandCompact: { width: "36%", padding: 28, gap: 16 },
  form: { flexGrow: 1, paddingHorizontal: 72, justifyContent: "center", gap: 16 },
});
