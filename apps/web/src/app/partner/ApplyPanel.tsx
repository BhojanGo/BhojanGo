"use client";
// "Add your kitchen": the part that depends on who is looking (R8 F7).
//   signed out        -> "Start your application": a kitchen partner account
//                        (POST /kitchens/apply), then straight into the steps below
//   customer          -> "Apply with this account" (POST /restaurants/apply): only an
//                        account with no orders can become a kitchen's (signup.py)
//   kitchen partner   -> their application where they left off (business details,
//                        licence, tax and bank, menu, go live), or their live kitchen
//   delivery partner, admin -> a short note: kitchens apply with their own account
import { ApiError, unwrap } from "@bhojango/api-client";
import { Button } from "@bhojango/ui";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { api, urls, useHydrated, useSession } from "@/lib/client";
import { useLanguage, useT } from "@/lib/i18n";
import { apiProblem, applicationState, cityOptions, defaultCity, e164, splitLinks, validate, type FieldKey, type SignUpFields, type Terms } from "@/lib/kitchenJoin";

type T = ReturnType<typeof useT>;
type Step = { key: string; title: string; done: boolean; detail: string };
type Application = {
  restaurant_id: string; name: string; done: number; total: number; current: string | null; status: string;
  fssai_number: string | null; fssai_expires_on: string | null; fssai_document: boolean; gstin: string | null;
  payout_account: string | null; area: string | null; street?: string | null; zip?: string | null; country?: string | null;
  cuisines?: string[]; steps: Step[];
};

const bare = "block h-12 w-full rounded-card border-[1.5px] border-line-strong bg-white px-3 text-body font-normal text-kohl outline-none focus:border-peacock aria-[invalid=true]:border-chili";
const field = `mt-1 ${bare}`;
const card = "rounded-[24px] border border-line bg-white p-5 shadow-[0_1px_2px_rgba(17,20,24,0.04)] md:p-8";

/** The hero's action: start (or, for a kitchen partner, continue) the application, lower on this page. */
export function HeroAction() {
  const t = useT();
  const hydrated = useHydrated();
  const role = useSession((s) => s.user?.role);
  const label = hydrated && role === "restaurant_owner" ? t("kitchen_join.continue") : t("kitchen_join.start");
  return (
    <a
      href="#apply"
      data-testid="partner-start"
      onClick={() => window.setTimeout(() => document.getElementById("apply-title")?.focus(), 350)}
      className="inline-flex h-14 items-center justify-center rounded-pill bg-peacock px-7 text-label text-white hover:bg-peacock-deep hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peacock"
    >
      {label}
    </a>
  );
}

interface PanelProps {
  terms: Terms | null;
  visitorCity: string | null;
  countryKnown: boolean;
  countries: string[];
  taxRegimes: Record<string, string>;
  phoneCodes: Record<string, string>;
}

export function ApplyPanel(props: PanelProps) {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const [created, setCreated] = useState<string | null>(null);
  const state = applicationState(user?.role);
  const who = user?.email ?? user?.phone ?? "";

  if (!hydrated) {
    return (
      <div className={card} aria-busy="true" data-testid="partner-loading">
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.form_title")}</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="h-[74px] animate-pulse rounded-card bg-porcelain" />)}
        </div>
      </div>
    );
  }
  if (state === "kitchen") return <MyApplication {...props} created={created} />;
  if (state === "delivery" || state === "other") {
    return (
      <div className={card} data-testid="partner-other-role">
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.form_title")}</h2>
        <p className="m-0 mt-3 max-w-[640px] text-body text-muted">{t(state === "delivery" ? "kitchen_join.delivery_note" : "kitchen_join.admin_note")}</p>
        <Button variant="secondary" className="mt-5" onClick={() => void signOut()}>{t("common.sign_out")}</Button>
      </div>
    );
  }
  if (!props.countryKnown || !props.terms) {
    return (
      <div className={card} data-testid="partner-unavailable">
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.form_title")}</h2>
        <p role="status" className="m-0 mt-3 text-body text-muted">
          {!props.countryKnown ? t("kitchen_join.no_country", { countries: props.countries.join(", ") }) : t("kitchen_join.unavailable")}
        </p>
      </div>
    );
  }
  if (state === "customer") {
    return <CustomerApply terms={props.terms} visitorCity={props.visitorCity} who={who} defaultName={user?.full_name ?? ""} onSignOut={() => void signOut()} />;
  }
  return <SignUpForm terms={props.terms} visitorCity={props.visitorCity} onCreated={setCreated} />;
}

// ── signed out: the account ──────────────────────────────────────────────────

function SignUpForm({ terms, visitorCity, onCreated }: { terms: Terms; visitorCity: string | null; onCreated: (email: string) => void }) {
  const t = useT();
  const { language } = useLanguage();
  const adopt = useSession((s) => s.adopt);
  const cities = cityOptions(terms.cities);
  const [f, setF] = useState<SignUpFields>({
    kitchen_name: "", city_code: defaultCity(cities, visitorCity), full_name: "", phone: "", email: "", password: "", accept_terms: false,
  });
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({});
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  // Round 8 (D5): the account is made once the emailed code is entered (sentTo: that email).
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const summary = useRef<HTMLDivElement>(null);
  const id = useId();

  const set = <K extends FieldKey>(k: K, v: SignUpFields[K]) => {
    const next = { ...f, [k]: v };
    setF(next);
    if (tried) setErrors(validate(next, terms.phone_code, cities));
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTried(true);
    setProblem(null);
    const found = validate(f, terms.phone_code, cities);
    setErrors(found);
    if (Object.keys(found).length) {
      window.setTimeout(() => summary.current?.focus(), 0);
      return;
    }
    setBusy(true);
    try {
      await sendApplication();
      setCode("");
      setSentTo(f.email.trim());
    } catch (err) {
      showProblem(err);
    } finally {
      setBusy(false);
    }
  }

  async function sendApplication() {
    // 202 whether or not the email has an account: a code goes to it (or an email saying "sign in").
    unwrap(await api.core.POST("/api/v1/kitchens/apply", {
      body: {
        kitchen_name: f.kitchen_name.trim(), city_code: f.city_code, full_name: f.full_name.trim(), phone: e164(terms.phone_code, f.phone),
        email: f.email.trim(), password: f.password, accept_terms: true, language,
      },
    }));
  }

  function showProblem(err: unknown) {
    if (err instanceof ApiError) {
      const p = apiProblem(err.code);
      if (p.field) setErrors({ [p.field]: p.key });
      const reason = (err.body as { detail?: { reason?: string } } | undefined)?.detail?.reason;
      const key = err.code === "PASSWORD" && reason === "PASSWORD_BREACHED" ? "password_breached"
        : err.code === "PASSWORD" && reason === "PASSWORD_LIKE_EMAIL" ? "password_email"
          : err.code === "TOO_MANY_CODES" || err.status === 429 ? "too_many"
            : err.code === "CODE_INVALID" ? "code" : p.key;
      setProblem(t(`kitchen_join.errors.${key}`));
    } else {
      setProblem(t("kitchen_join.errors.network"));
    }
    window.setTimeout(() => summary.current?.focus(), 0);
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    if (!sentTo || code.length !== 6) return;
    setBusy(true);
    setProblem(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/auth/email/verify", { body: { email: sentTo, code } })) as {
        access_token: string; refresh_token: string;
      };
      onCreated(sentTo);
      await adopt(r);
    } catch (err) {
      setCode("");
      showProblem(err);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    setProblem(null);
    try {
      await sendApplication();
    } catch (err) {
      showProblem(err);
    } finally {
      setBusy(false);
    }
  }


  const count = Object.keys(errors).length;
  const err = (k: FieldKey) => (errors[k] ? t(`kitchen_join.errors.${errors[k]}`) : null);
  const consent = splitLinks(t("kitchen_join.consent", { terms: "{terms}", privacy: "{privacy}" }), ["terms", "privacy"]);

  if (sentTo) {
    return (
      <div className="grid gap-6 lg:grid-cols-[1fr_340px] lg:gap-10">
        <form noValidate onSubmit={verify} className={card} aria-labelledby="apply-title" data-testid="partner-code">
          <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.code_title")}</h2>
          <p className="m-0 mt-2 max-w-[640px] text-body text-muted">{t("kitchen_join.code_sent", { email: sentTo })}</p>
          <div ref={summary} tabIndex={-1} role="alert" aria-live="assertive" className="outline-none">
            {problem && <p data-testid="partner-form-error" className="m-0 mt-5 rounded-card bg-[#FCEDEA] p-3 text-label text-chili">{problem}</p>}
          </div>
          <div className="mt-6 max-w-[320px]">
            <Field id={`${id}-code`} label={t("kitchen_join.code_label")} error={null}>
              {(a) => <input {...a} name="code" inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={6} value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} className={`${field} tracking-[0.3em]`} />}
            </Field>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button type="submit" size="lg" loading={busy} disabled={code.length !== 6} data-testid="partner-verify">{t("kitchen_join.code_submit")}</Button>
            <button type="button" onClick={() => void resend()} disabled={busy} className="min-h-[44px] font-semibold text-peacock">{t("kitchen_join.code_resend")}</button>
            <button type="button" onClick={() => { setSentTo(null); setProblem(null); }} className="min-h-[44px] font-semibold text-peacock">{t("kitchen_join.code_back")}</button>
          </div>
        </form>
        <NextSteps documents={terms.documents} />
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px] lg:gap-10">
      <form noValidate onSubmit={submit} className={card} aria-labelledby="apply-title" data-testid="partner-form">
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.form_title")}</h2>
        <p className="m-0 mt-2 text-body text-muted">{t("kitchen_join.form_lead")}</p>
        <div ref={summary} tabIndex={-1} role="alert" aria-live="assertive" className="outline-none">
          {(problem || (tried && count > 0)) && (
            <p data-testid="partner-form-error" className="m-0 mt-5 rounded-card bg-[#FCEDEA] p-3 text-label text-chili">
              {problem ?? t("kitchen_join.errors.summary", { count })}
            </p>
          )}
        </div>
        <div className="mt-6 grid gap-x-5 gap-y-4 md:grid-cols-2">
          <Field id={`${id}-kitchen`} label={t("kitchen_join.kitchen_name")} hint={t("kitchen_join.kitchen_name_hint")} error={err("kitchen_name")}>
            {(a) => <input {...a} name="kitchen_name" autoComplete="organization" value={f.kitchen_name} onChange={(e) => set("kitchen_name", e.target.value)} className={field} maxLength={120} />}
          </Field>
          <Field id={`${id}-city`} label={t("kitchen_join.city")} error={err("city_code")}>
            {(a) => (
              <select {...a} name="city_code" value={f.city_code} onChange={(e) => set("city_code", e.target.value)} className={field}>
                <option value="">{t("kitchen_join.city_pick")}</option>
                {cities.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.status === "soon" ? t("kitchen_join.city_soon", { city: `${c.name}, ${c.region}` }) : `${c.name}, ${c.region}`}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field id={`${id}-name`} label={t("kitchen_join.contact_name")} error={err("full_name")}>
            {(a) => <input {...a} name="full_name" autoComplete="name" value={f.full_name} onChange={(e) => set("full_name", e.target.value)} className={field} maxLength={80} />}
          </Field>
          <Field id={`${id}-phone`} label={t("kitchen_join.phone")} hint={t("kitchen_join.phone_hint")} error={err("phone")}>
            {(a) => (
              <div className="mt-1 flex">
                <span aria-label={t("kitchen_join.phone_code", { code: terms.phone_code })} className="flex h-12 items-center rounded-l-card border-[1.5px] border-r-0 border-line-strong bg-porcelain px-3 text-body tabular-nums text-muted">
                  {terms.phone_code}
                </span>
                <input {...a} name="phone" type="tel" inputMode="tel" autoComplete="tel-national" value={f.phone} onChange={(e) => set("phone", e.target.value)}
                  className={`${bare} rounded-l-none tabular-nums`} maxLength={20} />
              </div>
            )}
          </Field>
          <Field id={`${id}-email`} label={t("kitchen_join.email")} hint={t("kitchen_join.email_hint")} error={err("email")}>
            {(a) => <input {...a} name="email" type="email" inputMode="email" autoComplete="email" value={f.email} onChange={(e) => set("email", e.target.value)} className={field} maxLength={254} />}
          </Field>
          <Field id={`${id}-password`} label={t("kitchen_join.password")} hint={t("kitchen_join.password_hint")} error={err("password")}>
            {(a) => (
              <div className="relative">
                <input {...a} name="password" type={show ? "text" : "password"} autoComplete="new-password" value={f.password} onChange={(e) => set("password", e.target.value)}
                  className={`${field} pr-14`} maxLength={128} />
                <button type="button" onClick={() => setShow(!show)} aria-pressed={show} aria-label={show ? t("kitchen_join.hide_password") : t("kitchen_join.show_password")}
                  className="absolute right-1 top-1 flex h-11 w-11 items-center justify-center rounded-pill text-muted hover:text-peacock focus-visible:outline focus-visible:outline-2 focus-visible:outline-peacock">
                  <EyeIcon off={show} />
                </button>
              </div>
            )}
          </Field>
        </div>
        <div className="mt-5">
          <label className="flex min-h-[44px] cursor-pointer items-start gap-3 text-body">
            <input type="checkbox" name="accept_terms" checked={f.accept_terms} onChange={(e) => set("accept_terms", e.target.checked)}
              aria-invalid={!!errors.accept_terms} aria-describedby={errors.accept_terms ? `${id}-consent-error` : undefined}
              className="mt-[3px] h-5 w-5 shrink-0 accent-peacock" />
            <span>
              {consent.map((p, i) => ("link" in p
                ? <Link key={i} href={p.link === "terms" ? "/terms" : "/privacy"} target="_blank" className="font-semibold text-peacock underline">{t(`kitchen_join.${p.link}`)}</Link>
                : <span key={i}>{p.text}</span>))}
            </span>
          </label>
          {errors.accept_terms && <p id={`${id}-consent-error`} className="m-0 mt-1 text-small text-chili">{err("accept_terms")}</p>}
        </div>
        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <Button type="submit" size="lg" loading={busy} data-testid="partner-submit" className="w-full sm:w-auto">{t("kitchen_join.submit")}</Button>
          <p className="m-0 text-body text-muted">
            {t("kitchen_join.have_account")}{" "}
            <Link href="/signin?next=/partner" className="font-semibold text-peacock">{t("kitchen_join.sign_in")}</Link>
          </p>
        </div>
      </form>
      <NextSteps documents={terms.documents} />
    </div>
  );
}

/** Beside the form: what happens right after "Create account" (true of the product today). */
function NextSteps({ documents }: { documents: { key: string; title: string }[] }) {
  const t = useT();
  const items = [t("kitchen_join.next_email"), t("kitchen_join.next_saved"), t("kitchen_join.next_review")];
  return (
    <section aria-labelledby="next-title" data-testid="partner-next" className="rounded-[24px] bg-porcelain p-5 md:p-6 lg:self-start">
      <h3 id="next-title" className="m-0 text-h3">{t("kitchen_join.next_title")}</h3>
      <ul className="m-0 mt-4 list-none space-y-3 p-0">
        {items.map((x) => (
          <li key={x} className="flex gap-3 text-body">
            <span aria-hidden="true" className="mt-[9px] h-2 w-2 shrink-0 rounded-pill bg-peacock" />
            <span>{x}</span>
          </li>
        ))}
      </ul>
      {documents.length > 0 && (
        <>
          <p className="m-0 mt-5 text-label">{t("kitchen_join.next_docs")}</p>
          <ul className="m-0 mt-2 flex list-none flex-wrap gap-2 p-0">
            {documents.map((d) => <li key={d.key} className="rounded-pill border border-line-strong bg-white px-3 py-1 text-small">{d.title}</li>)}
          </ul>
        </>
      )}
    </section>
  );
}

function Field({ id, label, hint, error, children }: {
  id: string; label: string; hint?: string; error: string | null;
  children: (a: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}) {
  const describedBy = [error ? `${id}-error` : null, hint && !error ? `${id}-hint` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <label htmlFor={id} className="text-label">{label}</label>
      {children({ id, "aria-invalid": !!error, "aria-describedby": describedBy })}
      {error ? <p id={`${id}-error`} className="m-0 mt-1 text-small text-chili">{error}</p> : null}
      {hint && !error ? <p id={`${id}-hint`} className="m-0 mt-1 text-small text-muted">{hint}</p> : null}
    </div>
  );
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {off ? <path d="M4 4l16 16" /> : null}
    </svg>
  );
}

// ── signed in as a customer ──────────────────────────────────────────────────

function CustomerApply({ terms, visitorCity, who, defaultName, onSignOut }: {
  terms: Terms; visitorCity: string | null; who: string; defaultName: string; onSignOut: () => void;
}) {
  const t = useT();
  const adopt = useSession((s) => s.adopt);
  const cities = cityOptions(terms.cities);
  const [f, setF] = useState({ kitchen_name: "", city_code: defaultCity(cities, visitorCity), full_name: defaultName });
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setProblem(null);
    const found: Partial<Record<FieldKey, string>> = {
      ...(f.kitchen_name.trim().length < 2 ? { kitchen_name: "kitchen_name" } : {}),
      ...(!cities.some((c) => c.code === f.city_code) ? { city_code: "city" } : {}),
      ...(f.full_name.trim().length < 2 ? { full_name: "contact_name" } : {}),
    };
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const r = unwrap(await api.core.POST("/api/v1/restaurants/apply", {
        body: { kitchen_name: f.kitchen_name.trim(), city_code: f.city_code, full_name: f.full_name.trim() },
      }));
      await adopt(r as { access_token: string; refresh_token: string });
    } catch (err) {
      setProblem(err instanceof ApiError
        ? (err.code === "HAS_ORDERS" || err.code === "ROLE" ? t("kitchen_join.has_orders") : t("kitchen_join.errors.generic"))
        : t("kitchen_join.errors.network"));
    } finally {
      setBusy(false);
    }
  }
  const err = (k: FieldKey) => (errors[k] ? t(`kitchen_join.errors.${errors[k]}`) : null);
  return (
    <form noValidate onSubmit={submit} className={card} aria-labelledby="apply-title" data-testid="partner-customer">
      <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.customer_title")}</h2>
      <p className="m-0 mt-2 max-w-[720px] text-body text-muted">{t("kitchen_join.customer_body", { who })}</p>
      {problem && <p role="alert" className="m-0 mt-5 rounded-card bg-[#FCEDEA] p-3 text-label text-chili">{problem}</p>}
      <div className="mt-6 grid gap-x-5 gap-y-4 md:grid-cols-3">
        <Field id={`${id}-kitchen`} label={t("kitchen_join.kitchen_name")} hint={t("kitchen_join.kitchen_name_hint")} error={err("kitchen_name")}>
          {(a) => <input {...a} value={f.kitchen_name} onChange={(e) => setF({ ...f, kitchen_name: e.target.value })} className={field} maxLength={120} />}
        </Field>
        <Field id={`${id}-city`} label={t("kitchen_join.city")} error={err("city_code")}>
          {(a) => (
            <select {...a} value={f.city_code} onChange={(e) => setF({ ...f, city_code: e.target.value })} className={field}>
              <option value="">{t("kitchen_join.city_pick")}</option>
              {cities.map((c) => <option key={c.code} value={c.code}>{c.status === "soon" ? t("kitchen_join.city_soon", { city: `${c.name}, ${c.region}` }) : `${c.name}, ${c.region}`}</option>)}
            </select>
          )}
        </Field>
        <Field id={`${id}-name`} label={t("kitchen_join.contact_name")} error={err("full_name")}>
          {(a) => <input {...a} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} className={field} maxLength={80} />}
        </Field>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <Button type="submit" size="lg" loading={busy}>{t("kitchen_join.customer_title")}</Button>
        <Button type="button" variant="secondary" size="lg" onClick={onSignOut}>{t("kitchen_join.customer_other")}</Button>
      </div>
    </form>
  );
}

// ── signed in as a kitchen partner: the application ─────────────────────────

function MyApplication({ taxRegimes, created }: PanelProps & { created: string | null }) {
  const t = useT();
  const user = useSession((s) => s.user);
  const [app, setApp] = useState<Application | null>(null);
  const [none, setNone] = useState(false);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  const take = useCallback((r: Loaded) => {
    setFailed(r === "failed");
    setNone(r === "none");
    if (typeof r === "object") setApp(r);
    return typeof r === "object" ? r : null;
  }, []);
  const load = useCallback(async () => take(await fetchApplication()), [take]);
  useEffect(() => {
    let live = true;
    void fetchApplication().then((r) => live && take(r));
    return () => {
      live = false;
    };
  }, [take]);
  useEffect(() => {
    if (created && app) heading.current?.focus();
  }, [created, app]);

  if (failed) {
    return (
      <div className={card}>
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.continue")}</h2>
        <p role="alert" className="m-0 mt-3 text-body text-muted">{t("kitchen_join.app_error")}</p>
        <Button variant="secondary" className="mt-4" onClick={() => void load()}>{t("common.retry")}</Button>
      </div>
    );
  }
  if (none) return <p className="text-body text-muted">{t("kitchen_join.app_error")}</p>;
  if (!app) {
    return (
      <div className={card} aria-busy="true" data-testid="partner-app-loading">
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.continue")}</h2>
        <div className="mt-6 grid gap-3">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-12 animate-pulse rounded-card bg-porcelain" />)}</div>
      </div>
    );
  }

  const gst = taxRegimes[app.country ?? ""] === "gst";
  const who = user?.email ?? user?.phone ?? "";
  if (app.status === "active" || app.status === "suspended") {
    const live = app.status === "active";
    return (
      <div className={card} data-testid="partner-app-status" data-status={app.status}>
        <h2 id="apply-title" tabIndex={-1} className="m-0 text-h2 outline-none">{t(live ? "kitchen_join.app_live_title" : "kitchen_join.app_paused_title")}</h2>
        <p className="m-0 mt-1 text-h3">{app.name}</p>
        <p className="m-0 mt-3 max-w-[640px] text-body text-muted">
          {live ? t("kitchen_join.app_live_body", { phone: user?.phone ?? who }) : t("kitchen_join.app_paused_body")}
        </p>
        {!live && <Link href="/help" className="mt-4 inline-flex h-12 items-center rounded-pill bg-peacock px-6 text-label text-white hover:text-white">{t("footer.help")}</Link>}
      </div>
    );
  }

  const current = open ?? app.current ?? "go_live";
  const reload = async () => {
    const a = await load();
    setOpen(a?.current ?? null);
  };
  return (
    <div className={card} data-testid="partner-application" data-current={app.current ?? ""}>
      {created && (
        <p role="status" className="m-0 mb-5 rounded-card bg-peacock-mist p-3 text-label text-peacock-deep">{t("kitchen_join.created", { email: created })}</p>
      )}
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="apply-title" ref={heading} tabIndex={-1} className="m-0 text-h2 outline-none">{t("kitchen_join.app_title", { kitchen: app.name })}</h2>
        <span className="text-label tabular-nums text-peacock">{t("kitchen_join.app_progress", { done: app.done, total: app.total })}</span>
      </div>
      <p className="m-0 mt-2 text-small text-muted" data-testid="partner-saved">{t("kitchen_join.app_saved", { who })}</p>
      <div className="mt-6 grid gap-6 lg:grid-cols-[300px_1fr] lg:gap-10">
        <ol className="m-0 list-none space-y-1 p-0" aria-label={t("partner.apply.steps_label")}>
          {app.steps.map((s, i) => {
            const on = s.key === current;
            const text = stepText(t, s, gst);
            return (
              <li key={s.key}>
                <button type="button" onClick={() => setOpen(s.key)} aria-current={on ? "step" : undefined}
                  aria-label={t("kitchen_join.step_open", { step: text.title })}
                  className={`flex min-h-[52px] w-full items-center gap-3 rounded-card px-3 py-2 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-peacock ${on ? "bg-peacock-mist" : "hover:bg-porcelain"}`}>
                  <span aria-hidden="true" className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-pill text-small font-semibold ${s.done ? "bg-peacock text-white" : on ? "border-2 border-peacock text-peacock" : "border-[1.5px] border-line-strong text-muted"}`}>
                    {s.done ? "✓" : i + 1}
                  </span>
                  <span className="min-w-0">
                    <b className="block text-label">{text.title}</b>
                    <span className="block text-small text-muted">{s.done ? t("kitchen_join.step_done") : t("kitchen_join.step_todo")}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <div className="min-w-0 rounded-card bg-porcelain p-4 md:p-6" data-testid={`step-${current}`}>
          <StepBody app={app} stepKey={current} gst={gst} onSaved={reload} />
        </div>
      </div>
    </div>
  );
}

type Loaded = Application | "none" | "failed";

/** The kitchen partner's first kitchen and its application ("none": no kitchen yet). */
async function fetchApplication(): Promise<Loaded> {
  try {
    const mine = unwrap(await api.core.GET("/api/v1/restaurants/mine"));
    if (!mine[0]) return "none";
    return unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/application", { params: { path: { restaurant_id: mine[0].id } } })) as Application;
  } catch {
    return "failed";
  }
}

/** A step's name in the visitor's language (as the BhojanGo Kitchen app words it). */
function stepText(t: T, s: Step, gst: boolean): { title: string; detail: string } {
  const v = gst ? "gst" : "other";
  switch (s.key) {
    case "business": return { title: t("partner.apply.steps.business"), detail: t("partner.apply.steps.business_detail") };
    case "fssai": return { title: t(`partner.apply.steps.fssai_${v}`), detail: t(`partner.apply.steps.fssai_${v}_detail`) };
    case "gst_bank": return { title: t(`partner.apply.steps.tax_${v}`), detail: t(`partner.apply.steps.tax_${v}_detail`) };
    case "menu": return { title: t("partner.apply.steps.menu"), detail: t("kitchen_join.menu_body") };
    case "go_live": return { title: t("partner.apply.steps.go_live"), detail: t("kitchen_join.go_live_body") };
    default: return { title: s.title, detail: s.detail };
  }
}

function StepBody({ app, stepKey, gst, onSaved }: { app: Application; stepKey: string; gst: boolean; onSaved: () => Promise<void> }) {
  const t = useT();
  const step = app.steps.find((s) => s.key === stepKey);
  if (!step) return null;
  if (stepKey === "business") return <Business app={app} onSaved={onSaved} />;
  if (stepKey === "fssai" && gst) return <Licence app={app} onSaved={onSaved} />;
  if (stepKey === "gst_bank") return <TaxBank app={app} gst={gst} onSaved={onSaved} />;
  const text = stepText(t, step, gst);
  const allDone = app.steps.filter((s) => s.key !== "go_live").every((s) => s.done);
  return (
    <>
      <h3 className="m-0 text-h3">{text.title}</h3>
      <p className="m-0 mt-2 text-body text-muted">
        {stepKey === "fssai" ? t("kitchen_join.permit_done") : stepKey === "go_live" && allDone ? t("kitchen_join.app_review") : text.detail}
      </p>
      <p className={`m-0 mt-4 text-label ${step.done ? "text-peacock" : "text-[#8A5A12]"}`}>{step.done ? t("kitchen_join.step_done") : t("kitchen_join.step_todo")}</p>
    </>
  );
}

function useSave(onSaved: () => Promise<void>) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      await onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? t("kitchen_join.save_failed") : t("kitchen_join.errors.network"));
    } finally {
      setBusy(false);
    }
  };
  return { busy, msg, setMsg, run };
}

function Business({ app, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const t = useT();
  const has = !!app.street;
  const [f, setF] = useState({ street: app.street ?? "", area: has ? app.area ?? "" : "", zip: app.zip ?? "", cuisines: (app.cuisines ?? []).join(", ") });
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null);
  const [pinMsg, setPinMsg] = useState<string | null>(null);
  const [tried, setTried] = useState(false);
  const { busy, msg, run } = useSave(onSaved);
  const id = useId();
  const cuisines = f.cuisines.split(",").map((c) => c.trim()).filter(Boolean).slice(0, 5);
  const bad = { street: f.street.trim().length < 3, area: f.area.trim().length < 2, zip: f.zip.trim().length < 3, cuisines: cuisines.length === 0 };
  const invalid = Object.values(bad).some(Boolean);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  function locate() {
    setPinMsg(null);
    if (!navigator.geolocation) return setPinMsg(t("kitchen_join.pin_failed"));
    navigator.geolocation.getCurrentPosition((p) => setPin({ lat: p.coords.latitude, lng: p.coords.longitude }), () => setPinMsg(t("kitchen_join.pin_failed")), { timeout: 10000 });
  }
  function save(e: React.FormEvent) {
    e.preventDefault();
    setTried(true);
    if (invalid) return;
    void run(async () => unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/business", {
      params: { path: { restaurant_id: app.restaurant_id } },
      body: { street: f.street.trim(), area: f.area.trim(), zip: f.zip.trim(), cuisines, ...(pin ? { lat: pin.lat, lng: pin.lng } : {}) },
    })));
  }
  const e = (k: keyof typeof bad) => (tried && bad[k] ? t("kitchen_join.business_errors") : null);
  return (
    <form noValidate onSubmit={save} aria-label={t("kitchen_join.business_title")}>
      <h3 className="m-0 text-h3">{t("kitchen_join.business_title")}</h3>
      <p className="m-0 mt-2 text-body text-muted">{t("kitchen_join.business_lead")}</p>
      {tried && invalid && <p role="alert" className="m-0 mt-4 text-label text-chili">{t("kitchen_join.business_errors")}</p>}
      <div className="mt-4 grid gap-x-4 gap-y-3 md:grid-cols-2">
        <div className="md:col-span-2">
          <FieldBare id={`${id}-street`} label={t("kitchen_join.street")} invalid={!!e("street")}>
            {(a) => <input {...a} autoComplete="street-address" value={f.street} onChange={set("street")} className={field} maxLength={200} />}
          </FieldBare>
        </div>
        <FieldBare id={`${id}-area`} label={t("kitchen_join.area")} invalid={!!e("area")}>
          {(a) => <input {...a} value={f.area} onChange={set("area")} className={field} maxLength={80} />}
        </FieldBare>
        <FieldBare id={`${id}-zip`} label={t("kitchen_join.zip")} invalid={!!e("zip")}>
          {(a) => <input {...a} autoComplete="postal-code" value={f.zip} onChange={set("zip")} className={`${field} tabular-nums`} maxLength={12} />}
        </FieldBare>
        <div className="md:col-span-2">
          <FieldBare id={`${id}-cuisines`} label={t("kitchen_join.cuisines")} hint={t("kitchen_join.cuisines_hint")} invalid={!!e("cuisines")}>
            {(a) => <input {...a} value={f.cuisines} onChange={set("cuisines")} className={field} maxLength={200} />}
          </FieldBare>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button type="button" variant="secondary" onClick={locate}>{pin ? t("kitchen_join.pin_set") : t("kitchen_join.pin")}</Button>
        <span className="text-small text-muted" role={pinMsg ? "status" : undefined}>{pinMsg ?? t("kitchen_join.pin_note")}</span>
      </div>
      {msg && <p role="alert" className="m-0 mt-4 text-label text-chili">{msg}</p>}
      <Button type="submit" size="lg" loading={busy} className="mt-5" data-testid="business-save">{t("partner.apply.save_continue")}</Button>
    </form>
  );
}

function FieldBare({ id, label, hint, invalid, children }: {
  id: string; label: string; hint?: string; invalid: boolean;
  children: (a: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-label">{label}</label>
      {children({ id, "aria-invalid": invalid, "aria-describedby": hint ? `${id}-hint` : undefined })}
      {hint ? <p id={`${id}-hint`} className="m-0 mt-1 text-small text-muted">{hint}</p> : null}
    </div>
  );
}

/** POST /uploads (multipart): the licence, a PDF or a photo up to 5 MB. Returns the key. */
async function upload(file: File): Promise<string> {
  const send = (token: string | null) => {
    const form = new FormData();
    form.append("purpose", "partner_document");
    form.append("file", file);
    return fetch(`${urls.core}/api/v1/uploads`, { method: "POST", headers: token ? { authorization: `Bearer ${token}` } : {}, body: form });
  };
  let r = await send(useSession.getState().access);
  if (r.status === 401) r = await send(await useSession.getState().refresh());
  const body = (await r.json().catch(() => null)) as { key?: string } | null;
  if (!r.ok || !body?.key) throw new Error("upload");
  return body.key;
}

function Licence({ app, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const t = useT();
  const [num, setNum] = useState(app.fssai_number ?? "");
  const [until, setUntil] = useState(app.fssai_expires_on ?? "");
  const [doc, setDoc] = useState<{ name: string; key: string | null } | null>(app.fssai_document ? { name: t("partner.apply.licence_on_file"), key: null } : null);
  const [uploading, setUploading] = useState(false);
  const { busy, msg, setMsg, run } = useSave(onSaved);
  const id = useId();
  const digits = num.replace(/\D/g, "");

  async function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(null);
    if (file.size > 5 * 1024 * 1024) return setMsg(t("kitchen_join.upload_failed"));
    setUploading(true);
    try {
      setDoc({ name: file.name, key: await upload(file) });
    } catch {
      setDoc(null);
      setMsg(t("kitchen_join.upload_failed"));
    } finally {
      setUploading(false);
    }
  }
  function save(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/licence", {
      params: { path: { restaurant_id: app.restaurant_id } },
      body: { fssai_number: digits, fssai_expires_on: until, ...(doc?.key ? { document_key: doc.key } : {}) },
    })));
  }
  return (
    <form noValidate onSubmit={save} aria-label={t("partner.apply.fssai_title")}>
      <h3 className="m-0 text-h3">{t("partner.apply.fssai_title")}</h3>
      <p className="m-0 mt-2 text-body text-muted">{t("partner.apply.fssai_sub")}</p>
      <div className="mt-4 grid gap-x-4 gap-y-3 md:grid-cols-2">
        <FieldBare id={`${id}-num`} label={t("partner.apply.licence_number")} hint={t("partner.apply.licence_number_hint")} invalid={false}>
          {(a) => <input {...a} inputMode="numeric" autoComplete="off" value={num} onChange={(e) => setNum(e.target.value.replace(/\D/g, "").slice(0, 14))} className={`${field} tabular-nums`} />}
        </FieldBare>
        <FieldBare id={`${id}-until`} label={t("partner.apply.valid_until")} hint={t("kitchen_join.fssai_date_hint")} invalid={false}>
          {(a) => <input {...a} type="date" value={until} onChange={(e) => setUntil(e.target.value)} className={field} />}
        </FieldBare>
      </div>
      <div className="mt-4">
        <label htmlFor={`${id}-doc`} className="text-label">{t("kitchen_join.licence_choose")}</label>
        <input id={`${id}-doc`} type="file" accept="application/pdf,image/jpeg,image/png" onChange={pick}
          className="mt-1 block w-full text-small file:mr-3 file:h-11 file:cursor-pointer file:rounded-pill file:border-[1.5px] file:border-line-strong file:bg-white file:px-4 file:text-label file:text-kohl" />
        {(doc || uploading) && <p role="status" className="m-0 mt-1 text-small text-muted">{uploading ? t("partner.apply.uploading") : `${doc!.name} · ${doc!.key ? t("partner.apply.uploaded_now") : t("partner.apply.on_file")}`}</p>}
      </div>
      <p className="m-0 mt-4 rounded-card bg-white p-3 text-small text-muted">{t("partner.apply.fssai_check")}</p>
      {msg && <p role="alert" className="m-0 mt-4 text-label text-chili">{msg}</p>}
      <Button type="submit" size="lg" loading={busy} disabled={digits.length !== 14 || !until || uploading} className="mt-5">{t("partner.apply.save_continue")}</Button>
    </form>
  );
}

const GSTIN = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

function TaxBank({ app, gst, onSaved }: { app: Application; gst: boolean; onSaved: () => Promise<void> }) {
  const t = useT();
  const [gstin, setGstin] = useState(app.gstin ?? "");
  const tax = useSave(onSaved);
  const bank = useSave(onSaved);
  const id = useId();
  const ok = GSTIN.test(gstin);

  function addBank() {
    void bank.run(async () => {
      const r = unwrap(await api.core.POST("/api/v1/finance/payout-accounts", { body: { payee_type: "restaurant", restaurant_id: app.restaurant_id } })) as { onboarding_url?: string | null };
      if (r.onboarding_url) window.location.assign(r.onboarding_url);
    });
  }
  return (
    <div>
      <h3 className="m-0 text-h3">{gst ? t("partner.apply.gst_title") : t("partner.apply.steps.tax_other")}</h3>
      <p className="m-0 mt-2 text-body text-muted">{gst ? t("partner.apply.gst_sub") : t("partner.apply.steps.tax_other_detail")}</p>
      {gst && (
        <form noValidate className="mt-4" onSubmit={(e) => {
          e.preventDefault();
          if (ok) void tax.run(async () => unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/gst", { params: { path: { restaurant_id: app.restaurant_id } }, body: { gstin } })));
        }}>
          <label htmlFor={`${id}-gstin`} className="text-label">{t("partner.apply.gstin")}</label>
          <div className="mt-1 flex flex-col gap-3 sm:flex-row">
            <input id={`${id}-gstin`} value={gstin} maxLength={15} autoComplete="off" aria-invalid={gstin.length === 15 && !ok} aria-describedby={`${id}-gstin-hint`}
              onChange={(e) => setGstin(e.target.value.toUpperCase().replace(/[^0-9A-Z]/g, ""))} className={`${bare} uppercase tabular-nums sm:max-w-[320px]`} />
            <Button type="submit" loading={tax.busy} disabled={!ok}>{app.gstin ? t("partner.apply.update") : t("partner.apply.save_gstin")}</Button>
          </div>
          <p id={`${id}-gstin-hint`} className="m-0 mt-1 text-small text-muted">{t("partner.apply.gstin_check")}</p>
          {tax.msg && <p role="alert" className="m-0 mt-2 text-label text-chili">{tax.msg}</p>}
        </form>
      )}
      <div className="mt-6 rounded-card bg-white p-4">
        <b className="block text-label">{t("partner.apply.bank")}</b>
        <p className="m-0 mt-1 text-body">
          {app.payout_account === "active" ? t("partner.apply.bank_confirmed") : app.payout_account ? t("partner.apply.bank_waiting") : t("partner.apply.bank_none")}
        </p>
        <p className="m-0 mt-1 text-small text-muted">{t("partner.apply.bank_partner")} {t("kitchen_join.bank_note")}</p>
        {app.payout_account !== "active" && (
          <Button variant={gst && !app.gstin ? "secondary" : "primary"} className="mt-3" loading={bank.busy} onClick={addBank}>
            {app.payout_account ? t("partner.apply.continue") : t("partner.apply.add_bank")}
          </Button>
        )}
        {bank.msg && <p role="alert" className="m-0 mt-2 text-label text-chili">{bank.msg}</p>}
      </div>
    </div>
  );
}
