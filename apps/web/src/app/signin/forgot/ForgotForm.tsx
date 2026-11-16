"use client";
// Forgot password: the email, then "check your email". The answer is the same whether
// or not the email has an account (the API's and this page's), so it can't be used to
// find out who has one.
import Link from "next/link";
import { useState } from "react";

import { useT } from "@/lib/i18n";
import { authError, forgotPassword, looksLikeEmail } from "../emailAuth";
import { EmailField, primaryBtn, textBtn } from "../fields";

export function ForgotForm({ initialEmail }: { initialEmail: string }) {
  const t = useT();
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!looksLikeEmail(email)) return setError(t("auth.err_email"));
    setBusy(true);
    setError(null);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(authError(err, t));
    } finally {
      setBusy(false);
    }
  }

  const back = (
    <Link href="/signin?way=email" className="inline-flex min-h-[44px] items-center gap-[6px] text-label">
      <span aria-hidden="true">←</span> {t("auth.back_to_sign_in")}
    </Link>
  );

  if (sent) {
    return (
      <div>
        {back}
        <h1 className="m-0 mt-2 text-h1">{t("auth.link_sent_heading")}</h1>
        <p role="status" className="m-0 mt-3 text-body text-muted">{t("auth.link_sent", { email: email.trim() })}</p>
        <p className="m-0 mt-3 text-small text-muted">{t("auth.check_spam")}</p>
        <button type="button" onClick={() => setSent(false)} className={`${textBtn} mt-4`}>{t("auth.use_other_email")}</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate>
      {back}
      <h1 className="m-0 mt-2 text-h1">{t("auth.forgot_heading")}</h1>
      <p className="m-0 mt-2 text-body text-muted">{t("auth.forgot_sub")}</p>
      <EmailField value={email} onChange={setEmail} autoFocus />
      {error && <p role="alert" className="m-0 mt-3 text-label text-[#8C1D18]">{error}</p>}
      <button type="submit" disabled={busy} className={primaryBtn}>{busy ? t("auth.sending") : t("auth.send_link")}</button>
    </form>
  );
}
