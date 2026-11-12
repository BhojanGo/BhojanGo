// A partner with several kitchens picks the one this tablet runs (remembered).
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useKitchen } from "../lib/data";
import { color, Icon, Mark, radius, t } from "../lib/ui";

export default function Kitchens() {
  const { kitchens, choose } = useKitchen();
  return (
    <SafeAreaView style={{ flex: 1, alignItems: "center", backgroundColor: color.porcelain }}>
      <View style={{ width: 640, flex: 1, paddingTop: 48, gap: 16 }}>
        <Mark />
        <Text accessibilityRole="header" style={t.big}>Which kitchen is this tablet for?</Text>
        <Text style={t.muted}>New orders for it ring here. You can change it later from Help.</Text>
        <ScrollView contentContainerStyle={{ gap: 12, paddingVertical: 8 }}>
          {(kitchens ?? []).map((k) => (
            <Pressable key={k.id} accessibilityRole="button" accessibilityLabel={k.name}
              onPress={async () => { await choose(k); router.replace(k.status === "active" ? "/orders" : "/apply"); }} style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={t.title}>{k.name}</Text>
                <Text style={t.muted}>{[k.city, k.status === "active" ? "Live" : "Applying"].filter(Boolean).join(" · ")}</Text>
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
