// The 6-digit code. Only rider accounts get in: anyone else is signed out again.
import { errorMessage, useSession } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState, type ComponentRef } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { night, radius, space, textFont, ui } from "../lib/theme";

const RESEND_AFTER = 30;

export default function Code() {
  const { phone, country } = useLocalSearchParams<{ phone: string; country: "IN" | "US" }>();
  const verify = useSession((s) => s.verifyCode);
  const sendCode = useSession((s) => s.sendCode);
  const signOut = useSession((s) => s.signOut);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wait, setWait] = useState(RESEND_AFTER);
  const input = useRef<ComponentRef<typeof TextInput>>(null);

  useEffect(() => {
    const t = setInterval(() => setWait((w) => (w > 0 ? w - 1 : 0)), 1000);
    return () => clearInterval(t);
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
        setError("This number is a partner or admin account. Use another number to ride.");
        setCode("");
        return;
      }
      router.replace("/drive");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, "That code didn't work. Check it and try again."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={ui.screen}>
      <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={styles.back}>
        <Icon name="back" />
      </Pressable>
      <View style={styles.body}>
        <Text accessibilityRole="header" style={[ui.h1, { fontSize: 30 }]}>Enter the 6-digit code</Text>
        <Text style={[ui.body, { color: night.muted }]}>
          Sent to <Text style={ui.bold}>{phone}</Text> ·{" "}
          <Text style={[textFont("700"), { color: night.link }]} onPress={() => router.back()}>Edit</Text>
        </Text>
        <Pressable accessibilityLabel="Verification code" onPress={() => input.current?.focus()} style={styles.boxes}>
          {Array.from({ length: 6 }, (_, i) => (
            <View key={i} style={[styles.box, i === code.length && styles.boxActive]}>
              <Text style={[ui.bold, { fontSize: 26 }]}>{code[i] ?? ""}</Text>
            </View>
          ))}
        </Pressable>
        <TextInput
          ref={input}
          testID="code"
          accessibilityLabel="Code"
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
        {error ? <Text style={[textFont("600"), { color: night.sosText, fontSize: 14 }]}>{error}</Text> : null}
        <Text style={ui.muted}>
          Didn&apos;t get it?{" "}
          {wait > 0 ? (
            <Text>Resend in <Text style={ui.bold}>0:{String(wait).padStart(2, "0")}</Text></Text>
          ) : (
            <Text style={[textFont("700"), { color: night.link }]} onPress={() => { void sendCode(phone, country); setWait(RESEND_AFTER); }}>
              Send it again
            </Text>
          )}
        </Text>
      </View>
      <View style={{ padding: space[5] }}>
        <Pressable accessibilityRole="button" disabled={code.length !== 6 || busy} onPress={() => submit()}
          style={[ui.cta, { opacity: code.length === 6 && !busy ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? "Checking…" : "Verify"}</Text>
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
