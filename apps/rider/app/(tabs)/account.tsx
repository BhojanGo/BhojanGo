// Account: who you are, your language (the country's, from Markets), documents,
// payouts, safety, legal (the country's Privacy policy and Terms on the website),
// sign-out and deleting the account (R19: location sharing stops first).
import { DeleteAccount, formatPhone, LanguagePicker, LegalLinks, SafeAreaView, type, useCountry, useI18n, useSession } from "@bhojango/mobile-core";
import { router, type Href } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon, type IconName } from "../../lib/icons";
import { startTracking, stopTracking, trackingHere } from "../../lib/location";
import { night, space, ui } from "../../lib/theme";

/** Was this phone sharing its location when deleting started (to restart it if the server says no)? */
let wasSharing = false;

export default function Account() {
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const { t } = useI18n();
  const { countries } = useCountry();
  const countryName = countries.find((c) => c.code === user?.country)?.name ?? user?.country;
  const rows: { key: string; icon: IconName; title: string; detail: string; href: Href }[] = [
    { key: "documents", icon: "document", title: t("rider.account.documents"), detail: t("rider.account.documents_detail"), href: "/documents" },
    { key: "payouts", icon: "bank", title: t("rider.account.payouts"), detail: t("rider.account.payouts_detail"), href: "/payouts" },
    { key: "safety", icon: "alert", title: t("rider.account.safety"), detail: t("rider.account.safety_detail"), href: "/sos" },
  ];
  return (
    <SafeAreaView style={ui.screen} edges={["top"]}>
      <ScrollView testID="account-screen" contentContainerStyle={{ padding: space[5], gap: space[4], paddingBottom: space[8] }}>
        <Text testID="account-title" accessibilityRole="header" style={[type.h2, { color: night.text }]}>
          {t("rider.account.title")}
        </Text>
        <View style={styles.card}>
          <Text style={ui.h2}>{user?.full_name}</Text>
          <Text testID="account-phone" style={ui.muted}>{[user?.phone ? formatPhone(user.phone) : null, countryName].filter(Boolean).join(" · ")}</Text>
        </View>
        <View style={[styles.card, { padding: 0 }]}>
          {rows.map((r, i) => (
            <Pressable key={r.key} testID={`account-${r.key}`} accessibilityRole="button" onPress={() => router.push(r.href)}
              style={[styles.row, i < rows.length - 1 && { borderBottomWidth: 1, borderBottomColor: night.raised }]}>
              <Icon name={r.icon} stroke={night.link} />
              <View style={{ flex: 1 }}>
                <Text style={ui.bold}>{r.title}</Text>
                <Text style={ui.muted}>{r.detail}</Text>
              </View>
              <Icon name="chevronRight" size={18} />
            </Pressable>
          ))}
        </View>
        <View testID="language-section" style={[styles.card, { gap: space[3] }]}>
          <Text accessibilityRole="header" style={ui.bold}>{t("rider.account.language")}</Text>
          <LanguagePicker tone="dark" />
        </View>
        <Pressable testID="sign-out" accessibilityRole="button" onPress={async () => { await stopTracking(); await signOut(); router.replace("/sign-in"); }} style={ui.outline}>
          <Text style={ui.bold}>{t("rider.account.sign_out")}</Text>
        </Pressable>
        <Text style={[ui.muted, { textAlign: "center" }]}>{t("rider.account.sign_out_note")}</Text>
        <View testID="legal-section" style={[styles.card, { paddingVertical: space[2] }]}>
          <Text accessibilityRole="header" style={[ui.bold, { paddingTop: space[2] }]}>{t("rider.account.legal")}</Text>
          <LegalLinks tone="dark" country={user?.country} />
        </View>
        <View testID="delete-section" style={[styles.card, { gap: space[3] }]}>
          <Text accessibilityRole="header" style={ui.bold}>{t("rider.account.delete")}</Text>
          <DeleteAccount tone="dark" body={t("account.delete.delivery_body")} note={t("account.delete.delivery_note")}
            // Location sharing stops before the account goes; if the server keeps it (a payout
            // still owed, a delivery on its way), sharing starts again where it was on.
            before={async () => { wasSharing = await trackingHere(); await stopTracking(); }}
            undo={async () => { if (wasSharing) await startTracking(); }}
            onDeleted={() => router.replace("/sign-in")} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  card: { padding: 16, borderRadius: 16, backgroundColor: night.surface, gap: 4 },
  row: { flexDirection: "row", alignItems: "center", gap: 14, padding: 16 },
});
