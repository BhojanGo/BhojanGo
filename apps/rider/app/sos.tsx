// SOS: call emergency services, and tell BhojanGo's safety team where you are.
import { api, ApiError, unwrap, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { currentFix } from "../lib/location";
import { night, radius, space, textFont, ui } from "../lib/theme";

export default function Sos() {
  const country = useSession((s) => s.user?.country);
  const emergency = country === "IN" ? "112" : "911";
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
      setMsg(e instanceof ApiError ? e.message : `Couldn't reach the safety team. Call ${emergency}.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={[ui.screen, { padding: space[5], gap: space[4] }]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text accessibilityRole="header" style={[ui.h1, { color: night.sosText }]}>Get help now</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Close" onPress={() => router.back()} style={styles.close}><Icon name="close" /></Pressable>
      </View>
      <Text style={[ui.body, { color: night.muted }]}>If you or anyone else is in danger, call {emergency} first. Then let us know, so we can help and pause your deliveries.</Text>
      <Pressable accessibilityRole="button" onPress={() => Linking.openURL(`tel:${emergency}`)} style={styles.call}>
        <Icon name="phone" stroke={night.text} />
        <Text style={[textFont("800"), { color: night.text, fontSize: 19 }]}>Call {emergency}</Text>
      </Pressable>
      {sent ? (
        <View style={styles.sent} accessibilityLiveRegion="polite">
          <Icon name="shield" stroke={night.link} />
          <Text style={[ui.body, { flex: 1, lineHeight: 21 }]}>
            <Text style={ui.bold}>The safety team has your alert</Text> and your location. Stay somewhere safe; they&apos;ll call you.
          </Text>
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={alertTeam} disabled={busy} style={[ui.outline, { height: 64, borderColor: night.sosBorder }]}>
          <Icon name="alert" stroke={night.sosText} />
          <Text style={[textFont("800"), { color: night.sosText, fontSize: 17 }]}>{busy ? "Sending…" : "Alert BhojanGo safety team"}</Text>
        </Pressable>
      )}
      {msg ? <Text style={[textFont("600"), { color: night.sosText }]}>{msg}</Text> : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  close: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  call: { height: 72, borderRadius: radius.pill, backgroundColor: night.chili, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  sent: { flexDirection: "row", gap: 12, padding: 16, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg, alignItems: "center" },
});
