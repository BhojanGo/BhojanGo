"use client";
// "Notify me": coming-soon cities, addresses outside every zone, and "Don't see
// your city?". Stored as a waitlist sign-up (city, email, consent, time); Markets
// shows the demand per city.

import { useState } from "react";

import { urls } from "@/lib/client";
import { useLanguage, useT } from "@/lib/i18n";

export function NotifyMe({
  variant = "band",
  cityCode,
  cityName,
  point,
  source,
  title,
}: {
  variant?: "band" | "card";
  cityCode?: string | null;
  cityName?: string | null;
  point?: { lat: number; lng: number } | null;
  source: "soon_city" | "outside_zone" | "suggest_city";
  title?: string;
}) {
  const t = useT();
  const { language, country } = useLanguage();
  const [email, setEmail] = useState("");
  const [city, setCity] = useState("");
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [problem, setProblem] = useState<string | null>(null);
  const askCity = !cityCode && !point;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!consent) {
      setProblem(t("notify.consent_needed"));
      return;
    }
    setState("busy");
    setProblem(null);
    const r = await fetch(`${urls.core}/api/v1/markets/waitlist`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email,
        consent,
        source,
        locale: `${language}-${country?.code ?? "US"}`,
        ...(cityCode ? { city_code: cityCode } : {}),
        ...(askCity ? { city_text: city } : {}),
        ...(point ? { lat: point.lat, lng: point.lng } : {}),
      }),
    }).catch(() => null);
    if (r && r.ok) setState("done");
    else {
      setState("error");
      setProblem(t("common.error"));
    }
  }

  const done = state === "done";
  const dark = variant === "band";
  const field = `h-12 min-w-0 rounded-full px-[18px] text-body outline-none ${dark ? "bg-[#1E2A2D] text-white placeholder:text-[#A9B8BA]" : "border border-[#E2E7E8] bg-white text-[#111418] placeholder:text-[#4C5A5E]"}`;
  return (
    <section
      id={source === "suggest_city" ? "suggest" : undefined}
      aria-label={t("notify.title")}
      className={dark ? "rounded-[20px] bg-[#111418] px-6 py-5 text-white md:flex md:items-center md:gap-4" : "rounded-[20px] border border-[#E2E7E8] bg-[#F4F6F6] p-6"}
    >
      <p className={`m-0 text-h3 ${dark ? "md:flex-grow" : ""}`}>
        {title ?? (cityName ? t("notify.city_title", { city: cityName }) : t("notify.band_title"))}
      </p>
      {done ? (
        <p role="status" className={`m-0 mt-3 font-bold md:mt-0 ${dark ? "text-[#E8A93C]" : "text-[#0B5D66]"}`}>
          {t("notify.done")}
        </p>
      ) : (
        <form onSubmit={submit} className="mt-3 flex flex-col gap-2 md:mt-0">
          <div className="flex flex-col gap-2 sm:flex-row">
            {askCity && (
              <input required aria-label={t("notify.city")} placeholder={t("notify.city")} value={city} onChange={(e) => setCity(e.target.value)} className={`${field} sm:w-[180px]`} />
            )}
            <input required type="email" aria-label={t("notify.email")} placeholder={t("notify.email")} value={email} onChange={(e) => setEmail(e.target.value)} className={`${field} sm:w-[240px]`} />
            <button type="submit" disabled={state === "busy"} className="h-12 shrink-0 rounded-full bg-[#E8A93C] px-6 font-bold text-[#111418] disabled:opacity-60">
              {t("notify.button")}
            </button>
          </div>
          <label className={`flex items-start gap-2 text-small ${dark ? "text-[#A9B8BA]" : "text-[#4C5A5E]"}`}>
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-[2px]" />
            {t("notify.consent")}
          </label>
          {problem && <span role="alert" className={`text-small ${dark ? "text-[#F2B8B5]" : "text-[#A3271F]"}`}>{problem}</span>}
        </form>
      )}
    </section>
  );
}
