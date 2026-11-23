"use client";

/**
 * "Kitchen offer ceiling" (R22 security review, S11): the most a kitchen's own offer
 * may give, set on a country's page and overridden on a city's page. An empty box is
 * inherited from the level above (country, then BhojanGo's default for the currency).
 * The API refuses a kitchen offer above it (markets/service/offer_ceiling.py).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiError, can, marketsApi, moneySymbol, useAdminMe } from "@/lib/markets";
import { CEILING_FIELDS, CEILING_SETTING, type Ceiling, ceilingPatch, effectiveCeiling, ownCeiling } from "@/lib/offerCeiling";

interface Props {
  /** Where the setting is saved. */
  level: "country" | "city";
  code: string;
  name: string;
  currency: string;
  /** This level's settings. */
  settings: Record<string, unknown>;
  /** The levels above, country first (a city: its country and state). */
  parents: { name: string; settings: Record<string, unknown> | null | undefined }[];
}

export function OfferCeiling({ level, code, name, currency, settings, parents }: Props) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const own = ownCeiling(settings);
  const [form, setForm] = useState<Ceiling>(own);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const editable = can(me, "markets.edit", code);
  const inherited = effectiveCeiling(parents, currency);
  const sym = moneySymbol(currency);
  const changed = JSON.stringify(ceilingPatch(form)) !== JSON.stringify(Object.keys(own).length ? own : null);

  async function save() {
    const patch = ceilingPatch(form);
    if (patch && "error" in patch) {
      setMsg({ ok: false, text: patch.error as string });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const body = { settings: { [CEILING_SETTING]: patch } };
      if (level === "country") await marketsApi.updateCountry(code, body);
      else await marketsApi.updateCity(code, body);
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setMsg({ ok: true, text: "Saved. New restaurant offers must stay within it; running offers carry on." });
    } catch (e) {
      setMsg({ ok: false, text: apiError(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Restaurant offer ceiling" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Restaurant offer ceiling</h2>
        {editable ? (
          <button type="button" disabled={busy || !changed} onClick={() => void save()}
            className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50">Save offer ceiling</button>
        ) : null}
      </div>
      <p className="mt-1 text-small text-muted">
        The most an offer a kitchen in {name} pays for itself may give, in {currency}. Kitchens can&apos;t start an offer above it.
        {level === "city" ? " Leave a box empty to use the country's." : " Cities can set their own."}
      </p>
      <fieldset className="mt-4 grid gap-3 border-0 p-0 [grid-template-columns:repeat(auto-fill,minmax(200px,1fr))]" disabled={!editable || busy}>
        <legend className="sr-only">Kitchen offer ceiling in {name}</legend>
        {CEILING_FIELDS.map((f) => {
          const from = inherited[f.key];
          return (
            <label key={f.key} className="block text-label">
              {f.label}
              <span className="mt-1 flex items-center gap-1 rounded-xl border border-line px-3">
                <span className="text-muted">{sym.trim()}</span>
                <input inputMode="decimal" value={form[f.key] ?? ""} placeholder={from ? from.value : "not set"}
                  onChange={(e) => { setMsg(null); setForm({ ...form, [f.key]: e.target.value.replace(/[^\d.]/g, "") }); }}
                  className="h-11 w-full bg-transparent font-normal outline-none" />
              </span>
              <span className="mt-1 block text-small font-normal text-muted">
                {f.note}. {form[f.key] ? `Set here (${name}).` : from ? `From ${from.source}: ${sym}${from.value}.` : "Not set: restaurant offers are refused."}
              </span>
            </label>
          );
        })}
      </fieldset>
      {msg ? <p role="status" className={`mt-3 text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
    </section>
  );
}
