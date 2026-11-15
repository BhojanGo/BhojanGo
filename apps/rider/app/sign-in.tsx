// Riders sign in with their phone and a code by SMS (dark, like the rest of the app).
import {
  e164, errorMessage, field, type MarketCountry, PhoneCountryButton, type, useCountry, useI18n, useSession,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RiderMark } from "../lib/icons";
import { night, radius, space, ui } from "../lib/theme";

export default function SignIn() {
  const sendCode = useSession((s) => s.sendCode);
  const { t } = useI18n();
  // The phone's country: Markets' countries, starting from the current one (tap the box for the next).
  const { country: current, countries, chooseCountry } = useCountry();
  const [picked, setPicked] = useState<MarketCountry | null>(null);
  const country = picked ?? current ?? countries[0] ?? null;
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const digits = number.replace(/\D/g, "");
  const ok = !!country && digits.length >= 6 && digits.length <= 15 && !busy;

  async function send() {
    setBusy(true);
    setError(null);
    if (!country) return;
    const phone = e164(country.phone_code, number);
    try {
      await sendCode(phone, country.code);
      void chooseCountry(country.code);
      router.push({ pathname: "/code", params: { phone, country: country.code } });
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, t("rider.sign_in.send_failed")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView testID="sign-in-screen" style={ui.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.body}>
        <View style={styles.brand}>
          <RiderMark />
          <Text style={ui.bold}>{t("rider.brand")}</Text>
        </View>
        <Text accessibilityRole="header" style={[ui.display, { marginTop: 48 }]}>{t("rider.sign_in.hero")}</Text>
        <Text style={[ui.body, { color: night.muted, marginTop: space[3] }]}>{t("rider.sign_in.sub")}</Text>
        <View style={{ flex: 1 }} />
        <Text style={ui.bold}>{t("rider.sign_in.mobile")}</Text>
        <View style={styles.phone}>
          <PhoneCountryButton tone="dark" value={country} onChange={setPicked} style={styles.cc} />
          <TextInput
            testID="phone"
            accessibilityLabel={t("rider.sign_in.mobile")}
            value={number}
            onChangeText={setNumber}
            keyboardType="phone-pad"
            placeholder={t("signin.mobile")}
            placeholderTextColor={night.muted}
            maxLength={14}
            style={[field.bodyLg, styles.number]}
          />
        </View>
        {error ? <Text style={[type.small, { color: night.sosText }]}>{error}</Text> : null}
        <Pressable testID="send-code" accessibilityRole="button" accessibilityState={{ disabled: !ok }} disabled={!ok} onPress={send}
          style={[ui.cta, { opacity: ok ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? t("rider.sign_in.sending") : t("rider.sign_in.send")}</Text>
        </Pressable>
        <Text style={[ui.muted, { textAlign: "center" }]}>{t("rider.sign_in.hint")}</Text>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  body: { flex: 1, padding: space[5], gap: space[3] },
  brand: { flexDirection: "row", alignItems: "center", gap: 8, height: 44 },
  phone: { flexDirection: "row", gap: space[2] },
  cc: {
    height: 56, paddingHorizontal: space[4], borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong,
    justifyContent: "center", backgroundColor: night.surface,
  },
  number: {
    flex: 1, height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, paddingHorizontal: space[4],
    letterSpacing: 0.5, color: night.text, backgroundColor: night.surface,
  },
});
