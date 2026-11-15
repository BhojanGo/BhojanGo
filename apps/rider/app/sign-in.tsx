// Riders sign in with their phone and a code by SMS (dark, like the rest of the app).
import { e164, errorMessage, PhoneCountryButton, useCountry, useI18n, useSession, type MarketCountry } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RiderMark } from "../lib/icons";
import { night, radius, space, textFont, ui } from "../lib/theme";

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
      setError(errorMessage((e as { body?: unknown }).body, "We couldn't send a code. Check the number and try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={ui.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.body}>
        <View style={styles.brand}>
          <RiderMark />
          <Text style={[ui.bold, { fontSize: 15, ...textFont("700") }]}>BhojanGo Rider</Text>
        </View>
        <Text accessibilityRole="header" style={[ui.h1, { marginTop: 48, fontSize: 40, lineHeight: 42 }]}>Ride on your{"\n"}own hours.</Text>
        <Text style={[ui.body, { color: night.muted, marginTop: space[3] }]}>
          See the full pay before you accept. Tips are 100% yours.
        </Text>
        <View style={{ flex: 1 }} />
        <Text style={[ui.bold, { fontSize: 14, ...textFont("700") }]}>Mobile number</Text>
        <View style={styles.phone}>
          <PhoneCountryButton tone="dark" value={country} onChange={setPicked} style={styles.cc} />
          <TextInput
            testID="phone"
            accessibilityLabel="Mobile number"
            value={number}
            onChangeText={setNumber}
            keyboardType="phone-pad"
            placeholder={t("signin.mobile")}
            placeholderTextColor={night.muted}
            maxLength={14}
            style={[textFont("600"), styles.number]}
          />
        </View>
        {error ? <Text style={[textFont("600"), { color: night.sosText, fontSize: 13 }]}>{error}</Text> : null}
        <Pressable accessibilityRole="button" accessibilityState={{ disabled: !ok }} disabled={!ok} onPress={send}
          style={[ui.cta, { opacity: ok ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? "Sending…" : "Send code"}</Text>
        </Pressable>
        <Text style={[ui.muted, { textAlign: "center" }]}>Sign in with the number you applied with.</Text>
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
    fontSize: 18, letterSpacing: 0.5, color: night.text, backgroundColor: night.surface,
  },
});
