"use client";
// CustomerSignIn.html / CustomerOTP.html on the web: phone, then a 6-digit code.
import { errorMessage } from "@bhojango/api-client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { useSession } from "@/lib/client";
import { Button } from "@bhojango/ui";

const CODES = { IN: "+91", US: "+1" } as const;

function SignInForm() {
  const router = useRouter();
  const next = useSearchParams().get("next") ?? "/";
  const { sendCode, verify } = useSession();
  const [country, setCountry] = useState<"IN" | "US">("IN");
  const [number, setNumber] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const digits = number.replace(/\D/g, "");

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const phone = `${CODES[country]}${digits}`;
    try {
      await sendCode(phone, country);
      setSent(phone);
    } catch (err) {
      setError(errorMessage((err as { body?: unknown }).body, "We couldn't send a code. Check the number and try again."));
    } finally {
      setBusy(false);
    }
  }

  async function check(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await verify(sent!, code, country);
      router.replace(next.startsWith("/") ? next : "/");
    } catch (err) {
      setError(errorMessage((err as { body?: unknown }).body, "That code didn't work. Check it and try again."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-5 py-14">
      {!sent ? (
        <form onSubmit={send} className="space-y-4 rounded-sheet bg-white p-8 shadow-float">
          <h1 className="font-display text-3xl font-semibold">Sign in or sign up</h1>
          <p className="text-muted">We&apos;ll text you a code. No password needed.</p>
          <label className="block text-sm font-bold" htmlFor="phone">Mobile number</label>
          <div className="flex gap-2">
            <select aria-label="Country code" value={country} onChange={(e) => setCountry(e.target.value as "IN" | "US")}
              className="h-14 rounded-card border-[1.5px] border-line-strong px-3 font-extrabold">
              <option value="IN">IN +91</option>
              <option value="US">US +1</option>
            </select>
            <input id="phone" name="phone" inputMode="tel" autoComplete="tel-national" value={number} onChange={(e) => setNumber(e.target.value)}
              placeholder={country === "IN" ? "98480 21234" : "(208) 555-0199"} className="h-14 min-w-0 flex-1 rounded-card border-[1.5px] border-line-strong px-4 text-lg font-semibold" />
          </div>
          {error ? <p role="alert" className="text-sm font-semibold text-chili">{error}</p> : null}
          <Button type="submit" block size="lg" loading={busy} disabled={digits.length !== 10}>Send code</Button>
          <p className="text-center text-xs text-muted">By continuing you agree to our Terms and Privacy notice.</p>
        </form>
      ) : (
        <form onSubmit={check} className="space-y-4 rounded-sheet bg-white p-8 shadow-float">
          <h1 className="font-display text-3xl font-semibold">Enter the 6-digit code</h1>
          <p className="text-muted">Sent to <b className="text-kohl">{sent}</b> · <button type="button" className="font-bold text-peacock" onClick={() => setSent(null)}>Edit</button></p>
          <input aria-label="Code" name="code" inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={6} value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            className="h-16 w-full rounded-card border-[1.5px] border-line-strong text-center text-3xl font-extrabold tracking-[0.5em]" />
          {error ? <p role="alert" className="text-sm font-semibold text-chili">{error}</p> : null}
          <Button type="submit" block size="lg" loading={busy} disabled={code.length !== 6}>Verify</Button>
        </form>
      )}
    </div>
  );
}

export default function SignIn() {
  return <Suspense><SignInForm /></Suspense>;
}
