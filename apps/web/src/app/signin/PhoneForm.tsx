"use client";
// The phone number (WebSignIn): the country's calling code comes from Markets
// (the directory), the code is sent by SMS, then /signin/code.
import { errorMessage } from "@bhojango/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { Chevron } from "@/components/Icons";
import { useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";

type Country = { code: string; name: string; phone_code: string };

export function PhoneForm({ countries, initial, next }: { countries: Country[]; initial: string | null; next: string }) {
  const t = useT();
  const router = useRouter();
  const sendCode = useSession((s) => s.sendCode);
  const [code, setCode] = useState(initial);
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();
  const helpId = useId();
  const country = countries.find((c) => c.code === code) ?? null;
  const digits = number.replace(/\D/g, "");
  const ok = !!country && digits.length >= 6 && digits.length <= 15;

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!country || !ok) return;
    setBusy(true);
    setError(null);
    const phone = `${country.phone_code}${digits}`;
    try {
      await sendCode(phone, country.code as "IN" | "US");
      router.push(`/signin/code?${new URLSearchParams({ phone, country: country.code, next })}`);
    } catch (err) {
      setError(errorMessage((err as { body?: unknown }).body, t("signin.send_failed")));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={send} noValidate>
      <h1 className="m-0 font-display text-[30px] font-semibold leading-[1.1] tracking-[-0.8px] md:text-[40px] md:tracking-[-1px]">{t("signin.heading")}</h1>
      <p className="m-0 mt-2 hidden text-base text-[#4C5A5E] md:block">{t("signin.sub")}</p>
      <div className="mt-6 md:mt-8">
        <label htmlFor={inputId} className="block text-sm font-bold">{t("signin.mobile")}</label>
        <span className="mt-2 flex h-14 items-center overflow-hidden rounded-[14px] border-2 border-[#0B5D66] text-[17px] focus-within:ring-2 focus-within:ring-[#0B5D66]/30">
          <span className="relative flex h-full shrink-0 items-center gap-[6px] border-r border-[#E2E7E8] px-[14px] font-bold">
            {country && <span className="rounded-[5px] bg-[#111418] px-[5px] py-[2px] text-[11px] font-extrabold text-white">{country.code}</span>}
            {country?.phone_code}
            {countries.length > 1 && <Chevron color="#4C5A5E" />}
            {countries.length > 1 && (
              <select aria-label={t("signin.country_code")} value={code ?? ""} onChange={(e) => setCode(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0">
                {countries.map((c) => (
                  <option key={c.code} value={c.code}>{`${c.name} ${c.phone_code}`}</option>
                ))}
              </select>
            )}
          </span>
          <input
            id={inputId}
            name="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            autoFocus
            aria-describedby={helpId}
            value={number}
            onChange={(e) => setNumber(e.target.value.replace(/[^\d ()-]/g, ""))}
            className="h-full min-w-0 flex-grow bg-transparent px-4 outline-none"
          />
        </span>
        <p id={helpId} className="m-0 mt-[6px] text-[13px] text-[#4C5A5E]">{t("signin.help")}</p>
      </div>
      {error && <p role="alert" className="m-0 mt-3 text-sm font-semibold text-[#8C1D18]">{error}</p>}
      <button type="submit" disabled={!ok || busy} className="mt-5 h-14 w-full rounded-full bg-[#0B5D66] px-[22px] text-[15px] font-extrabold text-white hover:bg-[#083F46] disabled:bg-[#8FB3B7]">
        {busy ? t("signin.sending") : t("signin.send_code")}
      </button>
      <div className="mt-7 hidden rounded-2xl bg-[#F4F6F6] p-4 text-sm leading-[1.5] md:block">
        <b>{t("signin.partner_q")}</b> <span className="text-[#4C5A5E]">{t("signin.partner_note")}</span>{" "}
        <Link href="/partner" className="font-bold">{t("signin.add_kitchen")}</Link> · <Link href="/ride" className="font-bold">{t("signin.ride")}</Link>
      </div>
    </form>
  );
}
