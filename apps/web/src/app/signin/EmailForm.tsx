"use client";
// The Email tab of /signin (round 8, D5):
//   sign in   email + password; "Email me a code instead"; "Forgot password?"
//   create    email + a new password (10+ characters) -> a 6-digit code by email
//   code      the code from either; then back to where they were
// The API never says whether an email has an account, so neither does this page:
// a new visitor picks "Create an account" themselves.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { useT } from "@/lib/i18n";
import { placeFromDefaultAddress } from "./afterSignIn";
import {
  authError, looksLikeEmail, MIN_PASSWORD, sendEmailCode, signInWithPassword, signUp, verifyEmailCode,
} from "./emailAuth";
import { CodeBoxes, EmailField, PasswordField, primaryBtn, textBtn } from "./fields";

type Mode = "signin" | "create" | "code";
const WAIT = 30; // seconds before "Send a new code"

export function EmailForm({ country, next, hasPlace, initialMode = "signin" }: {
  country: string | null; next: string; hasPlace: boolean; initialMode?: "signin" | "create";
}) {
  const t = useT();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [from, setFrom] = useState<"signin" | "create">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [boxesKey, setBoxesKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentAt, setSentAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const errorId = useId();
  const emailOk = looksLikeEmail(email);
  const wait = Math.max(0, WAIT - Math.floor(Math.max(0, now - sentAt) / 1000));

  useEffect(() => {
    if (mode !== "code") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [mode]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError(authError(err, t));
      setBusy(false);
      return false;
    }
    setBusy(false);
    return true;
  }

  async function done() {
    await placeFromDefaultAddress(hasPlace);
    router.replace(next);
    router.refresh();
  }

  async function submitSignIn(e: React.FormEvent) {
    e.preventDefault();
    if (!emailOk || !password) return setError(t(!emailOk ? "auth.err_email" : "auth.err_password_missing"));
    if (await run(() => signInWithPassword(email.trim(), password))) await done();
  }

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!emailOk) return setError(t("auth.err_email"));
    if (password.length < MIN_PASSWORD) return setError(t("auth.err_too_short"));
    if (!country) return setError(t("auth.err_generic"));
    if (await run(() => signUp(email.trim(), password, country))) {
      setFrom("create");
      setSentAt(Date.now());
      setMode("code");
    }
  }

  async function askForCode() {
    if (!emailOk) return setError(t("auth.err_email"));
    if (await run(() => sendEmailCode(email.trim()))) {
      setFrom("signin");
      setSentAt(Date.now());
      setMode("code");
    }
  }

  async function resend() {
    const again = from === "create" ? () => signUp(email.trim(), password, country ?? "") : () => sendEmailCode(email.trim());
    if (await run(again)) {
      setSentAt(Date.now());
      setCode("");
      setBoxesKey((k) => k + 1);
    }
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    if (code.length !== 6) return;
    if (await run(() => verifyEmailCode(email.trim(), code))) return done();
    setCode("");
    setBoxesKey((k) => k + 1);
  }

  const errorBox = error && <p id={errorId} role="alert" className="m-0 mt-3 text-label text-[#8C1D18]">{error}</p>;

  if (mode === "code") {
    return (
      <form onSubmit={submitCode} noValidate aria-labelledby="email-code-heading">
        <button type="button" onClick={() => { setMode(from); setError(null); }} className="inline-flex min-h-[44px] items-center gap-[6px] text-label">
          <span aria-hidden="true">←</span> {t("auth.use_other_email")}
        </button>
        <h2 id="email-code-heading" className="m-0 mt-2 text-h2">{t("auth.code_heading")}</h2>
        <p className="m-0 mt-1 text-body text-muted">{t("auth.code_sent", { email: email.trim() })}</p>
        <CodeBoxes key={boxesKey} onChange={setCode} legend={t("auth.code_label")} />
        <p className="m-0 mt-4 text-small text-muted" aria-live="polite">
          {t("auth.check_spam")}{" "}
          {wait > 0 ? (
            <b className="text-[#111418]">{t("signin.resend_in", { time: `0:${String(wait).padStart(2, "0")}` })}</b>
          ) : (
            <button type="button" onClick={() => void resend()} disabled={busy} className="font-bold text-[#0B5D66]">{t("auth.resend")}</button>
          )}
        </p>
        {errorBox}
        <button type="submit" disabled={code.length !== 6 || busy} className={primaryBtn}>
          {busy ? t("auth.verifying") : t("auth.verify")}
        </button>
      </form>
    );
  }

  if (mode === "create") {
    return (
      <form onSubmit={submitCreate} noValidate aria-labelledby="create-heading">
        <h2 id="create-heading" className="m-0 mt-6 text-h3">{t("auth.create_heading")}</h2>
        <EmailField value={email} onChange={setEmail} autoFocus describedBy={error ? errorId : undefined} />
        <PasswordField label={t("auth.create_password")} value={password} onChange={setPassword} isNew hint={t("auth.password_hint")} />
        {errorBox}
        <button type="submit" disabled={busy} className={primaryBtn}>{busy ? t("auth.creating") : t("auth.create")}</button>
        <p className="m-0 mt-4 text-small text-muted">
          {t("auth.have_account")}{" "}
          <button type="button" onClick={() => { setMode("signin"); setError(null); }} className={textBtn}>{t("auth.sign_in")}</button>
        </p>
      </form>
    );
  }

  return (
    <form onSubmit={submitSignIn} noValidate>
      <EmailField value={email} onChange={setEmail} autoFocus describedBy={error ? errorId : undefined} />
      <PasswordField label={t("auth.password")} value={password} onChange={setPassword} />
      <div className="mt-1 flex flex-wrap justify-between gap-x-4">
        <button type="button" onClick={() => void askForCode()} disabled={busy} className={textBtn}>{t("auth.email_code_instead")}</button>
        <Link href={`/signin/forgot${looksLikeEmail(email) ? `?email=${encodeURIComponent(email.trim())}` : ""}`}
          className={`${textBtn} inline-flex items-center`}>{t("auth.forgot")}</Link>
      </div>
      {errorBox}
      <button type="submit" disabled={busy} className={primaryBtn}>{busy ? t("auth.signing_in") : t("auth.sign_in")}</button>
      <p className="m-0 mt-4 text-small text-muted">
        {t("auth.new_here")}{" "}
        <button type="button" onClick={() => { setMode("create"); setError(null); }} className={textBtn}>{t("auth.create_account")}</button>
      </p>
    </form>
  );
}
