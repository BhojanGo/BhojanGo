// CustomerSignIn.html: phone number, a code by SMS, no password.
import {
  Button, color, e164, errorMessage, LogoMark, PhoneCountryButton, radius, space, textFont, Txt, useCountry, useI18n, useSession,
  type MarketCountry,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

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
    <SafeAreaView style={styles.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <View style={styles.brand}>
          <LogoMark size={34} />
          <Text style={[textFont("700"), styles.word]}>bhojango</Text>
        </View>
        <View style={styles.hero}>
          <Txt variant="hero" style={{ fontSize: 40, lineHeight: 42 }}>Real food.{"\n"}Fair prices.</Txt>
          <Txt style={{ color: color.muted, marginTop: space[3] }}>Every fee shown before you pay.</Txt>
        </View>
        <View style={styles.sheet} accessibilityLabel="Sign in">
          <Txt variant="h1" accessibilityRole="header">Sign in or sign up</Txt>
          <Txt variant="small" style={{ color: color.muted }}>We&apos;ll text you a code. No password needed.</Txt>
          <Text style={[textFont("700"), styles.label]}>Mobile number</Text>
          <View style={styles.phone}>
            <PhoneCountryButton value={country} onChange={setPicked} />
            <TextInput
              testID="phone"
              accessibilityLabel="Mobile number"
              value={number}
              onChangeText={setNumber}
              keyboardType="phone-pad"
              placeholder={t("signin.mobile")}
              placeholderTextColor={color.muted}
              maxLength={14}
              style={[textFont("600"), styles.number]}
            />
          </View>
          {error ? <Text style={[textFont("600"), { color: color.chili, fontSize: 13 }]}>{error}</Text> : null}
          <Button title="Send code" size="lg" block loading={busy} disabled={!country || digits.length < 6 || digits.length > 15} onPress={send} />
          <Txt variant="small" style={{ color: color.muted, textAlign: "center", marginTop: space[2] }}>
            By continuing you agree to our Terms and Privacy notice.
          </Txt>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.peacockMist },
  brand: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: space[5], paddingTop: space[4] },
  word: { fontSize: 24, color: color.kohl, letterSpacing: -0.6 },
  hero: { paddingHorizontal: space[5], paddingTop: 48, flex: 1 },
  sheet: {
    backgroundColor: color.white, borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet,
    padding: space[6], paddingBottom: space[8], gap: space[3],
  },
  label: { fontSize: 14, color: color.kohl, marginTop: space[2] },
  phone: { flexDirection: "row", gap: space[2] },
  number: {
    flex: 1, height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: space[4],
    fontSize: 18, letterSpacing: 0.5, color: color.kohl,
  },
});
