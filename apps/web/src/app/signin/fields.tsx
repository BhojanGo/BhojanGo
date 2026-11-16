"use client";
// The sign-in pages' fields: an email box, a password box with Show / Hide, and
// six boxes for a code (typing moves on, pasting fills them all, Backspace goes back).
import { forwardRef, useId, useRef, useState } from "react";

import { useT } from "@/lib/i18n";

export const fieldBox = "mt-2 block h-14 w-full rounded-[14px] border-[1.5px] border-[#C9D3D4] bg-white px-4 text-body-lg text-[#111418] outline-none focus:border-2 focus:border-[#0B5D66] aria-[invalid=true]:border-[#8C1D18]";
export const primaryBtn = "mt-5 h-14 w-full rounded-full bg-[#0B5D66] px-[22px] text-label text-white hover:bg-[#083F46] disabled:bg-[#8FB3B7]";
export const textBtn = "min-h-[44px] text-label font-bold text-[#0B5D66] underline-offset-4 hover:underline";

export function EmailField({ value, onChange, invalid, describedBy, autoFocus }: {
  value: string; onChange: (v: string) => void; invalid?: boolean; describedBy?: string; autoFocus?: boolean;
}) {
  const t = useT();
  const id = useId();
  return (
    <div className="mt-6">
      <label htmlFor={id} className="block text-label">{t("auth.email")}</label>
      <input id={id} name="email" type="email" inputMode="email" autoComplete="username" autoCapitalize="none" spellCheck={false}
        autoFocus={autoFocus} required value={value} onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid || undefined} aria-describedby={describedBy} className={fieldBox} />
    </div>
  );
}

export const PasswordField = forwardRef<HTMLInputElement, {
  label: string; value: string; onChange: (v: string) => void; isNew?: boolean; hint?: string; invalid?: boolean; autoFocus?: boolean;
}>(function PasswordField({ label, value, onChange, isNew, hint, invalid, autoFocus }, ref) {
  const t = useT();
  const id = useId();
  const hintId = useId();
  const [shown, setShown] = useState(false);
  return (
    <div className="mt-4">
      <label htmlFor={id} className="block text-label">{label}</label>
      <span className="relative mt-2 block">
        <input ref={ref} id={id} name={isNew ? "new-password" : "password"} type={shown ? "text" : "password"}
          autoComplete={isNew ? "new-password" : "current-password"} autoFocus={autoFocus} required
          minLength={isNew ? 10 : undefined} maxLength={128} value={value} onChange={(e) => onChange(e.target.value)}
          aria-invalid={invalid || undefined} aria-describedby={hint ? hintId : undefined}
          className={`${fieldBox} mt-0 pr-[88px]`} />
        <button type="button" onClick={() => setShown((s) => !s)} aria-pressed={shown} aria-controls={id}
          className="absolute right-1 top-1/2 h-11 -translate-y-1/2 rounded-full px-4 text-label font-bold text-[#0B5D66] hover:bg-[#EFF6F6]">
          {shown ? t("auth.hide") : t("auth.show")}
        </button>
      </span>
      {hint && <p id={hintId} className="m-0 mt-[6px] text-small text-muted">{hint}</p>}
    </div>
  );
});

const EMPTY = ["", "", "", "", "", ""];

/** Six boxes; ``onChange`` gets the digits typed so far (6 when complete). Remount (key) to clear. */
export function CodeBoxes({ onChange, legend }: { onChange: (code: string) => void; legend: string }) {
  const t = useT();
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const [digits, setDigits] = useState<string[]>(EMPTY);

  function set(next: string[]) {
    setDigits(next);
    onChange(next.every(Boolean) ? next.join("") : next.join("").slice(0, 5));
  }

  function fill(from: number, text: string) {
    const clean = text.replace(/\D/g, "");
    if (!clean) return;
    const out = [...digits];
    for (let i = 0; i < clean.length && from + i < 6; i++) out[from + i] = clean[i] ?? "";
    set(out);
    boxes.current[Math.min(5, from + clean.length)]?.focus();
  }

  return (
    <fieldset className="m-0 mt-6 border-0 p-0">
      <legend className="mb-2 text-label">{legend}</legend>
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
              set(digits.map((x, j) => (j === i ? v : x)));
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
            className="h-[60px] w-[48px] rounded-[14px] border-[1.5px] border-[#C9D3D4] text-center text-h2 outline-none focus:border-2 focus:border-[#0B5D66] md:h-[64px] md:w-[56px]"
          />
        ))}
      </div>
    </fieldset>
  );
}
