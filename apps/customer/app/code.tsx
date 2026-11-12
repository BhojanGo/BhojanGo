// CustomerOTP.html: six boxes, filled from the SMS where the phone allows.
import { Button, color, errorMessage, radius, space, textFont, Txt, useSession } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState, type ComponentRef } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";

const RESEND_AFTER = 30;

export default function Code() {
  const { phone, country } = useLocalSearchParams<{ phone: string; country: "IN" | "US" }>();
  const verify = useSession((s) => s.verifyCode);
  const sendCode = useSession((s) => s.sendCode);
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
      router.replace("/home");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, "That code didn't work. Check it and try again."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={styles.back}>
        <Icon name="back" />
      </Pressable>
      <View style={styles.body}>
        <Txt variant="h1" accessibilityRole="header" style={{ fontSize: 30, lineHeight: 33 }}>Enter the 6-digit code</Txt>
        <Txt style={{ color: color.muted }}>
          Sent to <Text style={textFont("800")}>{phone}</Text> ·{" "}
          <Text style={[textFont("700"), { color: color.peacock }]} onPress={() => router.back()}>Edit</Text>
        </Txt>
        <Pressable accessibilityLabel="Verification code" onPress={() => input.current?.focus()} style={styles.boxes}>
          {Array.from({ length: 6 }, (_, i) => (
            <View key={i} style={[styles.box, i === code.length && styles.boxActive]}>
              <Text style={[textFont("800"), { fontSize: 26, color: color.kohl }]}>{code[i] ?? ""}</Text>
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
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Icon name="message" size={18} stroke={color.muted} />
          <Txt variant="small" style={{ color: color.muted }}>We&apos;ll fill it in from the SMS automatically.</Txt>
        </View>
        {error ? <Text style={[textFont("600"), { color: color.chili, fontSize: 14 }]}>{error}</Text> : null}
        <Txt variant="small" style={{ color: color.muted }}>
          Didn&apos;t get it?{" "}
          {wait > 0 ? (
            <Text>Resend in <Text style={textFont("800")}>0:{String(wait).padStart(2, "0")}</Text></Text>
          ) : (
            <Text style={[textFont("700"), { color: color.peacock }]} onPress={() => { void sendCode(phone, country); setWait(RESEND_AFTER); }}>
              Send it again
            </Text>
          )}
        </Txt>
      </View>
      <View style={{ padding: space[5] }}>
        <Button title="Verify" size="lg" block loading={busy} disabled={code.length !== 6} onPress={() => submit()} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.white },
  back: { width: 44, height: 44, margin: space[2], alignItems: "center", justifyContent: "center" },
  body: { flex: 1, paddingHorizontal: space[5], gap: space[4] },
  boxes: { flexDirection: "row", gap: 8, marginTop: space[2] },
  box: {
    flex: 1, height: 60, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong,
    alignItems: "center", justifyContent: "center",
  },
  boxActive: { borderColor: color.peacock, borderWidth: 2 },
  hidden: { position: "absolute", opacity: 0, width: 1, height: 1 },
});
