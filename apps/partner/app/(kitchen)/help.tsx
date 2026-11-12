// Help: who to call, which kitchen this tablet runs, the alert sound, sign out.
import { useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useBoard } from "../../lib/board";
import { useKitchen } from "../../lib/data";
import { Btn, color, radius, t, textFont } from "../../lib/ui";

export default function Help() {
  const { kitchen, kitchens } = useKitchen();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const { muted, mute } = useBoard();
  return (
    <SafeAreaView edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={s.header}><Text accessibilityRole="header" style={t.h1}>Help</Text></View>
      <View style={{ padding: 24, gap: 16, flexDirection: "row", alignItems: "flex-start" }}>
        <View style={[s.panel, { flex: 1 }]}>
          <Text style={[textFont("800"), { fontSize: 17 }]}>Partner support</Text>
          <Text style={t.body}>For a problem with an order, a rider or a payout, contact your BhojanGo partner manager.</Text>
          <Text style={t.muted}>A rejected or late order shows the reason to the customer and is refunded in full.</Text>
        </View>
        <View style={[s.panel, { flex: 1 }]}>
          <Text style={[textFont("800"), { fontSize: 17 }]}>This tablet</Text>
          <Text style={t.body}>{kitchen?.name} · signed in as {user?.full_name}</Text>
          <Text style={t.muted}>New orders ring until you accept or reject them.</Text>
          <Btn title={muted ? "Turn the new-order alert back on" : "Mute the new-order alert"} onPress={() => mute(!muted)} />
          {kitchens && kitchens.length > 1 ? <Btn title="Switch kitchen" onPress={() => router.replace("/kitchens")} /> : null}
          <Btn title="Sign out" kind="danger" onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
        </View>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 12 },
});
