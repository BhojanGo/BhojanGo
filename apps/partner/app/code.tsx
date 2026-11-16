// The 6-digit code. Only partner accounts get in.
import { errorMessage, formatPhone, num, type, useI18n, useSession } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useRef, useState, type ComponentRef } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useKitchen } from "../lib/data";
import { useLayout } from "../lib/layout";
import { Split } from "../lib/split";
import { Btn, color, radius, t, textFont } from "../lib/ui";

export default function Code() {
  const { phone, country } = useLocalSearchParams<{ phone: string; country: string }>();
  const verify = useSession((s) => s.verifyCode);
  const signOut = useSession((s) => s.signOut);
  const loadKitchen = useKitchen((s) => s.load);
  const { t: tr } = useI18n();
  const { narrow } = useLayout(); // a phone: six smaller boxes fit its width
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
        setError(tr("partner.code.wrong_account"));
        setCode("");
        return;
      }
      await loadKitchen();
      router.replace("/");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, tr("partner.code.failed")));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Split>
      <Text accessibilityRole="header" style={t.big}>{tr("partner.code.title")}</Text>
      <Text style={t.muted}>
        {tr("partner.code.sent_to")} <Text style={textFont("700")}>{formatPhone(phone)}</Text> ·{" "}
        <Text style={[textFont("700"), { color: color.peacock }]} onPress={() => router.back()}>{tr("partner.code.edit")}</Text>
      </Text>
      <Pressable accessibilityLabel={tr("partner.code.label")} onPress={() => input.current?.focus()} style={{ flexDirection: "row", gap: narrow ? 8 : 10 }}>
        {Array.from({ length: 6 }, (_, i) => (
          <View key={i} style={[s.box, narrow && { width: 46, height: 58 }, i === code.length && { borderColor: color.peacock, borderWidth: 2 }]}>
            <Text style={[narrow ? type.h2 : type.h1, num]}>{code[i] ?? ""}</Text>
          </View>
        ))}
      </Pressable>
      <TextInput disableFullscreenUI ref={input} testID="code" accessibilityLabel={tr("partner.code.label")} autoFocus value={code} keyboardType="number-pad"
        textContentType="oneTimeCode" autoComplete="sms-otp" style={s.hidden}
        onChangeText={(v) => {
          const d = v.replace(/\D/g, "").slice(0, 6);
          setCode(d);
          if (d.length === 6) void submit(d);
        }} />
      {error ? <Text style={[type.small, { color: color.chili }]}>{error}</Text> : null}
      <Btn testID="verify" title={tr("partner.code.verify")} kind="primary" height={56} busy={busy} disabled={code.length !== 6} onPress={() => submit()} />
    </Split>
  );
}

const s = StyleSheet.create({
  box: { width: 56, height: 68, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  hidden: { position: "absolute", opacity: 0, width: 1, height: 1 },
});
