// Partners sign in with the kitchen's phone number and a code by SMS.
import { e164, errorMessage, PhoneCountryButton, useCountry, useI18n, useSession, type MarketCountry } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";

import { Split } from "../lib/split";
import { Btn, color, radius, t, textFont } from "../lib/ui";

export default function SignIn() {
  const sendCode = useSession((s) => s.sendCode);
  const { t: tr } = useI18n();
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
      setError(errorMessage((e as { body?: unknown }).body, tr("partner.sign_in.send_failed")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Split>
      <Text testID="sign-in-title" accessibilityRole="header" style={t.big}>{tr("partner.sign_in.title")}</Text>
      <Text style={t.muted}>{tr("partner.sign_in.sub")}</Text>
      <Text style={[t.label, { marginTop: 8 }]}>{tr("partner.sign_in.mobile")}</Text>
      <View style={{ flexDirection: "row", gap: 8 }}>
        <PhoneCountryButton value={country} onChange={setPicked} />
        <TextInput testID="phone" accessibilityLabel={tr("partner.sign_in.mobile")} value={number} onChangeText={setNumber} keyboardType="phone-pad"
          placeholder={tr("signin.mobile")} placeholderTextColor={color.muted} maxLength={14}
          style={[textFont("600"), s.number]} />
      </View>
      {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
      <Btn testID="send-code" title={tr("partner.sign_in.send")} kind="primary" height={56} busy={busy} disabled={!country || digits.length < 6 || digits.length > 15} onPress={send} />
      <Text style={t.muted}>{tr("partner.sign_in.new")}</Text>
    </Split>
  );
}

const s = StyleSheet.create({
  number: { flex: 1, height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 18 },
});
