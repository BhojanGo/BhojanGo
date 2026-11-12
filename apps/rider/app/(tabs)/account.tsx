// Account: who you are, your documents, payouts, safety and sign-out.
import { useSession } from "@bhojango/mobile-core";
import { router, type Href } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon, type IconName } from "../../lib/icons";
import { stopTracking } from "../../lib/location";
import { displayFont, night, space, textFont, ui } from "../../lib/theme";

export default function Account() {
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const rows: { icon: IconName; title: string; detail: string; href: Href }[] = [
    { icon: "document", title: "Documents", detail: "Licence, insurance, background check", href: "/documents" },
    { icon: "bank", title: "Payouts", detail: "Payout account and past weeks", href: "/payouts" },
    { icon: "alert", title: "Safety", detail: "SOS and emergency numbers", href: "/sos" },
  ];
  return (
    <SafeAreaView style={ui.screen} edges={["top"]}>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }}>
        <Text accessibilityRole="header" style={[displayFont("600"), { color: night.text, fontSize: 22 }]}>Account</Text>
        <View style={styles.card}>
          <Text style={[ui.h1, { fontSize: 26 }]}>{user?.full_name}</Text>
          <Text style={ui.muted}>{[user?.phone, user?.country === "IN" ? "India" : "United States"].filter(Boolean).join(" · ")}</Text>
        </View>
        <View style={[styles.card, { padding: 0 }]}>
          {rows.map((r, i) => (
            <Pressable key={r.title} accessibilityRole="button" onPress={() => router.push(r.href)}
              style={[styles.row, i < rows.length - 1 && { borderBottomWidth: 1, borderBottomColor: night.raised }]}>
              <Icon name={r.icon} stroke={night.link} />
              <View style={{ flex: 1 }}>
                <Text style={[ui.bold, { fontSize: 16 }]}>{r.title}</Text>
                <Text style={ui.muted}>{r.detail}</Text>
              </View>
              <Icon name="chevronRight" size={18} />
            </Pressable>
          ))}
        </View>
        <Pressable accessibilityRole="button" onPress={async () => { await stopTracking(); await signOut(); router.replace("/sign-in"); }} style={ui.outline}>
          <Text style={[ui.bold, textFont("700")]}>Sign out</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  card: { padding: 16, borderRadius: 16, backgroundColor: night.surface, gap: 4 },
  row: { flexDirection: "row", alignItems: "center", gap: 14, padding: 16 },
});
