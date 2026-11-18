"use client";

/**
 * "Delivery partners": what the website's /deliver page says it takes to deliver in
 * this country, and where to get BhojanGo Delivery. Saved as the country's
 * delivery_partner setting; the API refuses a document the delivery app doesn't
 * collect (markets/service/delivery.py). Pay itself comes from the pricing rules,
 * not from here.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiError, can, type CountrySummary, marketsApi, useAdminMe } from "@/lib/markets";

const VEHICLES: [string, string][] = [["motorcycle", "Motorcycle"], ["scooter", "Scooter"], ["electric_scooter", "Electric scooter"], ["car", "Car"]];
// One choice per step of the delivery app's onboarding; the words differ by country.
const STEPS: { step: string; label: string; options: [string, string][] }[] = [
  { step: "licence", label: "Licence", options: [["driving_licence", "Driving licence"], ["drivers_license", "Driver's license"]] },
  { step: "insurance", label: "Vehicle papers", options: [["vehicle_rc_insurance", "Vehicle RC and insurance"], ["vehicle_insurance", "Vehicle insurance"]] },
  { step: "payout", label: "Payout", options: [["bank_account", "A bank account"], ["payout_account", "A payout account"]] },
  { step: "background_check", label: "Background check", options: [["background_check", "A background check"]] },
];

type Terms = { min_age?: number; vehicles?: string[]; documents?: string[]; example_trip?: { distance: number }; app_links?: { android?: string | null; ios?: string | null } };

export function DeliveryPartners({ country }: { country: CountrySummary }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const saved = ((country.settings as Record<string, unknown>).delivery_partner ?? {}) as Terms;
  const docs = saved.documents ?? [];
  const [f, setF] = useState({
    age: saved.min_age ? String(saved.min_age) : "",
    vehicles: saved.vehicles ?? [],
    docs: Object.fromEntries(STEPS.map((s) => [s.step, s.options.find(([k]) => docs.includes(k))?.[0] ?? ""])) as Record<string, string>,
    distance: String(saved.example_trip?.distance ?? 3),
    android: saved.app_links?.android ?? "",
    ios: saved.app_links?.ios ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const editable = can(me, "markets.edit", country.code);

  async function save() {
    setBusy(true);
    setProblem(null);
    setDone(false);
    const value = {
      ...(f.age ? { min_age: Number(f.age) } : {}),
      vehicles: f.vehicles,
      documents: STEPS.map((s) => f.docs[s.step]).filter(Boolean),
      example_trip: { distance: Number(f.distance) },
      app_links: { android: f.android.trim() || null, ios: f.ios.trim() || null },
    };
    try {
      await marketsApi.updateCountry(country.code, { settings: { delivery_partner: value } });
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setDone(true);
    } catch (e) {
      setProblem(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  const input = "mt-1 block w-full rounded-lg border border-line px-3 py-2 text-small text-kohl disabled:bg-[#FAFBFB]";
  return (
    <section aria-label="Delivery partners" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Delivery partners</h2>
        {editable && (
          <button type="button" disabled={busy || f.vehicles.length === 0} onClick={() => void save()}
            className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50">
            Save
          </button>
        )}
      </div>
      <p className="mt-1 text-small text-muted">
        What the website&apos;s Deliver with BhojanGo page lists for {country.name}. Each document is a step the BhojanGo Delivery app
        asks for. Pay on that page comes from the pricing rules (delivery partner pay, minimum hourly pay, batch bonus).
      </p>
      <fieldset disabled={!editable || busy} className="mt-4 grid gap-5 border-0 p-0 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
        <label className="text-small text-muted">
          Minimum age
          <input type="number" min={16} max={25} value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} className={input} />
        </label>
        <label className="text-small text-muted">
          Example trip ({country.distance_unit}, kitchen to customer)
          <input type="number" min={0.5} max={20} step={0.5} value={f.distance} onChange={(e) => setF({ ...f, distance: e.target.value })} className={input} />
        </label>
        <div>
          <div className="text-small text-muted">Vehicles</div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-2">
            {VEHICLES.map(([k, label]) => (
              <label key={k} className="inline-flex min-h-[32px] items-center gap-2 text-small text-kohl">
                <input type="checkbox" checked={f.vehicles.includes(k)}
                  onChange={(e) => setF({ ...f, vehicles: e.target.checked ? [...f.vehicles, k] : f.vehicles.filter((v) => v !== k) })} />
                {label}
              </label>
            ))}
          </div>
        </div>
        {STEPS.map((s) => (
          <label key={s.step} className="text-small text-muted">
            {s.label}
            <select value={f.docs[s.step]} onChange={(e) => setF({ ...f, docs: { ...f.docs, [s.step]: e.target.value } })} className={input}>
              <option value="">Not listed</option>
              {s.options.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </label>
        ))}
        <label className="text-small text-muted">
          Google Play link (empty until published)
          <input type="url" placeholder="https://play.google.com/store/apps/details?id=…" value={f.android} onChange={(e) => setF({ ...f, android: e.target.value })} className={input} />
        </label>
        <label className="text-small text-muted">
          App Store link (empty until published)
          <input type="url" placeholder="https://apps.apple.com/…" value={f.ios} onChange={(e) => setF({ ...f, ios: e.target.value })} className={input} />
        </label>
      </fieldset>
      {done && <p role="status" className="mt-3 text-label text-peacock-dark">Saved. The website picks it up within a few minutes.</p>}
      {problem && <p role="alert" className="mt-3 rounded-xl bg-danger-tint p-3 text-small text-danger-ink">{problem}</p>}
    </section>
  );
}
