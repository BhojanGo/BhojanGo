"use client";
// Profile > Sign-in and security (round 8, D5): one account per person. Link a mobile
// number and an email, each confirmed with a 6-digit code; set or change the password
// (every other device is signed out). An email or number on another account can't be
// added, and the page says so without saying whose it is.
import { unwrap, type CoreSchemas } from "@bhojango/api-client";
import { formatPhone } from "@bhojango/i18n";
import { useCallback, useEffect, useId, useState } from "react";

import { api, useSession } from "@/lib/client";
import { useLanguage, useT } from "@/lib/i18n";
import { authError, looksLikeEmail, MIN_PASSWORD } from "../../signin/emailAuth";
import { CodeBoxes, PasswordField } from "../../signin/fields";
import { card, ghost, h2, input, link, primary, Row } from "./ui";

type Overview = CoreSchemas["SecurityOverview"];
type Country = { code: string; name: string; phone_code: string };
type Editing = null | "email" | "phone" | "password";

function lang(): string | undefined {
  const l = typeof document === "undefined" ? "" : document.documentElement.lang;
  return /^[a-z]{2}$/.test(l) ? l : undefined;
}

export function Security({ countries }: { countries: Country[] }) {
  const t = useT();
  const [info, setInfo] = useState<Overview | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let live = true;
    api.core.GET("/api/v1/me/security")
      .then((r) => {
        if (!live) return;
        setInfo(unwrap(r));
        setFailed(false);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [version]);

  async function finished(message: string) {
    setEditing(null);
    setSaved(message);
    load();
    try {
      useSession.setState({ user: unwrap(await api.core.GET("/api/v1/users/me")) });
    } catch {
      // the profile above refreshes next time
    }
  }

  const open = (what: Editing) => () => {
    setSaved(null);
    setEditing(what);
  };

  return (
    <section id="security" aria-labelledby="security-title" className={card}>
      <h2 id="security-title" className={h2}>{t("account.security.title")}</h2>
      <p className="mt-1 text-small text-muted">{t("account.security.sub")}</p>
      {!info && !failed && (
        <div className="mt-4 space-y-3" aria-busy="true" aria-label={t("account.security.loading")}>
          {[0, 1, 2].map((i) => <div key={i} className="h-12 animate-pulse rounded-xl bg-[#EEF1F1]" />)}
        </div>
      )}
      {failed && (
        <p role="alert" className="mt-4 text-label text-[#8C1D18]">
          {t("account.security.load_failed")}{" "}
          <button type="button" onClick={load} className={link}>{t("account.security.retry")}</button>
        </p>
      )}
      {info && (
        <>
          {editing === "phone" ? (
            <LinkPhone countries={countries} replacing={!!info.phone} onDone={() => void finished(t("account.security.phone_saved"))} onCancel={() => setEditing(null)} />
          ) : (
            <Row
              label={t("account.security.phone")}
              note={info.phone ? (info.phone_verified ? t("account.security.verified_signin") : t("account.security.unverified")) : t("account.security.phone_why")}
              action={<button type="button" onClick={open("phone")} className={link}>{info.phone ? t("account.security.change") : t("account.security.add")}</button>}
            >
              {info.phone ? formatPhone(info.phone) : t("account.security.not_set")}
            </Row>
          )}
          {editing === "email" ? (
            <LinkEmail replacing={!!info.email} onDone={() => void finished(t("account.security.email_saved"))} onCancel={() => setEditing(null)} />
          ) : (
            <Row
              label={t("account.security.email")}
              note={info.email ? (info.email_verified ? t("account.security.verified_signin") : t("account.security.unverified")) : t("account.security.email_why")}
              action={<button type="button" onClick={open("email")} className={link}>{info.email ? t("account.security.change") : t("account.security.add")}</button>}
            >
              {info.email ?? t("account.security.not_set")}
            </Row>
          )}
          {editing === "password" ? (
            <ChangePassword hasPassword={info.has_password} onDone={() => void finished(t("account.security.password_saved"))} onCancel={() => setEditing(null)} />
          ) : (
            <Row
              label={t("account.security.password")}
              note={info.has_password ? t("account.security.password_set") : info.email ? t("account.security.password_none") : t("account.security.password_needs_email")}
              action={info.email ? (
                <button type="button" onClick={open("password")} className={link}>
                  {info.has_password ? t("account.security.change") : t("account.security.set")}
                </button>
              ) : undefined}
            >
              {info.has_password ? "••••••••••" : t("account.security.not_set")}
            </Row>
          )}
          {(info.google_linked || info.apple_linked) && (
            <Row label={t("account.security.also")}>
              {[info.google_linked && "Google", info.apple_linked && "Apple"].filter(Boolean).join(" · ")}
            </Row>
          )}
          {saved && <p role="status" className="pt-3 text-label text-[#0B5D66]">{saved}</p>}
        </>
      )}
    </section>
  );
}

function FormShell({ title, children, onSubmit }: { title: string; children: React.ReactNode; onSubmit: (e: React.FormEvent) => void }) {
  return (
    <form onSubmit={onSubmit} noValidate className="border-b border-[#EEF1F1] py-4">
      <h3 className="m-0 text-h3">{title}</h3>
      {children}
    </form>
  );
}

function useStep() {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(work: () => Promise<void>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await work();
      return true;
    } catch (err) {
      setError(authError(err, t));
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, setError, run };
}

function LinkEmail({ replacing, onDone, onCancel }: { replacing: boolean; onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const id = useId();
  const { busy, error, setError, run } = useStep();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!sent) {
      if (!looksLikeEmail(email)) return setError(t("auth.err_email"));
      if (await run(async () => { unwrap(await api.core.POST("/api/v1/me/email", { body: { email: email.trim(), language: lang() } })); })) setSent(true);
      return;
    }
    if (code.length !== 6) return;
    if (await run(async () => { unwrap(await api.core.POST("/api/v1/me/email/verify", { body: { email: email.trim(), code } })); })) onDone();
  }

  return (
    <FormShell title={t(replacing ? "account.security.email_change_title" : "account.security.email_title")} onSubmit={submit}>
      {!sent ? (
        <label htmlFor={id} className="mt-3 block text-label text-muted">
          {t("auth.email")}
          <input id={id} type="email" inputMode="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className={input} />
        </label>
      ) : (
        <>
          <p className="mt-2 text-body text-muted">{t("account.security.code_sent_to", { to: email.trim() })}</p>
          <CodeBoxes onChange={setCode} legend={t("auth.code_label")} />
        </>
      )}
      {error && <p role="alert" className="mt-3 text-label text-[#8C1D18]">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="submit" disabled={busy || (sent && code.length !== 6)} className={primary}>
          {busy ? t("auth.sending") : sent ? t("account.security.confirm") : t("account.security.send_code")}
        </button>
        <button type="button" onClick={onCancel} className={ghost}>{t("common.cancel")}</button>
      </div>
    </FormShell>
  );
}

function LinkPhone({ countries, replacing, onDone, onCancel }: { countries: Country[]; replacing: boolean; onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const id = useId();
  const ccId = useId();
  const { country: here } = useLanguage();
  const hereCode = here?.code;
  const { busy, error, run } = useStep();
  const [cc, setCc] = useState(countries.find((c) => c.code === hereCode)?.code ?? countries[0]?.code ?? "");
  const [number, setNumber] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const country = countries.find((c) => c.code === cc) ?? null;
  const digits = number.replace(/\D/g, "");
  const phone = country ? `${country.phone_code}${digits}` : "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!sent) {
      if (!country || digits.length < 6 || digits.length > 15) return;
      if (await run(async () => { unwrap(await api.core.POST("/api/v1/me/phone", { body: { phone, country: country.code, language: lang() } })); })) setSent(true);
      return;
    }
    if (code.length !== 6) return;
    if (await run(async () => { unwrap(await api.core.POST("/api/v1/me/phone/verify", { body: { phone, code } })); })) onDone();
  }

  return (
    <FormShell title={t(replacing ? "account.security.phone_change_title" : "account.security.phone_title")} onSubmit={submit}>
      {!sent ? (
        <div className="mt-3 flex flex-wrap gap-3">
          <label htmlFor={ccId} className="text-label text-muted">
            {t("signin.country_code")}
            <select id={ccId} value={cc} onChange={(e) => setCc(e.target.value)} className={`${input} w-auto pr-8`}>
              {countries.map((c) => <option key={c.code} value={c.code}>{`${c.name} ${c.phone_code}`}</option>)}
            </select>
          </label>
          <label htmlFor={id} className="min-w-[200px] flex-grow text-label text-muted">
            {t("signin.mobile")}
            <input id={id} type="tel" inputMode="tel" autoComplete="tel-national" autoFocus value={number}
              onChange={(e) => setNumber(e.target.value.replace(/[^\d ()-]/g, ""))} className={input} />
          </label>
        </div>
      ) : (
        <>
          <p className="mt-2 text-body text-muted">{t("account.security.code_sent_to", { to: formatPhone(phone) })}</p>
          <CodeBoxes onChange={setCode} legend={t("auth.code_label")} />
        </>
      )}
      {error && <p role="alert" className="mt-3 text-label text-[#8C1D18]">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="submit" disabled={busy || (sent ? code.length !== 6 : digits.length < 6)} className={primary}>
          {busy ? t("auth.sending") : sent ? t("account.security.confirm") : t("account.security.send_code")}
        </button>
        <button type="button" onClick={onCancel} className={ghost}>{t("common.cancel")}</button>
      </div>
    </FormShell>
  );
}

function ChangePassword({ hasPassword, onDone, onCancel }: { hasPassword: boolean; onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const { busy, error, setError, run } = useStep();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (hasPassword && !current) return setError(t("auth.err_password_missing"));
    if (next.length < MIN_PASSWORD) return setError(t("auth.err_too_short"));
    const ok = await run(async () => {
      const tokens = unwrap(await api.core.POST("/api/v1/me/password", {
        body: { new_password: next, ...(hasPassword ? { current_password: current } : {}) },
      }));
      // Every other device is signed out; this one carries on with the new tokens.
      await useSession.getState().adopt(tokens);
    });
    if (ok) onDone();
  }

  return (
    <FormShell title={hasPassword ? t("account.security.change_password") : t("account.security.set_password")} onSubmit={submit}>
      {hasPassword && <PasswordField label={t("account.security.current_password")} value={current} onChange={setCurrent} autoFocus />}
      <PasswordField label={t("auth.new_password")} value={next} onChange={setNext} isNew autoFocus={!hasPassword} hint={t("auth.password_hint")} />
      <p className="mt-2 text-small text-muted">{t("account.security.signs_out_others")}</p>
      {error && <p role="alert" className="mt-3 text-label text-[#8C1D18]">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="submit" disabled={busy} className={primary}>{busy ? t("auth.saving") : t("auth.save_password")}</button>
        <button type="button" onClick={onCancel} className={ghost}>{t("common.cancel")}</button>
      </div>
    </FormShell>
  );
}

