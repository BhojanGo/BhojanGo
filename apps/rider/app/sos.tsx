// SOS: call emergency services, and tell BhojanGo's safety team where you are.
// The emergency number is the rider's country's (Markets settings
// `emergency_number`, in GET /markets/directory); a country without one gets
// "your local emergency number" and no call button rather than a guess.
import { api, ApiError, SafeAreaView, type, unwrap, useCountry, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { currentFix } from "../lib/location";
import { night, radius, space, ui } from "../lib/theme";

export default function Sos() {
  const { t } = useI18n();
  const { country } = useCountry(); // the rider's account country (useKnownCountry in the root layout)
  const emergency = country?.emergency_number ?? null;
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function alertTeam() {
    setBusy(true);
    setMsg(null);
    try {
      const fix = await currentFix().catch(() => null);
      unwrap(await api.realtime.POST("/api/v1/riders/me/sos", { body: { ...(fix ?? {}), note: null } }));
      setSent(true);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : emergency ? t("rider.sos.failed", { number: emergency }) : t("rider.sos.failed_local"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView testID="sos-screen" style={[ui.screen, { padding: space[5], gap: space[4] }]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text accessibilityRole="header" style={[ui.h1, { color: night.sosText, flex: 1 }]}>{t("rider.sos.title")}</Text>
        <Pressable testID="sos-close" accessibilityRole="button" accessibilityLabel={t("common.close")} onPress={() => router.back()} style={styles.close}>
          <Icon name="close" />
        </Pressable>
      </View>
      <Text style={[ui.body, { color: night.muted }]}>{emergency ? t("rider.sos.intro", { number: emergency }) : t("rider.sos.intro_local")}</Text>
      {emergency ? (
        <Pressable testID="sos-call" accessibilityRole="button" onPress={() => Linking.openURL(`tel:${emergency}`)} style={styles.call}>
          <Icon name="phone" stroke={night.text} />
          <Text style={[type.h3, { color: night.text }]}>{t("rider.sos.call", { number: emergency })}</Text>
        </Pressable>
      ) : null}
      {sent ? (
        <View testID="sos-sent" style={styles.sent} accessibilityLiveRegion="polite">
          <Icon name="shield" stroke={night.link} />
          <Text style={[ui.body, { flex: 1, lineHeight: 21 }]}>
            <Text style={ui.bold}>{t("rider.sos.sent_title")}</Text> {t("rider.sos.sent_body")}
          </Text>
        </View>
      ) : (
        <Pressable testID="sos-alert" accessibilityRole="button" onPress={alertTeam} disabled={busy} style={[ui.outline, { height: 64, borderColor: night.sosBorder }]}>
          <Icon name="alert" stroke={night.sosText} />
          <Text style={[type.h3, { color: night.sosText }]}>{busy ? t("rider.sos.sending") : t("rider.sos.alert")}</Text>
        </Pressable>
      )}
      {msg ? <Text style={[type.small, { color: night.sosText }]}>{msg}</Text> : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  close: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  call: { height: 72, borderRadius: radius.pill, backgroundColor: night.chili, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  sent: { flexDirection: "row", gap: 12, padding: 16, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg, alignItems: "center" },
});
