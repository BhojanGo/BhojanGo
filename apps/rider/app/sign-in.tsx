// Delivery partners sign in with their phone and a code by SMS (first), or their email
// (round 8, D5); dark, like the rest of the app.
import {
  codeSendErrorText, EmailSignIn, errorMessage, field, LanguagePill, LoadError, type MarketCountry, PhoneCountryButton, phoneExample, phonePlaceholder, SafeAreaView, SignInLegal, type SignInWay, SignInWays, toE164, type, useCountry, useI18n, useSession,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { RiderMark } from "../lib/icons";
import { night, radius, space, ui } from "../lib/theme";

export default function SignIn() {
  const sendCode = useSession((s) => s.sendCode);
  const signOut = useSession((s) => s.signOut);
  const { t } = useI18n();
  const [way, setWay] = useState<SignInWay>("phone");
  // The phone number's country code (not a site country: there is none to choose): Markets' countries, from the detected one.
  const { country: current, countries, error: marketsDown, failure, reload } = useCountry();
  // R9: no countries (the API can't be reached): the error state and Retry, never a form that can't send.
  const unreachable = marketsDown && !countries.length;
  const [picked, setPicked] = useState<MarketCountry | null>(null);
  const country = picked ?? current ?? countries[0] ?? null;
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const digits = number.replace(/\D/g, "");
  const ok = !!country && digits.length >= 6 && digits.length <= 15 && !busy;

  async function send() {
    if (!country) return;
    setBusy(true);
    setError(null);
    const phone = toE164(number, country.code);  // R38: a real number, as E.164
    if (!phone) {
      setError(t("common.phone_invalid", { example: phoneExample(country.code) }));
      setBusy(false);
      return;
    }
    try {
      await sendCode(phone, country.code);
      router.push({ pathname: "/code", params: { phone, country: country.code } });
    } catch (e) {
      setError(codeSendErrorText(e, t, errorMessage((e as { body?: unknown }).body, t("rider.sign_in.send_failed")), country.code));
    } finally {
      setBusy(false);
    }
  }

  // Signed in by email: a new account signs up to deliver; only delivery accounts get in.
  async function signedIn() {
    const role = useSession.getState().user?.role;
    if (role === "customer") {
      router.replace("/join");
      return;
    }
    if (role !== "driver") {
      await signOut();
      setError(t("rider.code.wrong_account"));
      return;
    }
    router.replace("/drive");
  }

  return (
    <SafeAreaView testID="sign-in-screen" style={ui.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <View style={styles.brand}>
          <RiderMark />
          <Text style={[ui.bold, { flex: 1 }]}>{t("rider.brand")}</Text>
          <LanguagePill tone="dark" />
        </View>
        <Text accessibilityRole="header" style={[ui.display, { marginTop: 48 }]}>{t("rider.sign_in.hero")}</Text>
        <Text style={[ui.body, { color: night.muted, marginTop: space[3] }]}>{t("rider.sign_in.sub")}</Text>
        <View style={{ flex: 1, minHeight: space[6] }} />
        {unreachable ? <LoadError error={failure} onRetry={reload} tone="dark" /> : null}
        {unreachable ? null : <SignInWays value={way} onChange={(w) => { setWay(w); setError(null); }} tone="dark" />}
        {unreachable ? null : way === "email" ? (
          <>
            <EmailSignIn country={country?.code ?? null} onSignedIn={() => void signedIn()} tone="dark" buttonVariant="rider" />
            {error ? <Text accessibilityRole="alert" style={[type.small, { color: night.sosText }]}>{error}</Text> : null}
          </>
        ) : (
        <>
        <Text style={ui.bold}>{t("rider.sign_in.mobile")}</Text>
        <View style={styles.phone}>
          <PhoneCountryButton tone="dark" value={country} onChange={setPicked} style={styles.cc} />
          <TextInput
            testID="phone"
            accessibilityLabel={t("rider.sign_in.mobile")}
            value={number}
            onChangeText={setNumber}
            keyboardType="phone-pad"
            placeholder={phonePlaceholder(country?.code)}
            placeholderTextColor={night.muted}
            maxLength={20}
            style={[field.bodyLg, styles.number]}
          />
        </View>
        {error ? <Text style={[type.small, { color: night.sosText }]}>{error}</Text> : null}
        <Pressable testID="send-code" accessibilityRole="button" accessibilityState={{ disabled: !ok }} disabled={!ok} onPress={send}
          style={[ui.cta, { opacity: ok ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? t("rider.sign_in.sending") : t("rider.sign_in.send")}</Text>
        </Pressable>
        <Text style={[ui.muted, { textAlign: "center" }]}>{t("rider.sign_in.hint")}</Text>
        </>
        )}
        {/* R20: the Terms and Privacy policy of the phone number's country, on the website. */}
        {unreachable ? null : <SignInLegal tone="dark" country={country?.code} />}
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  body: { flexGrow: 1, padding: space[5], gap: space[3] },
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
