"use client";

/**
 * "Payment methods" (R13): what checkout offers in this country, saved as its
 * payment_methods setting. Stripe countries show the Stripe ones (cards, and Apple Pay /
 * Google Pay, which run on cards; never Link); Razorpay countries UPI, wallets and net
 * banking. The API checks the list (markets/service/pay_methods.py).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiError, can, type CountrySummary, marketsApi, useAdminMe } from "@/lib/markets";

export const PAYMENT_METHODS: { key: string; label: string; note: string }[] = [
  { key: "card", label: "Cards", note: "Credit and debit cards" },
  { key: "apple_pay", label: "Apple Pay", note: "Runs on cards" },
  { key: "google_pay", label: "Google Pay", note: "Runs on cards" },
  { key: "upi", label: "UPI", note: "Razorpay" },
  { key: "wallet", label: "Wallets", note: "Razorpay" },
  { key: "net_banking", label: "Net banking", note: "Razorpay" },
];

export function PaymentMethods({ country }: { country: CountrySummary }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const saved = Array.isArray(country.settings.payment_methods) ? (country.settings.payment_methods as string[]) : ["card"];
  const [picked, setPicked] = useState<string[]>(saved);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const editable = can(me, "markets.edit", country.code);
  const changed = [...picked].sort().join() !== [...saved].sort().join();

  function toggle(key: string) {
    setMsg(null);
    setPicked((p) => (p.includes(key) ? p.filter((k) => k !== key) : [...p, key]));
  }

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const order = PAYMENT_METHODS.map((m) => m.key).filter((k) => picked.includes(k));
      await marketsApi.updateCountry(country.code, { settings: { payment_methods: order } });
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setMsg({ ok: true, text: "Saved. Checkout offers these from the next payment." });
    } catch (e) {
      setMsg({ ok: false, text: apiError(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Payment methods" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Payment methods</h2>
        {editable ? (
          <button type="button" disabled={busy || !changed || picked.length === 0} onClick={() => void save()}
            className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50">Save payment methods</button>
        ) : null}
      </div>
      <p className="mt-1 text-small text-muted">What checkout offers in {country.name}, on the website and in the app. Link and other wallets Stripe adds are never offered.</p>
      <fieldset className="mt-4 grid gap-3 border-0 p-0 [grid-template-columns:repeat(auto-fill,minmax(180px,1fr))]" disabled={!editable || busy}>
        <legend className="sr-only">Payment methods in {country.name}</legend>
        {PAYMENT_METHODS.map((m) => (
          <label key={m.key} className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl border border-line-soft p-3">
            <input type="checkbox" checked={picked.includes(m.key)} onChange={() => toggle(m.key)} className="h-5 w-5 accent-[#0B5D66]" />
            <span><span className="block font-bold">{m.label}</span><span className="block text-small text-muted">{m.note}</span></span>
          </label>
        ))}
      </fieldset>
      {msg ? <p role="status" className={`mt-3 text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
    </section>
  );
}
