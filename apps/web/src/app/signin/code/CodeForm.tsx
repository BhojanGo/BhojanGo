"use client";
// Six boxes for the code (WebOTP): typing moves on, pasting fills them all,
// Backspace goes back. Resend after a short wait. Then back to where they were.
import { errorMessage } from "@bhojango/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";
import { placeFromDefaultAddress } from "../afterSignIn";

const WAIT = 30; // seconds before "Resend"
const EMPTY = ["", "", "", "", "", ""];

export function CodeForm({ phone, country, next, hasPlace }: { phone: string; country: string; next: string; hasPlace: boolean }) {
  const t = useT();
  const router = useRouter();
  const { sendCode, verify } = useSession();
  const [digits, setDigits] = useState<string[]>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentAt, setSentAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const code = digits.join("");
  const wait = Math.max(0, WAIT - Math.floor((now - sentAt) / 1000));

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  function fill(from: number, text: string) {
    const clean = text.replace(/\D/g, "");
    if (!clean) return;
    setDigits((d) => {
      const out = [...d];
      for (let i = 0; i < clean.length && from + i < 6; i++) out[from + i] = clean[i] ?? "";
      return out;
    });
    boxes.current[Math.min(5, from + clean.length)]?.focus();
  }

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (code.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      await verify(phone, code, country);
      await placeFromDefaultAddress(hasPlace);
      router.replace(next);
      router.refresh();
    } catch (err) {
      setError(errorMessage((err as { body?: unknown }).body, t("signin.code_failed")));
      setDigits(EMPTY);
      boxes.current[0]?.focus();
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    try {
      await sendCode(phone, country);
      setSentAt(Date.now());
    } catch (err) {
      setError(errorMessage((err as { body?: unknown }).body, t("signin.send_failed")));
    }
  }

  return (
    <form onSubmit={check} noValidate>
      <Link href={`/signin?next=${encodeURIComponent(next)}`} className="inline-flex items-center gap-[6px] text-[15px] font-extrabold">
        <span aria-hidden="true">←</span> {t("signin.change_number")}
      </Link>
      <h1 className="m-0 mt-4 font-display text-[30px] font-semibold tracking-[-0.8px] md:text-[40px] md:tracking-[-1px]">{t("signin.code_heading")}</h1>
      <p className="m-0 mt-1 text-base text-[#4C5A5E]">
        {t("signin.sent_to")} <b className="text-[#111418]">{phone}</b>
      </p>
      <fieldset className="m-0 mt-7 border-0 p-0">
        <legend className="sr-only">{t("signin.code_label")}</legend>
        <div className="flex gap-2 md:gap-[10px]">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => {
                boxes.current[i] = el;
              }}
              aria-label={t("signin.digit", { n: i + 1 })}
              inputMode="numeric"
              autoComplete={i === 0 ? "one-time-code" : "off"}
              autoFocus={i === 0}
              maxLength={6}
              value={d}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "");
                if (v.length > 1) return fill(i, v);
                setDigits((all) => all.map((x, j) => (j === i ? v : x)));
                if (v) boxes.current[i + 1]?.focus();
              }}
              onKeyDown={(e) => {
                if (e.key === "Backspace" && !digits[i] && i > 0) boxes.current[i - 1]?.focus();
                if (e.key === "ArrowLeft" && i > 0) boxes.current[i - 1]?.focus();
                if (e.key === "ArrowRight" && i < 5) boxes.current[i + 1]?.focus();
              }}
              onPaste={(e) => {
                e.preventDefault();
                fill(i, e.clipboardData.getData("text"));
              }}
              className="h-[60px] w-[48px] rounded-[14px] border-[1.5px] border-[#C9D3D4] text-center text-[28px] font-bold outline-none focus:border-2 focus:border-[#0B5D66] md:h-[70px] md:w-[62px]"
            />
          ))}
        </div>
      </fieldset>
      <p className="m-0 mt-4 text-sm text-[#4C5A5E]" aria-live="polite">
        {t("signin.didnt_get")}{" "}
        {wait > 0 ? (
          <b className="text-[#111418]">{t("signin.resend_in", { time: `0:${String(wait).padStart(2, "0")}` })}</b>
        ) : (
          <button type="button" onClick={() => void resend()} className="font-extrabold text-[#0B5D66]">{t("signin.resend")}</button>
        )}
      </p>
      {error && <p role="alert" className="m-0 mt-3 text-sm font-semibold text-[#8C1D18]">{error}</p>}
      <button type="submit" disabled={code.length !== 6 || busy} className="mt-6 h-14 w-full rounded-full bg-[#0B5D66] px-[22px] text-[15px] font-extrabold text-white hover:bg-[#083F46] disabled:bg-[#8FB3B7]">
        {busy ? t("signin.verifying") : t("signin.verify")}
      </button>
      <p className="m-0 mt-5 rounded-2xl bg-[#EFF6F6] px-4 py-3 text-sm text-[#083F46]">{t("signin.never_ask")}</p>
    </form>
  );
}
