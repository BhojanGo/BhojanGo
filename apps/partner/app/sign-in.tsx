// Kitchen partners sign in with their email (first: the kitchen's account is an email
// and a password) or the kitchen's phone and a code by SMS (round 8, D5).
import {
  codeSendErrorText,
  EmailSignIn,
  errorMessage,
  field,
  LoadError,
  PhoneCountryButton,
  phoneExample,
  phonePlaceholder,
  reformatPhone,
  SignInLegal,
  SignInWays,
  toE164,
  type,
  type MarketCountry,
  type SignInWay,
  typePhone,
  useCountry,
  useI18n,
  useSession,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";

import { useKitchen } from "../lib/data";
import { Split } from "../lib/split";
import { Btn, color, radius, t } from "../lib/ui";

export default function SignIn() {
  const sendCode = useSession((s) => s.sendCode);
  const signOut = useSession((s) => s.signOut);
  const loadKitchen = useKitchen((s) => s.load);
  const { t: tr } = useI18n();
  // The phone number's country code (not a site country: there is none to choose): Markets' countries, from the detected one.
  const { country: current, countries, error: marketsDown, failure, reload } = useCountry();
  // R9: no countries (the API can't be reached): the error state and Retry, never a form that can't send.
  const unreachable = marketsDown && !countries.length;
  const [picked, setPicked] = useState<MarketCountry | null>(null);
  const country = picked ?? current ?? countries[0] ?? null;
  const [way, setWay] = useState<SignInWay>("email");
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const digits = number.replace(/\D/g, "");

  async function send() {
    if (!country) return;
    setBusy(true);
    setError(null);
    const phone = toE164(number, country.code);  // R38: a real number, as E.164
    if (!phone) {
      setError(tr("common.phone_invalid", { example: phoneExample(country.code) }));
      setBusy(false);
      return;
    }
    try {
      await sendCode(phone, country.code);
      router.push({ pathname: "/code", params: { phone, country: country.code } });
    } catch (e) {
      setError(codeSendErrorText(e, tr, errorMessage((e as { body?: unknown }).body, tr("partner.sign_in.send_failed")), country.code));
    } finally {
      setBusy(false);
    }
  }

  // Signed in by email: a new account applies with a kitchen; only kitchen accounts get in.
  async function signedIn() {
    const role = useSession.getState().user?.role;
    if (role === "customer") {
      router.replace("/join");
      return;
    }
    if (role !== "restaurant_owner") {
      await signOut();
      setError(tr("partner.code.wrong_account"));
      return;
    }
    await loadKitchen();
    router.replace("/");
  }

  return (
    <Split>
      <Text testID="sign-in-title" accessibilityRole="header" style={t.big}>{tr("partner.sign_in.title")}</Text>
      {unreachable ? <LoadError error={failure} onRetry={reload} /> : null}
      {unreachable ? null : <SignInWays value={way} onChange={(w) => { setWay(w); setError(null); }} order={["email", "phone"]} />}
      {unreachable ? null : way === "email" ? (
        <>
          <EmailSignIn country={country?.code ?? null} onSignedIn={() => void signedIn()} />
          {error ? <Text accessibilityRole="alert" style={[type.small, { color: color.chili }]}>{error}</Text> : null}
        </>
      ) : (
        <>
          <Text style={t.muted}>{tr("partner.sign_in.sub")}</Text>
          <Text style={[t.label, { marginTop: 8 }]}>{tr("partner.sign_in.mobile")}</Text>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <PhoneCountryButton value={country} onChange={(c) => { setPicked(c); setNumber((n) => reformatPhone(n, c?.code)); }} />
            <TextInput disableFullscreenUI testID="phone" accessibilityLabel={tr("partner.sign_in.mobile")} value={number} onChangeText={(v) => setNumber((n) => typePhone(n, v, country?.code))} keyboardType="phone-pad"
              placeholder={phonePlaceholder(country?.code)} placeholderTextColor={color.muted} maxLength={20}
              style={[field.bodyLg, s.number]} />
          </View>
          {error ? <Text style={[type.small, { color: color.chili }]}>{error}</Text> : null}
          <Btn testID="send-code" title={tr("partner.sign_in.send")} kind="primary" height={56} busy={busy} disabled={!country || digits.length < 6 || digits.length > 15} onPress={send} />
          <Text style={t.muted}>{tr("partner.sign_in.new")}</Text>
        </>
      )}
      {/* R20: the Terms and Privacy policy of the phone number's country, on the website. */}
      {unreachable ? null : <SignInLegal country={country?.code} style={{ marginTop: 8 }} />}
    </Split>
  );
}

const s = StyleSheet.create({
  number: { flex: 1, height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16 },
});
