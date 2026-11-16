// CustomerSignIn.html: Phone and Email as two equal ways in (round 8, D5). Phone: a code by
// SMS, no password. Email: a password, an email code, or a new account (EmailSignIn).
import {
  Button, color, e164, EmailSignIn, errorMessage, field, LanguagePill, LogoMark, type MarketCountry, PhoneCountryButton, radius,
  SafeAreaView, SignInWays, type SignInWay, space, Txt, type, useCountry, useI18n, useSession,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { SignInCollage } from "../components/SignInCollage";

export default function SignIn() {
  const sendCode = useSession((s) => s.sendCode);
  const { t } = useI18n();
  // The phone number's country code (not the site's country): Markets' countries, starting from the detected one (tap the box for the next).
  const { country: current, countries } = useCountry();
  const [picked, setPicked] = useState<MarketCountry | null>(null);
  const country = picked ?? current ?? countries[0] ?? null;
  const [way, setWay] = useState<SignInWay>("phone");
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const digits = number.replace(/\D/g, "");

  async function send() {
    setBusy(true);
    setError(null);
    if (!country) return;
    const phone = e164(country.phone_code, number);
    try {
      await sendCode(phone, country.code);
      router.push({ pathname: "/code", params: { phone, country: country.code } });
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, t("signin.send_failed")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
          <View style={styles.brand}>
            <LogoMark size={34} />
            <Text style={[type.h2, styles.word, { flex: 1 }]}>bhojango</Text>
            <LanguagePill />
          </View>
          <View style={styles.hero}>
            <Txt variant="display">{t("common.tagline")}</Txt>
            <Txt style={{ color: color.muted, marginTop: space[3] }}>{t("signin.promise_fees")}</Txt>
            {/* Food photos filling the room down to the sheet (R8: no empty middle on tall phones). */}
            <SignInCollage />
          </View>
          <View style={styles.sheet} accessibilityLabel={t("signin.title")}>
            <Txt variant="h2" accessibilityRole="header">{t("signin.heading")}</Txt>
            <SignInWays value={way} onChange={setWay} />
            {way === "email" ? (
              <EmailSignIn country={country?.code ?? current?.code ?? null} onSignedIn={() => router.replace("/home")} />
            ) : (
              <>
                <Txt variant="small" style={{ color: color.muted }}>{t("signin.help")}</Txt>
                <Text style={[type.label, styles.label]}>{t("signin.mobile")}</Text>
                <View style={styles.phone}>
                  <PhoneCountryButton value={country} onChange={setPicked} />
                  <TextInput
                    testID="phone"
                    accessibilityLabel={t("signin.mobile")}
                    value={number}
                    onChangeText={setNumber}
                    keyboardType="phone-pad"
                    placeholder={t("signin.mobile")}
                    placeholderTextColor={color.muted}
                    maxLength={14}
                    style={[field.bodyLg, styles.number]}
                  />
                </View>
                {error ? <Text style={[type.small, { color: color.chili }]}>{error}</Text> : null}
                <Button title={busy ? t("signin.sending") : t("signin.send_code")} size="lg" block loading={busy}
                  disabled={!country || digits.length < 6 || digits.length > 15} onPress={send} />
              </>
            )}
            <Txt variant="small" style={{ color: color.muted, textAlign: "center", marginTop: space[2] }}>
              {`${t("signin.agree_before")} ${t("signin.terms")} ${t("signin.agree_and")} ${t("signin.privacy")}.`}
            </Txt>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.peacockMist },
  brand: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: space[5], paddingTop: space[4] },
  word: { color: color.kohl },
  hero: { paddingHorizontal: space[5], paddingTop: space[8], paddingBottom: space[6], flex: 1 },
  sheet: {
    backgroundColor: color.white, borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet,
    padding: space[6], paddingBottom: space[8], gap: space[3],
  },
  label: { color: color.kohl, marginTop: space[2] },
  phone: { flexDirection: "row", gap: space[2] },
  number: {
    flex: 1, height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: space[4],
    letterSpacing: 0.5, color: color.kohl,
  },
});
