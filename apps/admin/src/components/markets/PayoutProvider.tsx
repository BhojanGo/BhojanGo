"use client";

/**
 * "Payouts": who pays this country's kitchens and riders (countries.payout_provider).
 * Payout accounts are opened, and payout runs paid, with this provider. A country
 * with none can't open; the API refuses the fake one in production.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  apiError,
  can,
  type CountrySummary,
  marketsApi,
  PAYOUT_PROVIDERS,
  type PayoutProviderName,
  payoutLabel,
  useAdminMe,
} from "@/lib/markets";

export function PayoutProvider({ country }: { country: CountrySummary }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const [picked, setPicked] = useState<PayoutProviderName>(country.payout_provider);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const editable = can(me, "markets.edit", country.code);

  async function save() {
    setBusy(true);
    setProblem(null);
    setDone(false);
    try {
      await marketsApi.updateCountry(country.code, { payout_provider: picked });
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setDone(true);
    } catch (e) {
      setProblem(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Payouts" className="rounded-2xl border border-line bg-white p-6">
      <h2 className="m-0 text-h3">Payouts</h2>
      <p className="mt-1 text-small text-muted">
        Who pays {country.name}&apos;s kitchens and riders each week: their payout accounts are opened, and payout runs paid, with
        this provider. Now: <b className="text-kohl">{payoutLabel(country.payout_provider)}</b>.
        {country.payout_provider === "none" && " The country can't open until one is chosen."}
      </p>
      {editable && (
        <form
          className="mt-4 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label className="min-w-[260px] text-small text-muted">
            Payout provider
            <select
              value={picked}
              onChange={(e) => {
                setPicked(e.target.value as PayoutProviderName);
                setDone(false);
              }}
              className="mt-1 block w-full rounded-lg border border-line px-3 py-2 text-small text-kohl"
            >
              {PAYOUT_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || picked === country.payout_provider}
            className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50"
          >
            Save payout provider
          </button>
        </form>
      )}
      {done && (
        <p role="status" className="mt-3 text-label text-peacock-dark">
          Saved.
        </p>
      )}
      {problem && (
        <p role="alert" className="mt-3 rounded-xl bg-danger-tint p-3 text-small text-danger-ink">
          {problem}
        </p>
      )}
    </section>
  );
}
