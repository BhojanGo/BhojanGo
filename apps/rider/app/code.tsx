// The 6-digit code. Only rider accounts get in: anyone else is signed out again.
import { errorMessage, type, useI18n, useSession } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState, type ComponentRef } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { night, radius, space, textFont, ui } from "../lib/theme";

const RESEND_AFTER = 30;

export default function Code() {
  const { phone, country } = useLocalSearchParams<{ phone: string; country: string }>();
  const verify = useSession((s) => s.verifyCode);
  const sendCode = useSession((s) => s.sendCode);
  const signOut = useSession((s) => s.signOut);
  const { t } = useI18n();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wait, setWait] = useState(RESEND_AFTER);
  const input = useRef<ComponentRef<typeof TextInput>>(null);

  useEffect(() => {
    const timer = setInterval(() => setWait((w) => (w > 0 ? w - 1 : 0)), 1000);
    return () => clearInterval(timer);
  }, []);

  async function submit(value = code) {
    if (value.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      await verify(phone, value, country);
      const role = useSession.getState().user?.role;
      if (role === "customer") {
        router.replace("/join"); // a new number: sign up to ride
        return;
      }
      if (role !== "driver") {
        await signOut();
        setError(t("rider.code.wrong_account"));
        setCode("");
        return;
      }
      router.replace("/drive");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, t("rider.code.failed")));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView testID="code-screen" style={ui.screen}>
      <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}>
        <Icon name="back" />
      </Pressable>
      <View style={styles.body}>
        <Text accessibilityRole="header" style={ui.h1}>{t("rider.code.title")}</Text>
        <Text style={[ui.body, { color: night.muted }]}>
          {t("rider.code.sent_to")} <Text style={[textFont("700"), { color: night.text }]}>{phone}</Text> ·{" "}
          <Text style={[textFont("700"), { color: night.link }]} onPress={() => router.back()}>{t("rider.code.edit")}</Text>
        </Text>
        <Pressable accessibilityLabel={t("rider.code.label")} onPress={() => input.current?.focus()} style={styles.boxes}>
          {Array.from({ length: 6 }, (_, i) => (
            <View key={i} style={[styles.box, i === code.length && styles.boxActive]}>
              <Text style={ui.h2}>{code[i] ?? ""}</Text>
            </View>
          ))}
        </Pressable>
        <TextInput
          ref={input}
          testID="code"
          accessibilityLabel={t("rider.code.label")}
          autoFocus
          value={code}
          onChangeText={(v) => {
            const digits = v.replace(/\D/g, "").slice(0, 6);
            setCode(digits);
            if (digits.length === 6) void submit(digits);
          }}
          keyboardType="number-pad"
          textContentType="oneTimeCode"
          autoComplete="sms-otp"
          style={styles.hidden}
        />
        {error ? <Text style={[type.label, { color: night.sosText }]}>{error}</Text> : null}
        <Text style={ui.muted}>
          {t("rider.code.not_received")}{" "}
          {wait > 0 ? (
            <Text>{t("rider.code.resend_in")} <Text style={[textFont("700"), { color: night.text }]}>0:{String(wait).padStart(2, "0")}</Text></Text>
          ) : (
            <Text style={[textFont("700"), { color: night.link }]} onPress={() => { void sendCode(phone, country); setWait(RESEND_AFTER); }}>
              {t("rider.code.send_again")}
            </Text>
          )}
        </Text>
      </View>
      <View style={{ padding: space[5] }}>
        <Pressable testID="verify" accessibilityRole="button" disabled={code.length !== 6 || busy} onPress={() => submit()}
          style={[ui.cta, { opacity: code.length === 6 && !busy ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? t("rider.code.checking") : t("rider.code.verify")}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  back: { width: 44, height: 44, margin: space[2], alignItems: "center", justifyContent: "center" },
  body: { flex: 1, paddingHorizontal: space[5], gap: space[4] },
  boxes: { flexDirection: "row", gap: 8, marginTop: space[2] },
  box: {
    flex: 1, height: 60, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, backgroundColor: night.surface,
    alignItems: "center", justifyContent: "center",
  },
  boxActive: { borderColor: night.kesar, borderWidth: 2 },
  hidden: { position: "absolute", opacity: 0, width: 1, height: 1 },
});
