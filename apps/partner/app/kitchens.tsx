// A partner with several kitchens picks the one this tablet runs (remembered).
import { SafeAreaView, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useKitchen } from "../lib/data";
import { color, Icon, Mark, radius, t } from "../lib/ui";

export default function Kitchens() {
  const { kitchens, choose } = useKitchen();
  const { t: tr } = useI18n();
  return (
    <SafeAreaView testID="kitchens-screen" style={{ flex: 1, alignItems: "center", backgroundColor: color.porcelain }}>
      <View style={{ width: "100%", maxWidth: 640, flex: 1, paddingTop: 48, paddingHorizontal: 24, gap: 16 }}>
        <Mark />
        <Text accessibilityRole="header" style={t.big}>{tr("partner.kitchens.title")}</Text>
        <Text style={t.muted}>{tr("partner.kitchens.sub")}</Text>
        <ScrollView contentContainerStyle={{ gap: 12, paddingVertical: 8 }}>
          {(kitchens ?? []).map((k) => (
            <Pressable key={k.id} testID={`kitchen-${k.id}`} accessibilityRole="button" accessibilityLabel={k.name}
              onPress={async () => { await choose(k); router.replace(k.status === "active" ? "/orders" : "/apply"); }} style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={t.title}>{k.name}</Text>
                <Text style={t.muted}>{[k.city, k.status === "active" ? tr("partner.kitchens.live") : tr("partner.kitchens.applying")].filter(Boolean).join(" · ")}</Text>
              </View>
              <Icon name="chevron" size={18} />
            </Pressable>
          ))}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: "row", alignItems: "center", padding: 20, borderRadius: radius.card, backgroundColor: color.white,
    borderWidth: 1, borderColor: color.line,
  },
});
