"use client";

/**
 * "Legal entity" (R15): who operates BhojanGo in this country, saved as its `legal` setting and
 * shown on the Terms and Privacy pages, the website footer, receipts, emails and admin Finance.
 * Countries with GST (India) also need the CIN, GSTIN and a grievance officer. Empty fields stay
 * empty (never invented) and are flagged as required before launch (the API's legal_missing).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiError, can, type CountrySummary, marketsApi, useAdminMe } from "@/lib/markets";

const LABELS: Record<string, { label: string; hint?: string; type?: string }> = {
  name: { label: "Legal name" },
  address: { label: "Registered address" },
  support_email: { label: "Support email", type: "email" },
  support_phone: { label: "Support phone", type: "tel", hint: "With the country code" },
  cin: { label: "CIN", hint: "Corporate Identity Number, 21 characters" },
  gstin: { label: "GSTIN", hint: "15 characters" },
  grievance_name: { label: "Grievance officer: name" },
  grievance_email: { label: "Grievance officer: email", type: "email" },
  grievance_phone: { label: "Grievance officer: phone", type: "tel" },
};
const BASE = ["name", "address", "support_email", "support_phone"];
const GST = ["cin", "gstin", "grievance_name", "grievance_email", "grievance_phone"];

export function LegalEntity({ country }: { country: CountrySummary }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const keys = country.tax_regime === "gst" ? [...BASE, ...GST] : BASE;
  const saved = (country.settings.legal ?? {}) as Record<string, string>;
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(keys.map((k) => [k, saved[k] ?? ""])));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const editable = can(me, "markets.edit", country.code);
  const missing = country.legal_missing ?? [];
  const changed = keys.some((k) => (values[k] ?? "") !== (saved[k] ?? ""));

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const legal = Object.fromEntries(keys.map((k) => [k, values[k].trim() || null]));
      await marketsApi.updateCountry(country.code, { settings: { legal } });
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setMsg({ ok: true, text: "Saved. Pages, receipts and emails use it from now on." });
    } catch (e) {
      setMsg({ ok: false, text: apiError(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Legal entity" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Legal entity</h2>
        {editable ? (
          <button type="button" disabled={busy || !changed} onClick={() => void save()}
            className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50">Save legal entity</button>
        ) : null}
      </div>
      <p className="mt-1 text-small text-muted">Who operates BhojanGo in {country.name}: shown on the Terms and Privacy pages, the website footer, receipts, emails and Finance.</p>
      {missing.length ? (
        <p role="note" data-testid="legal-missing" className="mt-3 rounded-xl bg-kesar-tint px-3 py-2 text-small text-kesar-ink">
          Required before launch: {missing.map((k) => LABELS[k]?.label ?? k).join(", ")}.
        </p>
      ) : null}
      <div className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]">
        {keys.map((k) => (
          <label key={k} className="text-small font-bold">{LABELS[k].label}
            <input aria-label={LABELS[k].label} type={LABELS[k].type ?? "text"} value={values[k]} disabled={!editable || busy}
              onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))} placeholder={missing.includes(k) ? "Required before launch" : undefined}
              className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal" />
            {LABELS[k].hint ? <span className="mt-1 block font-normal text-muted">{LABELS[k].hint}</span> : null}
          </label>
        ))}
      </div>
      {msg ? <p role="status" className={`mt-3 text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
    </section>
  );
}
