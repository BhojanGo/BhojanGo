"use client";
// Choose a new password with the emailed link: the link is checked first (expired or used
// links say so at once), then the new password (10+ characters, not breached). Saving
// signs the account out everywhere; then sign in with the new one.
import { ApiError } from "@bhojango/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useT } from "@/lib/i18n";
import { authError, MIN_PASSWORD, resetLinkWorks, resetPassword } from "../emailAuth";
import { PasswordField, primaryBtn } from "../fields";

type State = "checking" | "invalid" | "form" | "done";

export function ResetForm({ token }: { token: string }) {
  const t = useT();
  const [state, setState] = useState<State>(token.length >= 20 ? "checking" : "invalid");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token.length < 20) return;
    resetLinkWorks(token)
      .then((ok) => setState(ok ? "form" : "invalid"))
      .catch(() => setState("form")); // can't tell: let them try; saving says if it has expired
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(t("auth.err_too_short"));
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setState("done");
    } catch (err) {
      if (err instanceof ApiError && err.code === "RESET_LINK_INVALID") setState("invalid");
      else setError(authError(err, t));
    } finally {
      setBusy(false);
    }
  }

  if (state === "checking") {
    return (
      <div role="status" aria-live="polite" className="flex items-center gap-3 text-body text-[#3D4A4E]">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-[#C9D3D4] border-t-[#0B5D66]" aria-hidden="true" />
        {t("auth.checking_link")}
      </div>
    );
  }

  if (state === "invalid") {
    return (
      <div>
        <h1 className="m-0 text-h1 tracking-[-0.8px]">{t("auth.reset_title")}</h1>
        <p role="alert" className="m-0 mt-3 text-body text-[#8C1D18]">{t("auth.reset_invalid")}</p>
        <Link href="/signin/forgot" className={`${primaryBtn} flex items-center justify-center no-underline`}>{t("auth.ask_new_link")}</Link>
      </div>
    );
  }

  if (state === "done") {
    return (
      <div>
        <h1 className="m-0 text-h1 tracking-[-0.8px]">{t("auth.reset_done_heading")}</h1>
        <p role="status" className="m-0 mt-3 text-body text-[#3D4A4E]">{t("auth.reset_done")}</p>
        <Link href="/signin?way=email" className={`${primaryBtn} flex items-center justify-center no-underline`}>{t("auth.sign_in")}</Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate>
      <h1 className="m-0 text-h1 tracking-[-0.8px]">{t("auth.reset_title")}</h1>
      <p className="m-0 mt-2 text-body text-[#3D4A4E]">{t("auth.reset_sub")}</p>
      <PasswordField label={t("auth.new_password")} value={password} onChange={setPassword} isNew autoFocus hint={t("auth.password_hint")} />
      {error && <p role="alert" className="m-0 mt-3 text-label text-[#8C1D18]">{error}</p>}
      <button type="submit" disabled={busy} className={primaryBtn}>{busy ? t("auth.saving") : t("auth.save_password")}</button>
    </form>
  );
}
