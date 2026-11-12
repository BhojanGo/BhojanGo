// The 6-digit code. Only partner accounts get in.
import { errorMessage, useSession } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useRef, useState, type ComponentRef } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useKitchen } from "../lib/data";
import { Split } from "../lib/split";
import { Btn, color, radius, t, textFont } from "../lib/ui";

export default function Code() {
  const { phone, country } = useLocalSearchParams<{ phone: string; country: "IN" | "US" }>();
  const verify = useSession((s) => s.verifyCode);
  const signOut = useSession((s) => s.signOut);
  const loadKitchen = useKitchen((s) => s.load);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<ComponentRef<typeof TextInput>>(null);

  async function submit(value = code) {
    if (value.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      await verify(phone, value, country);
      const role = useSession.getState().user?.role;
      if (role === "customer") {
        router.replace("/join"); // a new number: apply with a kitchen
        return;
      }
      if (role !== "restaurant_owner") {
        await signOut();
        setError("This number is a rider or admin account. Use another number for your kitchen.");
        setCode("");
        return;
      }
      await loadKitchen();
      router.replace("/");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, "That code didn't work. Check it and try again."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Split>
      <Text accessibilityRole="header" style={t.big}>Enter the 6-digit code</Text>
      <Text style={t.muted}>
        Sent to <Text style={textFont("800")}>{phone}</Text> ·{" "}
        <Text style={[textFont("700"), { color: color.peacock }]} onPress={() => router.back()}>Edit</Text>
      </Text>
      <Pressable accessibilityLabel="Verification code" onPress={() => input.current?.focus()} style={{ flexDirection: "row", gap: 10 }}>
        {Array.from({ length: 6 }, (_, i) => (
          <View key={i} style={[s.box, i === code.length && { borderColor: color.peacock, borderWidth: 2 }]}>
            <Text style={[textFont("800"), { fontSize: 28 }]}>{code[i] ?? ""}</Text>
          </View>
        ))}
      </Pressable>
      <TextInput ref={input} testID="code" accessibilityLabel="Code" autoFocus value={code} keyboardType="number-pad"
        textContentType="oneTimeCode" autoComplete="sms-otp" style={s.hidden}
        onChangeText={(v) => {
          const d = v.replace(/\D/g, "").slice(0, 6);
          setCode(d);
          if (d.length === 6) void submit(d);
        }} />
      {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
      <Btn title="Verify" kind="primary" height={56} busy={busy} disabled={code.length !== 6} onPress={() => submit()} />
    </Split>
  );
}

const s = StyleSheet.create({
  box: { width: 64, height: 72, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  hidden: { position: "absolute", opacity: 0, width: 1, height: 1 },
});
