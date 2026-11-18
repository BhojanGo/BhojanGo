"use client";

/**
 * Price simulator (design board: AdminPricing, right column). The same cart
 * priced with the live rules and with chosen drafts, side by side, including
 * who gets what. Uses POST /api/v1/pricing/simulate.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { apiError, firstCity, moneySymbol, useMarkets } from "@/lib/markets";

type Line = { code: string; label: string; amount: string; funded_by: string | null };
type Split = { restaurant: string; rider: string; tax: string; platform: string; detail?: Record<string, string> };
type Side = { ok: boolean; message: string | null; lines: Line[]; total: string | null; split: Split | null };
type SimOut = { currency: string; live: Side; draft: Side; changes: { label: string; live: string; draft: string }[] };
type Rule = { id: string; family: string; template: string; name: string | null; version: number; status: string; market_scope: string };
type Restaurant = { id: string; name: string; city: string };

const SPLIT_ROWS: [Exclude<keyof Split, "detail">, string][] = [
  ["restaurant", "Kitchen gets"],
  ["rider", "Delivery partner gets"],
  ["tax", "Tax"],
  ["platform", "Platform keeps"],
];

function fmt(sym: string, v: string | number | null | undefined) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  return `${n < 0 ? "−" : ""}${sym}${Math.abs(n).toFixed(2)}`;
}

function Simulator() {
  const params = useSearchParams();
  const router = useRouter();
  const { data: markets } = useMarkets();
  // No ?city=: the first live city in Markets (never a hard-coded one).
  const city = params.get("city") ?? firstCity(markets) ?? "";
  const country = city.split("-")[0] ?? "";
  const cityInfo = markets?.flatMap((c) => c.regions.flatMap((r) => r.cities)).find((c) => c.code === city);
  const currency = markets?.find((c) => c.code === country)?.currency;
  const sym = currency ? moneySymbol(currency) : "";
  const unit = markets?.find((c) => c.code === country)?.distance_unit ?? "km";
  // A sales-tax country prices tax for an address (R15): the simulation asks for a ZIP code there.
  const needsZip = markets?.find((c) => c.code === country)?.tax_regime === "us_sales_tax";

  const [form, setForm] = useState({
    food: "560",
    distance: "4.2",
    when: `${new Date().toLocaleDateString("en-CA")}T20:00`, // today, 8 pm
    tip: "20",
    tier: "B",
    restaurant: "",
    promo: "",
    firstOrder: false,
    zip: "",
  });
  const [drafts, setDrafts] = useState<string[]>([]);

  const { data: restaurants } = useQuery({
    queryKey: ["restaurants", cityInfo?.name],
    enabled: Boolean(cityInfo),
    queryFn: async () =>
      (await adminApi.get<{ items: Restaurant[] }>("/user/restaurants", { params: { city: cityInfo?.name, limit: 100 } })).data.items,
  });
  const { data: draftRules } = useQuery({
    queryKey: ["rules", "drafts", city],
    enabled: Boolean(city),
    queryFn: async () => {
      const [d, p] = await Promise.all(
        ["draft", "pending_approval"].map((status) => adminApi.get<Rule[]>("/user/rules", { params: { status, scope: country } }))
      );
      return [...d.data, ...p.data].filter((r) => city === r.market_scope || city.startsWith(r.market_scope + "-") || r.market_scope.startsWith(city));
    },
  });

  const sim = useMutation({
    mutationFn: async () =>
      (
        await adminApi.post<SimOut>("/user/pricing/simulate", {
          city,
          restaurant_id: form.restaurant || null,
          cart: { food_subtotal: form.food },
          distance: form.distance,
          local_time: `${form.when}:00`,
          tip: form.tip || "0",
          restaurant_tier: form.tier || null,
          first_order: form.firstOrder,
          promo_code: form.promo || null,
          draft_rule_ids: drafts,
          postal_code: needsZip ? form.zip || null : null,
        })
      ).data,
  });

  const rows = useMemo(() => {
    const out = sim.data;
    if (!out) return [];
    const labels = Array.from(new Set([...out.live.lines.map((l) => l.label), ...out.draft.lines.map((l) => l.label)]));
    const amt = (side: Side, label: string) => side.lines.filter((l) => l.label === label).reduce((n, l) => n + Number(l.amount), 0);
    return labels.map((label) => ({ label, live: amt(out.live, label), draft: amt(out.draft, label) }));
  }, [sim.data]);

  const field = "mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 text-small text-kohl";
  const changed = (a: number | string | null | undefined, b: number | string | null | undefined) => Number(a) !== Number(b);

  return (
    <ConsoleShell
      section="Pricing & Rules"
      country={country}
      city={city}
      countryHref={(c) => `/pricing/simulator?city=${firstCity(markets, c) ?? ""}`}
      cityHref={(_, c) => `/pricing/simulator?city=${c}`}
    >
      <div>
        <div className="text-small text-muted">Pricing &amp; Rules ▸ Price simulator</div>
        <h1 className="m-0 mt-2 text-h1">Price simulator · {cityInfo?.name ?? city}</h1>
        <p className="mt-1 text-small text-muted">Price one cart with the live rules and with drafts before anyone approves them.</p>
      </div>

      <div className="flex flex-wrap gap-6">
        <form
          className="flex flex-[1_1_300px] flex-col gap-3 rounded-2xl border border-line bg-white p-6"
          onSubmit={(e) => {
            e.preventDefault();
            sim.mutate();
          }}
        >
          <h2 className="m-0 text-h3">Cart</h2>
          <label className="text-small text-muted">
            Food subtotal ({sym.trim()})
            <input required type="number" min="1" step="0.01" value={form.food} onChange={(e) => setForm({ ...form, food: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Distance ({unit})
            <input required type="number" min="0.1" step="0.1" value={form.distance} onChange={(e) => setForm({ ...form, distance: e.target.value })} className={field} />
          </label>
          {needsZip ? (
            <label className="text-small text-muted">
              Delivery ZIP code (sales tax)
              <input required inputMode="numeric" value={form.zip} onChange={(e) => setForm({ ...form, zip: e.target.value })} className={field} />
            </label>
          ) : null}
          <label className="text-small text-muted">
            Day and time ({cityInfo?.name ?? "city"} time)
            <input required type="datetime-local" value={form.when} onChange={(e) => setForm({ ...form, when: e.target.value })} className={field} />
          </label>
          <div className="flex gap-3">
            <label className="flex-1 text-small text-muted">
              Tip ({sym.trim()})
              <input type="number" min="0" step="1" value={form.tip} onChange={(e) => setForm({ ...form, tip: e.target.value })} className={field} />
            </label>
            <label className="flex-1 text-small text-muted">
              Kitchen tier
              <select value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })} className={field}>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
              </select>
            </label>
          </div>
          <label className="text-small text-muted">
            Kitchen (adds its own rules, e.g. packaging)
            <select value={form.restaurant} onChange={(e) => setForm({ ...form, restaurant: e.target.value })} className={field}>
              <option value="">Any kitchen</option>
              {restaurants?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <div className="flex gap-3">
            <label className="flex-1 text-small text-muted">
              Promo code
              <input value={form.promo} onChange={(e) => setForm({ ...form, promo: e.target.value.toUpperCase() })} className={field} />
            </label>
            <label className="mt-6 flex items-center gap-2 text-small text-kohl">
              <input type="checkbox" checked={form.firstOrder} onChange={(e) => setForm({ ...form, firstOrder: e.target.checked })} />
              First order
            </label>
          </div>

          <fieldset className="mt-2 rounded-xl border border-line-soft p-3">
            <legend className="px-1 text-label text-muted">Drafts to try</legend>
            {!draftRules?.length && <p className="m-0 text-small text-muted">No drafts here. Compare against live rules only.</p>}
            {draftRules?.map((r) => (
              <label key={r.id} className="flex items-center gap-2 py-1 text-small">
                <input
                  type="checkbox"
                  checked={drafts.includes(r.id)}
                  onChange={(e) => setDrafts(e.target.checked ? [...drafts, r.id] : drafts.filter((d) => d !== r.id))}
                />
                <span className="flex-grow">
                  {r.name ?? `${r.family} · ${r.template}`} <span className="text-muted">v{r.version} · {r.status.replace("_", " ")}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <button type="submit" disabled={sim.isPending} className="mt-2 h-11 rounded-full bg-peacock font-bold text-white disabled:opacity-60">
            {sim.isPending ? "Pricing…" : "Price this cart"}
          </button>
          {sim.error ? <p role="alert" className="m-0 rounded-xl bg-danger-tint p-3 text-small text-danger-ink">{apiError(sim.error)}</p> : null}
        </form>

        <section aria-label="Live and draft prices" className="flex-[2_1_480px] rounded-2xl border border-line bg-white p-6">
          <div className="flex flex-wrap items-center gap-2 text-small text-muted">
            <span className="rounded-full bg-porcelain px-3 py-1 tabular-nums">Cart {fmt(sym, form.food)}</span>
            <span className="rounded-full bg-porcelain px-3 py-1">{form.distance} {unit}</span>
            <span className="rounded-full bg-porcelain px-3 py-1">
              {new Date(form.when).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}
            </span>
            <span className="rounded-full bg-porcelain px-3 py-1">Tier {form.tier}</span>
          </div>
          {!sim.data && <p className="mt-6 text-small text-muted">Set up a cart and press “Price this cart”.</p>}
          {sim.data && (
            <div className="mt-4 overflow-x-auto">
              {(!sim.data.live.ok || !sim.data.draft.ok) && (
                <p role="alert" className="rounded-xl bg-kesar-tint p-3 text-small text-kesar-ink">
                  {!sim.data.live.ok ? `Live: ${sim.data.live.message}. ` : ""}
                  {!sim.data.draft.ok ? `Draft: ${sim.data.draft.message}.` : ""}
                </p>
              )}
              <div className="table-scroll"><table className="w-full min-w-[420px] border-collapse text-small tabular-nums">
                <thead>
                  <tr className="text-left text-caption text-muted">
                    <th className="py-2 font-bold">Line</th>
                    <th className="text-right font-bold">Live</th>
                    <th className="text-right font-bold">{drafts.length ? "Draft" : "Live (no drafts)"}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.label} className={`border-t border-line-soft ${changed(r.live, r.draft) ? "bg-kesar-tint/60 font-bold" : ""}`}>
                      <td className="py-2">{r.label}</td>
                      <td className="text-right">{fmt(sym, r.live)}</td>
                      <td className="text-right">{fmt(sym, r.draft)}</td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-kohl text-label">
                    <td className="py-3">Customer pays</td>
                    <td className="text-right">{fmt(sym, sim.data.live.total)}</td>
                    <td className="text-right">{fmt(sym, sim.data.draft.total)}</td>
                  </tr>
                  <tr data-testid="sim-commission" className="border-t border-line-soft">
                    <td className="py-2">Commission (from the kitchen)</td>
                    <td className="text-right">{fmt(sym, sim.data.live.split?.detail?.commission)}</td>
                    <td className="text-right">{fmt(sym, sim.data.draft.split?.detail?.commission)}</td>
                  </tr>
                  {SPLIT_ROWS.map(([key, label]) => {
                    const a = sim.data!.live.split?.[key];
                    const b = sim.data!.draft.split?.[key];
                    return (
                      <tr key={key} className={`border-t border-line-soft ${changed(a, b) ? "bg-kesar-tint/60 font-bold" : ""}`}>
                        <td className="py-2">{label}</td>
                        <td className="text-right">{fmt(sym, a)}</td>
                        <td className="text-right">{fmt(sym, b)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table></div>
              <p className="mt-3 text-small text-muted">
                {sim.data.changes.length ? `${sim.data.changes.length} amounts change with the drafts.` : "No change."}{" "}
                <button type="button" className="font-bold text-peacock" onClick={() => router.refresh()}>
                  Try another cart
                </button>
              </p>
            </div>
          )}
        </section>
      </div>
    </ConsoleShell>
  );
}

export default function SimulatorPage() {
  return (
    <Suspense fallback={null}>
      <Simulator />
    </Suspense>
  );
}
