// Round 8, D5: the apps' sign-in has two equal ways in, Phone and Email.
//   SignInWays   the two tabs (BhojanGo: Phone first; Kitchen: Email first; Delivery: Phone first)
//   EmailSignIn  email + password; "Email me a code instead"; "Forgot password?" (a link by
//                email that opens the website); a new account: a password (10+ characters),
//                then the 6-digit code from the email
// The API never says whether an email has an account, so neither do these screens.
import { ApiError } from "@bhojango/api-client";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useI18n, type Translate } from "../i18n";
import { AdminAccountError, emailAuth } from "../session";
import { Button, Input } from "./components";
import { color, dark, radius, space, touch } from "./theme";
import { field, type } from "./type";

export type Way = "phone" | "email";
export type Tone = "light" | "dark";

export function SignInWays({ value, onChange, order = ["phone", "email"], tone = "light" }: {
  value: Way;
  onChange: (w: Way) => void;
  /** Which tab comes first (the app's usual way in); both look the same. */
  order?: Way[];
  tone?: Tone;
}) {
  const { t } = useI18n();
  const d = tone === "dark";
  return (
    <View accessibilityRole="tablist" accessibilityLabel={t("auth.ways_label")} style={[s.ways, d && { backgroundColor: dark.raised }]}>
      {order.map((w) => {
        const on = w === value;
        return (
          <Pressable
            key={w}
            testID={`way-${w}`}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            onPress={() => onChange(w)}
            style={[s.way, on && (d ? { backgroundColor: dark.surface, borderColor: dark.lineStrong, borderWidth: 1 } : s.wayOn)]}
          >
            <Text style={[type.label, { color: on ? (d ? dark.text : color.kohl) : d ? dark.muted : color.muted }]}>
              {t(w === "phone" ? "auth.tab_phone" : "auth.tab_email")}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** The API's answer in the person's words (never a raw message or a stack trace). */
export function authErrorText(err: unknown, t: Translate): string {
  if (err instanceof AdminAccountError) return t("auth.err_admin");
  const code = err instanceof ApiError ? err.code : undefined;
  const retry = err instanceof ApiError ? (err.body as { detail?: { retry_after?: number } } | undefined)?.detail?.retry_after : undefined;
  switch (code) {
    case "INVALID_CREDENTIALS": return t("auth.err_invalid");
    case "ACCOUNT_LOCKED": return t("auth.err_locked", { minutes: Math.max(1, Math.ceil((retry ?? 900) / 60)) });
    case "PASSWORD_TOO_SHORT": return t("auth.err_too_short");
    case "PASSWORD_TOO_LONG": return t("auth.err_too_long");
    case "PASSWORD_LIKE_EMAIL": return t("auth.err_like_email");
    case "PASSWORD_BREACHED": return t("auth.err_breached");
    case "CODE_INVALID": return t("auth.err_code");
    case "TOO_MANY_EMAILS": return t("auth.err_too_many");
    case "ACCOUNT_INACTIVE": return t("auth.err_inactive");
    default:
      if (err instanceof ApiError && err.status === 429) return t("auth.err_too_many");
      return t("auth.err_generic");
  }
}

const looksLikeEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());
type Mode = "signin" | "create" | "code" | "link-sent";
const WAIT = 30;
const clock = () => Date.now();

export function EmailSignIn({ country, onSignedIn, tone = "light", buttonVariant = "primary" }: {
  /** The Markets country a new account belongs to (the detected one). */
  country: string | null;
  onSignedIn: () => void;
  tone?: Tone;
  buttonVariant?: "primary" | "rider";
}) {
  const { t } = useI18n();
  const d = tone === "dark";
  const [mode, setMode] = useState<Mode>("signin");
  const [from, setFrom] = useState<"signin" | "create">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentAt, setSentAt] = useState(0);
  const [now, setNow] = useState(clock);
  const wait = Math.max(0, WAIT - Math.floor(Math.max(0, now - sentAt) / 1000));
  const muted = d ? dark.muted : color.muted;
  const ink = d ? dark.text : color.kohl;
  const linkColor = d ? dark.link : color.peacock;
  const errorColor = d ? "#FFB4AB" : color.chili;

  useEffect(() => {
    if (mode !== "code") return;
    const id = setInterval(() => setNow(clock()), 1000);
    return () => clearInterval(id);
  }, [mode]);

  async function run(work: () => Promise<void>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await work();
      return true;
    } catch (e) {
      setError(authErrorText(e, t));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const go = (m: Mode) => {
    setError(null);
    setMode(m);
  };

  async function signIn() {
    if (!looksLikeEmail(email)) return setError(t("auth.err_email"));
    if (!password) return setError(t("auth.err_password_missing"));
    if (await run(() => emailAuth.signIn(email.trim(), password))) onSignedIn();
  }

  async function create() {
    if (!looksLikeEmail(email)) return setError(t("auth.err_email"));
    if (password.length < 10) return setError(t("auth.err_too_short"));
    if (!country) return setError(t("auth.err_generic"));
    if (await run(() => emailAuth.signUp(email.trim(), password, country))) {
      setFrom("create");
      setSentAt(clock());
      setCode("");
      go("code");
    }
  }

  async function askForCode() {
    if (!looksLikeEmail(email)) return setError(t("auth.err_email"));
    if (await run(() => emailAuth.sendCode(email.trim()))) {
      setFrom("signin");
      setSentAt(clock());
      setCode("");
      go("code");
    }
  }

  async function resend() {
    const again = from === "create" ? () => emailAuth.signUp(email.trim(), password, country ?? "") : () => emailAuth.sendCode(email.trim());
    if (await run(again)) {
      setSentAt(clock());
      setCode("");
    }
  }

  async function verify() {
    if (code.length !== 6) return;
    if (await run(() => emailAuth.verify(email.trim(), code))) onSignedIn();
    else setCode("");
  }

  async function forgot() {
    if (!looksLikeEmail(email)) return setError(t("auth.err_email"));
    if (await run(() => emailAuth.forgot(email.trim()))) go("link-sent");
  }

  const link = (label: string, onPress: () => void, testID?: string) => (
    <Pressable testID={testID} accessibilityRole="button" onPress={onPress} disabled={busy} hitSlop={8} style={s.link}>
      <Text style={[type.label, { color: linkColor }]}>{label}</Text>
    </Pressable>
  );
  const errorLine = error ? <Text accessibilityLiveRegion="polite" accessibilityRole="alert" style={[type.small, { color: errorColor }]}>{error}</Text> : null;
  const emailInput = (
    <Input testID="email" dark={d} label={t("auth.email")} value={email} onChangeText={setEmail} keyboardType="email-address"
      autoCapitalize="none" autoCorrect={false} autoComplete="email" textContentType="emailAddress" returnKeyType="next" />
  );

  if (mode === "link-sent") {
    return (
      <View style={s.stack}>
        <Text accessibilityRole="header" style={[type.h3, { color: ink }]}>{t("auth.link_sent_heading")}</Text>
        <Text style={[type.body, { color: muted }]}>{t("auth.link_sent", { email: email.trim() })}</Text>
        <Text style={[type.small, { color: muted }]}>{t("auth.check_spam")}</Text>
        {link(t("auth.back_to_sign_in"), () => go("signin"), "back-to-sign-in")}
      </View>
    );
  }

  if (mode === "code") {
    return (
      <View style={s.stack}>
        {link(`← ${t("auth.use_other_email")}`, () => go(from))}
        <Text accessibilityRole="header" style={[type.h3, { color: ink }]}>{t("auth.code_heading")}</Text>
        <Text style={[type.body, { color: muted }]}>{t("auth.code_sent", { email: email.trim() })}</Text>
        <Text style={[type.label, { color: ink }]}>{t("auth.code_label")}</Text>
        <TextInput
          testID="email-code"
          accessibilityLabel={t("auth.code_label")}
          value={code}
          onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, 6))}
          keyboardType="number-pad"
          textContentType="oneTimeCode"
          autoComplete="one-time-code"
          maxLength={6}
          autoFocus
          style={[field.bodyLg, s.code, d && { backgroundColor: dark.raised, borderColor: dark.lineStrong, color: dark.text }]}
        />
        <Text style={[type.small, { color: muted }]}>
          {t("auth.check_spam")} {wait > 0 ? t("signin.resend_in", { time: `0:${String(wait).padStart(2, "0")}` }) : ""}
        </Text>
        {wait === 0 ? link(t("auth.resend"), () => void resend()) : null}
        {errorLine}
        <Button testID="email-verify" title={busy ? t("auth.verifying") : t("auth.verify")} variant={buttonVariant} size="lg" block
          loading={busy} disabled={code.length !== 6} onPress={() => void verify()} />
      </View>
    );
  }

  const creating = mode === "create";
  return (
    <View style={s.stack}>
      {creating ? <Text accessibilityRole="header" style={[type.h3, { color: ink }]}>{t("auth.create_heading")}</Text> : null}
      {emailInput}
      <View>
        <Input testID="password" dark={d} label={creating ? t("auth.create_password") : t("auth.password")} value={password}
          onChangeText={setPassword} secureTextEntry={!shown} autoCapitalize="none" autoCorrect={false}
          autoComplete={creating ? "new-password" : "current-password"} textContentType={creating ? "newPassword" : "password"}
          hint={creating ? t("auth.password_hint") : undefined} maxLength={128} />
        <Pressable accessibilityRole="button" accessibilityLabel={shown ? t("auth.hide") : t("auth.show")} onPress={() => setShown((v) => !v)}
          hitSlop={8} style={s.show}>
          <Text style={[type.label, { color: linkColor }]}>{shown ? t("auth.hide") : t("auth.show")}</Text>
        </Pressable>
      </View>
      {!creating ? (
        <View style={s.row}>
          {link(t("auth.email_code_instead"), () => void askForCode(), "email-code-instead")}
          {link(t("auth.forgot"), () => void forgot(), "forgot-password")}
        </View>
      ) : null}
      {errorLine}
      <Button testID={creating ? "create-account" : "email-sign-in"} title={creating ? (busy ? t("auth.creating") : t("auth.create")) : busy ? t("auth.signing_in") : t("auth.sign_in")}
        variant={buttonVariant} size="lg" block loading={busy} onPress={() => void (creating ? create() : signIn())} />
      <View style={s.row}>
        <Text style={[type.small, { color: muted }]}>{creating ? t("auth.have_account") : t("auth.new_here")}</Text>
        {link(creating ? t("auth.sign_in") : t("auth.create_account"), () => go(creating ? "signin" : "create"), creating ? "to-sign-in" : "to-create")}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  ways: { flexDirection: "row", gap: 4, padding: 4, borderRadius: radius.pill, backgroundColor: color.line },
  way: { flex: 1, minHeight: touch.min, alignItems: "center", justifyContent: "center", borderRadius: radius.pill },
  wayOn: { backgroundColor: color.white, shadowColor: "#111418", shadowOpacity: 0.12, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  stack: { gap: space[3] },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", columnGap: space[3] },
  link: { minHeight: touch.min, justifyContent: "center" },
  show: { position: "absolute", right: space[3], top: 30, minHeight: touch.min, justifyContent: "center" },
  code: {
    height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: space[4],
    letterSpacing: 8, color: color.kohl, backgroundColor: color.white,
  },
});
