// Partners sign in with the kitchen's phone number and a code by SMS.
import { errorMessage, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { Split } from "../lib/split";
import { Btn, color, radius, t, textFont } from "../lib/ui";

const COUNTRIES = { IN: { code: "+91", label: "IN +91" }, US: { code: "+1", label: "US +1" } } as const;

export default function SignIn() {
  const sendCode = useSession((s) => s.sendCode);
  const [country, setCountry] = useState<"IN" | "US">("IN");
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const c = COUNTRIES[country];
  const digits = number.replace(/\D/g, "");

  async function send() {
    setBusy(true);
    setError(null);
    const phone = `${c.code}${digits}`;
    try {
      await sendCode(phone, country);
      router.push({ pathname: "/code", params: { phone, country } });
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, "We couldn't send a code. Check the number and try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Split>
      <Text accessibilityRole="header" style={t.big}>Sign in to your kitchen</Text>
      <Text style={t.muted}>Use the phone number on your partner account. We&apos;ll text you a code.</Text>
      <Text style={[t.label, { marginTop: 8 }]}>Mobile number</Text>
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Country code, ${country === "IN" ? "India" : "United States"} ${c.code}`}
          onPress={() => setCountry(country === "IN" ? "US" : "IN")} style={s.cc}>
          <Text style={[textFont("800"), { fontSize: 16 }]}>{c.label}</Text>
        </Pressable>
        <TextInput testID="phone" accessibilityLabel="Mobile number" value={number} onChangeText={setNumber} keyboardType="phone-pad"
          placeholder={country === "IN" ? "98480 21234" : "(208) 555-0199"} placeholderTextColor={color.muted} maxLength={14}
          style={[textFont("600"), s.number]} />
      </View>
      {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
      <Btn title="Send code" kind="primary" height={56} busy={busy} disabled={digits.length !== 10} onPress={send} />
      <Text style={t.muted}>Not on BhojanGo yet? Ask your BhojanGo contact for a partner account, then sign in to apply.</Text>
    </Split>
  );
}

const s = StyleSheet.create({
  cc: { height: 56, paddingHorizontal: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, justifyContent: "center" },
  number: { flex: 1, height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 18 },
});
