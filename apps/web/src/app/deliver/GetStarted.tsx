"use client";
// "Get started" on /deliver: name, phone (the country's calling code from Markets)
// and city -> the code we text (the same OTP as sign-in) -> POST /riders/apply, the
// call the BhojanGo Delivery app's Join screen makes. Then: get the app (QR code,
// store links from Markets once published, else /deliver/app) and sign in there
// with the same number to add documents.
import { ApiError, errorMessage, unwrap } from "@bhojango/api-client";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { Chevron } from "@/components/Icons";
import { api, useHydrated, useSession } from "@/lib/client";
import { firstName, qrPath } from "@/lib/deliver";
import { useT } from "@/lib/i18n";
import { codeSendError } from "../signin/emailAuth";

type Country = { code: string; name: string; phone_code: string };
type City = { code: string; name: string; region: string };
type Apps = { android?: string | null; ios?: string | null };

const WAIT = 30; // seconds before "Send a new code"
const field = "mt-2 block h-14 w-full rounded-[14px] border-[1.5px] border-[#3A4D50] bg-[#14201F] px-4 text-body-lg text-white outline-none focus:border-kesar-bright focus:ring-2 focus:ring-kesar-bright/30";
const primary = "inline-flex h-14 w-full items-center justify-center rounded-full bg-kesar-bright px-6 text-label text-kohl hover:bg-[#F0B957] disabled:cursor-not-allowed disabled:bg-[#2E4447] disabled:text-[#A9B8BA]";
const ERRORS: Record<string, string> = { HAS_ORDERS: "gs_err_has_orders", ROLE: "gs_err_role", ADMIN: "gs_err_role", CITY: "gs_err_city" };

export function GetStarted({ countries, country, cities, city, apps }: { countries: Country[]; country: string | null; cities: City[]; city: string | null; apps: Apps }) {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const { sendCode, verify, adopt, signOut } = useSession();
  const [step, setStep] = useState<"form" | "code" | "done">("form");
  const [cc, setCc] = useState(country ?? countries[0]?.code ?? null);
  const [name, setName] = useState("");
  const [number, setNumber] = useState("");
  const [cityCode, setCityCode] = useState(city ?? cities[0]?.code ?? "");
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentAt, setSentAt] = useState(0);
  const [now, setNow] = useState(0);
  const codeRef = useRef<HTMLInputElement>(null);
  const ids = { name: useId(), nameHelp: useId(), phone: useId(), city: useId(), code: useId() };

  const phoneCountry = countries.find((c) => c.code === cc) ?? null;
  const digits = number.replace(/\D/g, "");
  const phone = phoneCountry ? `${phoneCountry.phone_code}${digits}` : "";
  const nameOk = name.trim().split(/\s+/).filter(Boolean).length >= 2 && name.trim().length <= 80;
  const formOk = nameOk && !!phoneCountry && digits.length >= 6 && digits.length <= 15 && !!cityCode;
  const wait = Math.max(0, WAIT - Math.floor((now - sentAt) / 1000));
  const signedUp = hydrated && user?.role === "driver";

  useEffect(() => {
    if (step !== "code") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [step]);

  function problem(err: unknown, fallback: string): string {
    const code = err instanceof ApiError ? err.code : (err as { body?: { detail?: { code?: string } } })?.body?.detail?.code;
    if (code && ERRORS[code]) return t(`deliver_page.${ERRORS[code]}`);
    // Too many codes for this number (with how long to wait), or the SMS provider down.
    return codeSendError(err, t, errorMessage((err as { body?: unknown })?.body, fallback));
  }

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    if (!formOk || !phoneCountry) return;
    setBusy(true);
    setError(null);
    try {
      await sendCode(phone, phoneCountry.code);
      const at = Date.now();
      setSentAt(at);
      setNow(at);
      setOtp("");
      setStep("code");
      setTimeout(() => codeRef.current?.focus(), 0);
    } catch (err) {
      setError(problem(err, t("deliver_page.gs_send_failed")));
    } finally {
      setBusy(false);
    }
  }

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (otp.length !== 6 || !phoneCountry) return;
    setBusy(true);
    setError(null);
    try {
      await verify(phone, otp, phoneCountry.code);
    } catch (err) {
      setError(problem(err, t("deliver_page.gs_code_failed")));
      setOtp("");
      setBusy(false);
      codeRef.current?.focus();
      return;
    }
    try {
      const tokens = unwrap(await api.core.POST("/api/v1/riders/apply", { body: { full_name: name.trim().replace(/\s+/g, " "), city_code: cityCode } }));
      await adopt(tokens as { access_token: string; refresh_token: string });
      setStep("done");
    } catch (err) {
      setError(problem(err, t("deliver_page.gs_apply_failed")));
      setStep("form");
    } finally {
      setBusy(false);
    }
  }

  if (!hydrated) {
    return (
      <div aria-busy="true" className="rounded-[20px] bg-[#14201F] p-6" data-testid="gs-loading">
        <span className="sr-only">{t("deliver_page.gs_loading")}</span>
        <div className="h-5 w-40 animate-pulse rounded bg-[#24383B]" />
        <div className="mt-5 h-14 animate-pulse rounded-[14px] bg-[#24383B]" />
        <div className="mt-4 h-14 animate-pulse rounded-[14px] bg-[#24383B]" />
        <div className="mt-4 h-14 animate-pulse rounded-full bg-[#24383B]" />
      </div>
    );
  }

  if (step === "done" || signedUp) {
    return (
      <Done
        name={firstName(user?.full_name || name)}
        phone={user?.phone || phone}
        country={user?.country || country}
        apps={apps}
        onOther={async () => {
          await signOut();
          setStep("form");
          setNumber("");
          setOtp("");
        }}
      />
    );
  }

  if (step === "code") {
    return (
      <form onSubmit={check} noValidate className="rounded-[20px] bg-[#14201F] p-5 sm:p-6" data-testid="gs-code-form" aria-labelledby={`${ids.code}-h`}>
        <button type="button" onClick={() => { setStep("form"); setError(null); }} className="inline-flex min-h-[44px] items-center gap-2 text-label text-[#C4D0D2] hover:text-white">
          <span aria-hidden="true">←</span> {t("deliver_page.gs_change")}
        </button>
        <h3 id={`${ids.code}-h`} className="m-0 mt-2 text-h2">{t("deliver_page.gs_code_title")}</h3>
        <p className="m-0 mt-1 text-body text-[#C4D0D2]">{t("deliver_page.gs_code_sent", { phone })}</p>
        <label htmlFor={ids.code} className="mt-5 block text-label">{t("deliver_page.gs_code_label")}</label>
        <input
          ref={codeRef}
          id={ids.code}
          data-testid="gs-code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={otp}
          onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
          className={`${field} max-w-[240px] text-center text-h2 tracking-[0.4em] tabular-nums`}
        />
        <p className="m-0 mt-3 text-small text-[#C4D0D2]" aria-live="polite">
          {wait > 0 ? (
            t("deliver_page.gs_resend_in", { time: `0:${String(wait).padStart(2, "0")}` })
          ) : (
            <button type="button" onClick={() => void send()} className="min-h-[44px] font-bold text-kesar-bright underline-offset-2 hover:underline">{t("deliver_page.gs_resend")}</button>
          )}
        </p>
        {error && <p role="alert" className="m-0 mt-3 rounded-[12px] bg-[#3B1A18] px-4 py-3 text-label text-[#FFD9D5]">{error}</p>}
        <button type="submit" disabled={otp.length !== 6 || busy} className={`${primary} mt-5`} data-testid="gs-verify">
          {busy ? t("deliver_page.gs_verifying") : t("deliver_page.gs_verify")}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={send} noValidate className="rounded-[20px] bg-[#14201F] p-5 sm:p-6" data-testid="gs-form" aria-label={t("deliver_page.gs_title")}>
      {user && user.phone && (
        <p className="m-0 mb-4 rounded-[12px] bg-[#1C2B2D] px-4 py-3 text-small text-[#C4D0D2]">{t("deliver_page.gs_signed_in_as", { phone: user.phone })}</p>
      )}
      <label htmlFor={ids.name} className="block text-label">{t("deliver_page.gs_name")}</label>
      <input id={ids.name} data-testid="gs-name" autoComplete="name" value={name} maxLength={80} aria-describedby={ids.nameHelp}
        onChange={(e) => setName(e.target.value)} className={field} />
      <p id={ids.nameHelp} className="m-0 mt-[6px] text-small text-[#C4D0D2]">{t("deliver_page.gs_name_help")}</p>

      <label htmlFor={ids.phone} className="mt-4 block text-label">{t("deliver_page.gs_phone")}</label>
      <span className="mt-2 flex h-14 items-center overflow-hidden rounded-[14px] border-[1.5px] border-[#3A4D50] bg-[#14201F] text-body-lg focus-within:border-kesar-bright focus-within:ring-2 focus-within:ring-kesar-bright/30">
        <span className="relative flex h-full shrink-0 items-center gap-[6px] border-r border-[#3A4D50] px-[14px] font-bold">
          {phoneCountry?.phone_code}
          {countries.length > 1 && <Chevron color="#C4D0D2" />}
          {countries.length > 1 && (
            <select aria-label={t("deliver_page.gs_country_code")} value={cc ?? ""} onChange={(e) => setCc(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0">
              {countries.map((c) => <option key={c.code} value={c.code}>{`${c.name} ${c.phone_code}`}</option>)}
            </select>
          )}
        </span>
        <input id={ids.phone} data-testid="gs-phone" type="tel" inputMode="tel" autoComplete="tel-national" value={number}
          onChange={(e) => setNumber(e.target.value.replace(/[^\d ()-]/g, ""))} className="h-full min-w-0 flex-grow bg-transparent px-4 text-white outline-none" />
      </span>

      <label htmlFor={ids.city} className="mt-4 block text-label">{t("deliver_page.gs_city")}</label>
      <span className="relative block">
        <select id={ids.city} data-testid="gs-city" value={cityCode} onChange={(e) => setCityCode(e.target.value)} className={`${field} appearance-none pr-10`}>
          {cities.map((c) => <option key={c.code} value={c.code}>{`${c.name}, ${c.region}`}</option>)}
        </select>
        <span className="pointer-events-none absolute right-4 top-[calc(50%+4px)] -translate-y-1/2"><Chevron color="#C4D0D2" /></span>
      </span>

      {error && <p role="alert" className="m-0 mt-4 rounded-[12px] bg-[#3B1A18] px-4 py-3 text-label text-[#FFD9D5]">{error}</p>}
      <button type="submit" disabled={!formOk || busy} className={`${primary} mt-5`} data-testid="gs-send">
        {busy ? t("deliver_page.gs_sending") : t("deliver_page.gs_send")}
      </button>
      <Terms />
    </form>
  );
}

function Terms() {
  const t = useT();
  // The message has {terms} and {privacy}: split on them so they can be links.
  const text = t("deliver_page.gs_terms", { terms: "\u0001", privacy: "\u0002" });
  const parts = text.split(/(\u0001|\u0002)/);
  return (
    <p className="m-0 mt-4 text-small text-[#C4D0D2]">
      {parts.map((p, i) =>
        p === "\u0001" ? <Link key={i} href="/terms" className="font-bold text-white underline underline-offset-2 hover:text-white">{t("deliver_page.gs_terms_link")}</Link>
          : p === "\u0002" ? <Link key={i} href="/privacy" className="font-bold text-white underline underline-offset-2 hover:text-white">{t("deliver_page.gs_privacy_link")}</Link>
            : <span key={i}>{p}</span>,
      )}
    </p>
  );
}

function Done({ name, phone, country, apps, onOther }: { name: string; phone: string; country: string | null; apps: Apps; onOther: () => Promise<void> }) {
  const t = useT();
  // Done renders only after hydration (the form shows a skeleton until then), so window is there.
  const origin = typeof window === "undefined" ? null : window.location.origin;
  const headRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headRef.current?.focus();
  }, []);
  const appPage = `/deliver/app${country ? `?country=${encodeURIComponent(country)}` : ""}`;
  const url = origin ? `${origin}${appPage}` : null;
  const qr = url ? qrPath(url) : null;
  const stores = [
    apps.android ? { href: apps.android, label: t("deliver_page.done_android") } : null,
    apps.ios ? { href: apps.ios, label: t("deliver_page.done_ios") } : null,
  ].filter((x): x is { href: string; label: string } => !!x);
  return (
    <div className="rounded-[20px] bg-white p-5 text-kohl sm:p-6" data-testid="gs-done" role="status">
      <h3 ref={headRef} tabIndex={-1} className="m-0 text-h2 outline-none">{t("deliver_page.done_title", { name })}</h3>
      <p className="m-0 mt-2 text-body text-muted">{t("deliver_page.done_body", { phone })}</p>
      <div className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-center">
        {qr && (
          <figure className="m-0 hidden shrink-0 sm:block">
            <svg data-testid="gs-qr" data-url={url ?? ""} role="img" aria-label={t("deliver_page.qr_alt", { url: url ?? "" })} viewBox={`0 0 ${qr.size} ${qr.size}`}
              width="152" height="152" shapeRendering="crispEdges" className="rounded-[12px] border border-line">
              <rect width={qr.size} height={qr.size} fill="#fff" />
              <path d={qr.d} fill="#111418" />
            </svg>
            <figcaption className="mt-2 max-w-[152px] text-small text-muted">{t("deliver_page.done_scan")}</figcaption>
          </figure>
        )}
        <div className="flex flex-1 flex-col gap-3">
          {stores.map((s) => (
            <a key={s.href} href={s.href} rel="noopener noreferrer" className="inline-flex h-12 items-center justify-center rounded-full bg-kohl px-5 text-label text-white hover:text-white">
              {s.label}
            </a>
          ))}
          {!stores.length && <p className="m-0 text-small text-muted">{t("deliver_page.done_not_yet")}</p>}
          <Link href={appPage} data-testid="gs-app-link" className={`inline-flex h-12 items-center justify-center rounded-full px-5 text-label ${stores.length ? "border-[1.5px] border-line-strong text-kohl" : "bg-peacock text-white hover:bg-peacock-deep hover:text-white"}`}>
            {stores.length ? t("deliver_page.done_get_app") : t("deliver_page.done_how")}
          </Link>
        </div>
      </div>
      <button type="button" onClick={() => void onOther()} className="mt-5 min-h-[44px] text-label text-peacock underline-offset-2 hover:underline">
        {t("deliver_page.done_other")}
      </button>
    </div>
  );
}
