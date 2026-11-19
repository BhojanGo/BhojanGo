// Account and legal (R19, app store review): the country's Privacy policy and Terms
// on the website, and deleting the account (the kitchen closes and leaves BhojanGo;
// the server waits while a payout is still owed or orders are on their way).
// Reached from Help and settings, and from the application screen.
import { DeleteAccount, LegalLinks, SafeAreaView, type, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useKitchen } from "../lib/data";
import { color, Icon, radius, t } from "../lib/ui";

export default function Account() {
  const { t: tr } = useI18n();
  const user = useSession((s) => s.user);
  return (
    <SafeAreaView testID="account-screen" edges={["left", "right", "top"]} style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={s.header}>
        <Pressable testID="account-back" accessibilityRole="button" accessibilityLabel={tr("common.back")} onPress={() => router.back()} style={s.back}>
          <Icon name="back" />
        </Pressable>
        <Text accessibilityRole="header" style={t.h1}>{tr("partner.account.title")}</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16, width: "100%", maxWidth: 720, alignSelf: "center" }}>
        <View testID="legal-section" style={s.panel}>
          <Text accessibilityRole="header" style={type.h3}>{tr("account.legal.title")}</Text>
          <LegalLinks country={user?.country} />
        </View>
        <View testID="delete-section" style={s.panel}>
          <Text accessibilityRole="header" style={type.h3}>{tr("partner.account.delete")}</Text>
          <DeleteAccount body={tr("account.delete.kitchen_body")} note={tr("account.delete.kitchen_note")}
            onDeleted={() => { useKitchen.setState({ kitchens: null, kitchen: null }); router.replace("/sign-in"); }} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  header: {
    minHeight: 80, paddingHorizontal: 16, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line,
    flexDirection: "row", alignItems: "center", gap: 8,
  },
  back: { width: 48, height: 48, alignItems: "center", justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 12 },
});
