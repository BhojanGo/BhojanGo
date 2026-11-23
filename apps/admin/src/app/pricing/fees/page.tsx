"use client";
/**
 * R29 fee model v2: Pricing & Rules ▸ Fees. Pick a level (Country → State → City → Restaurant) and see each fee
 * setting's effective value and where it comes from ("Inherited from: United States"), the level's own value with
 * its dates, changes waiting for a second admin, and who changed what (old → new). Setting a value sends it for
 * approval (money rule); clearing it makes the level inherit again. API: /rules/fees (core_api rules/api/v1/fees.py).
 * R30: the payment fee estimate per payment method (card, UPI, wallet, net banking; cash has none) and the delivery
 * fee (base + per mile / km, all of it to the delivery partner) are set the same way.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { apiMessage } from "@/lib/ops";

type Level = "country" | "region" | "city" | "restaurant";
type Rate = { percent: string; fixed?: string };
type Value = Record<string, string | Rate | undefined>;
interface Ref { level: Level; scope_id: string; name: string }
interface OwnRule { rule_id: string; version: number; status: string; value: Value; effective_from: string; effective_to: string | null }
interface FieldRow {
  field: string;
  effective: Value | null;
  source: (Ref & { rule_id: string; version: number }) | null;
  inherited: boolean;
  own: OwnRule | null;
  scheduled: OwnRule[];
  pending: OwnRule[];
}
interface History { at: string; who: string; action: string; field: string; old: Value | null; new: Value | null }
interface FeeLevel { level: Level; scope_id: string; name: string; chain: Ref[]; fields: FieldRow[]; history: History[] }
interface Restaurant { id: string; name: string }

const LEVELS: { key: Level; label: string }[] = [
  { key: "country", label: "Country" }, { key: "region", label: "State" }, { key: "city", label: "City" }, { key: "restaurant", label: "Restaurant" },
];
const FIELDS: Record<string, { label: string; hint: string }> = {
  platform_fee_pct: { label: "Platform fee", hint: "% of the food subtotal, paid by the customer to BhojanGo" },
  min_platform_fee: { label: "Minimum platform fee", hint: "the smallest platform fee charged" },
  restaurant_commission_pct: { label: "Restaurant commission", hint: "% of food, taken from the restaurant's payout" },
  card_fee_estimate: {
    label: "Payment fee estimate",
    hint: "per payment method, % + fixed of the charge less the tip, taken from the restaurant's payout; cash has none. Production uses the gateway's actual fee",
  },
  delivery_fee: { label: "Delivery fee", hint: "base + per distance from the restaurant to the customer; all of it goes to the delivery partner" },
};
const METHODS: { key: string; label: string }[] = [
  { key: "card", label: "Card" }, { key: "upi", label: "UPI" }, { key: "wallet", label: "Wallet" }, { key: "net_banking", label: "Net banking" },
];
const OLD_DELIVERY: Record<string, string> = { flat: "a flat fee", distance_slabs: "distance slabs", free_above: "free above a subtotal", tier_base: "by restaurant tier" };
const ACTION: Record<string, string> = {
  "rule.created": "drafted", "rule.version_created": "drafted", "rule.edited": "edited", "rule.submitted": "sent for approval",
  "rule.approved": "approved", "rule.published": "published", "rule.rejected": "rejected", "rule.ended": "cleared", "rule.rolled_back": "rolled back",
};
// Steps of one change (no new value): show the value they're about, not "7% → 7%".
const STEPS = new Set(["rule.submitted", "rule.approved", "rule.rejected"]);
const LEVEL_WORD: Record<Level, string> = { country: "country", region: "state", city: "city", restaurant: "restaurant" };

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

const rate = (r: Rate, sym: string) => (Number(r.fixed ?? 0) > 0 ? `${r.percent}% + ${sym}${Number(r.fixed).toFixed(2)}` : `${r.percent}%`);

function show(field: string, v: Value | null | undefined, sym: string, unit = "mile"): string {
  if (!v) return "—";
  if (field === "min_platform_fee") return `${sym}${Number(v.amount).toFixed(2)}`;
  if (field === "card_fee_estimate") {
    if (typeof v.percent === "string") return `Card ${rate(v as unknown as Rate, sym)}`; // the R29 single rate
    return METHODS.filter((m) => v[m.key]).map((m) => `${m.label} ${rate(v[m.key] as Rate, sym)}`).join(" · ");
  }
  if (field === "delivery_fee") {
    if (v.template) return `Older shape: ${OLD_DELIVERY[v.template as string] ?? String(v.template)}`;
    return `${sym}${Number(v.base).toFixed(2)} + ${sym}${Number(v.per_unit).toFixed(2)} per ${unit}`;
  }
  return `${String(v.percent)}%`;
}

function Fees() {
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: markets } = useMarkets();
  const me = useAdminMe();
  const level = (params.get("level") as Level) || "country";
  const country = params.get("country") || markets?.[0]?.code || "";
  const countryInfo = markets?.find((c) => c.code === country);
  const regions = countryInfo?.regions ?? [];
  const region = params.get("region") || regions[0]?.code || "";
  const cities = regions.find((r) => r.code === region)?.cities ?? [];
  const city = params.get("city") || cities[0]?.code || "";
  const cityName = cities.find((c) => c.code === city)?.name ?? "";
  const restaurants = useQuery({
    queryKey: ["fees", "kitchens", cityName],
    enabled: level === "restaurant" && !!cityName,
    queryFn: async () => (await adminApi.get<{ items: Restaurant[] }>("/user/restaurants", { params: { city: cityName, limit: 100 } })).data.items,
  });
  const restaurant = params.get("restaurant") || restaurants.data?.[0]?.id || "";
  const scope = level === "country" ? country : level === "region" ? region : level === "city" ? city : restaurant;
  const sym = countryInfo?.currency === "INR" ? "₹" : "$";
  const unit = countryInfo?.code === "US" ? "mile" : "km";

  const data = useQuery({
    queryKey: ["fees", level, scope],
    enabled: !!scope,
    queryFn: async () => (await adminApi.get<FeeLevel>("/user/rules/fees", { params: { level, scope_id: scope } })).data,
  });
  const market = level === "restaurant" ? city : scope;
  const canEdit = can(me.data, "rules.edit", market);
  const canClear = can(me.data, "rules.approve", market);

  const go = (patch: Record<string, string>) => {
    const q = new URLSearchParams({ level, country, region, city, ...(restaurant ? { restaurant } : {}), ...patch });
    router.replace(`/pricing/fees?${q.toString()}`);
  };

  return (
    <ConsoleShell section="Pricing & Rules" country={country} city={city}
      countryHref={(c) => `/pricing/fees?level=country&country=${c}`} cityHref={(c, ci) => `/pricing/fees?level=city&country=${c}&city=${ci}`}>
      <div>
        <div className="text-small text-muted"><Link href="/pricing" className="text-peacock">Pricing &amp; Rules</Link> ▸ Fees</div>
        <h1 className="m-0 mt-2 text-h1">Fees{data.data ? ` · ${data.data.name}` : ""}</h1>
        <p className="mt-1 text-small text-muted">
          Each fee is set by the most specific level: restaurant, then city, then state, then country. A level with no value of its own inherits.
          Changes need a second admin and apply only to orders placed after they start.
        </p>
      </div>

      <nav aria-label="Level" className="flex flex-wrap items-center gap-2 rounded-2xl bg-white p-2" data-testid="fee-levels">
        {LEVELS.map((l) => (
          <button key={l.key} type="button" onClick={() => go({ level: l.key })} aria-current={level === l.key ? "page" : undefined}
            className={`h-9 rounded-xl px-3 text-label ${level === l.key ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>{l.label}</button>
        ))}
        <span className="mx-2 h-6 w-px bg-line" />
        <select aria-label="Country" value={country} onChange={(e) => go({ country: e.target.value, region: "", city: "", restaurant: "" })}
          className="h-9 rounded-xl border border-line px-2 text-label">
          {(markets ?? []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
        </select>
        {level !== "country" ? (
          <select aria-label="State" value={region} onChange={(e) => go({ region: e.target.value, city: "", restaurant: "" })}
            className="h-9 rounded-xl border border-line px-2 text-label">
            {regions.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </select>
        ) : null}
        {level === "city" || level === "restaurant" ? (
          <select aria-label="City" value={city} onChange={(e) => go({ city: e.target.value, restaurant: "" })}
            className="h-9 rounded-xl border border-line px-2 text-label">
            {cities.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        ) : null}
        {level === "restaurant" ? (
          <select aria-label="Restaurant" value={restaurant} onChange={(e) => go({ restaurant: e.target.value })}
            className="h-9 rounded-xl border border-line px-2 text-label">
            {(restaurants.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
        ) : null}
      </nav>

      {data.isError ? <p role="alert" className="text-danger">{apiMessage(data.error)}</p> : null}
      {data.data ? (
        <>
          <div className="text-small text-muted" data-testid="fee-chain">
            {data.data.chain.map((c) => `${LEVEL_WORD[c.level][0].toUpperCase()}${LEVEL_WORD[c.level].slice(1)}: ${c.name}`).join(" → ")}
          </div>
          <table className="w-full rounded-2xl bg-white text-left" data-testid="fee-table">
            <thead>
              <tr className="text-small text-muted">
                <th className="p-3">Fee</th><th className="p-3">Effective value</th><th className="p-3">Comes from</th>
                <th className="p-3">Set for this {LEVEL_WORD[level]}</th><th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {data.data.fields.map((f) => (
                <FeeRow key={f.field} row={f} sym={sym} unit={unit} level={level} scope={data.data!.scope_id} canEdit={canEdit} canClear={canClear}
                  onDone={() => void qc.invalidateQueries({ queryKey: ["fees"] })} />
              ))}
            </tbody>
          </table>

          <section className="rounded-2xl bg-white p-4" data-testid="fee-history">
            <h2 className="m-0 text-h3">Changes at this level</h2>
            {data.data.history.length === 0 ? <p className="text-small text-muted">No change has been made here: every fee is inherited.</p> : (
              <ul className="m-0 mt-2 list-none p-0">
                {data.data.history.map((h, i) => (
                  <li key={i} className="border-t border-line-soft py-2 text-small">
                    <b>{when(h.at)}</b> · {h.who} {ACTION[h.action] ?? h.action} <b>{FIELDS[h.field]?.label ?? h.field}</b>:{" "}
                    {STEPS.has(h.action) ? show(h.field, h.new, sym, unit) : `${h.old ? show(h.field, h.old, sym, unit) : "inherited"} → ${h.action === "rule.ended" ? "inherited" : show(h.field, h.new, sym, unit)}`}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </ConsoleShell>
  );
}

function FeeRow({ row, sym, unit, level, scope, canEdit, canClear, onDone }: {
  row: FieldRow; sym: string; unit: string; level: Level; scope: string; canEdit: boolean; canClear: boolean; onDone: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [rates, setRates] = useState<Record<string, string>>({}); // "upi.percent" -> "0"
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const meta = FIELDS[row.field];
  const src = row.source;
  const value = useMemo((): Value => {
    if (row.field === "min_platform_fee") return { amount: a };
    if (row.field === "delivery_fee") return { base: a, per_unit: b || "0" };
    if (row.field === "card_fee_estimate") {
      const out: Value = { card: { percent: a, fixed: b || "0" } };
      for (const m of METHODS.slice(1)) {
        const pct = rates[`${m.key}.percent`];
        if (pct) out[m.key] = { percent: pct, fixed: rates[`${m.key}.fixed`] || "0" };
      }
      return out;
    }
    return { percent: a };
  }, [row.field, a, b, rates]);
  const input = (label: string, v: string, set: (s: string) => void, aria: string) => (
    <label className="text-small">{label}
      <input aria-label={aria} value={v} onChange={(e) => set(e.target.value)} inputMode="decimal" className="ml-1 h-8 w-20 rounded-lg border border-line px-2" />
    </label>
  );

  async function save() {
    setBusy(true); setProblem(null);
    try {
      await adminApi.post("/user/rules/fees", { level, scope_id: scope, field: row.field, value,
        effective_from: from ? new Date(from).toISOString() : null, effective_to: to ? new Date(to).toISOString() : null });
      setEditing(false); onDone();
    } catch (e) { setProblem(apiMessage(e)); } finally { setBusy(false); }
  }
  async function clear() {
    setBusy(true); setProblem(null);
    try {
      await adminApi.delete("/user/rules/fees", { params: { level, scope_id: scope, field: row.field } });
      onDone();
    } catch (e) { setProblem(apiMessage(e)); } finally { setBusy(false); }
  }

  return (
    <tr className="border-t border-line-soft align-top" data-field={row.field}>
      <td className="p-3"><b>{meta.label}</b><div className="text-small text-muted">{meta.hint}</div></td>
      <td className="p-3 text-label tabular-nums" data-testid="effective">{show(row.field, row.effective, sym, unit)}</td>
      <td className="p-3 text-small" data-testid="source">
        {src ? (row.inherited ? <>Inherited from: <b>{src.name}</b></> : <>Set here</>) : "Not set anywhere"}
        {src ? <div className="text-muted">version {src.version}</div> : null}
      </td>
      <td className="p-3 text-small">
        {row.own ? <>{show(row.field, row.own.value, sym, unit)} · from {day(row.own.effective_from)}{row.own.effective_to ? ` to ${day(row.own.effective_to)}` : ""}</> : <span className="text-muted">—</span>}
        {row.scheduled.map((s) => <div key={s.rule_id} className="text-peacock-dark">Scheduled: {show(row.field, s.value, sym, unit)} from {day(s.effective_from)}</div>)}
        {row.pending.map((p) => <div key={p.rule_id} className="text-kesar-ink">Waiting for approval: {show(row.field, p.value, sym, unit)} from {day(p.effective_from)}</div>)}
        {problem ? <div role="alert" className="text-danger">{problem}</div> : null}
        {editing ? (
          <div className="mt-2 flex flex-wrap items-end gap-2">
            {input(row.field === "min_platform_fee" ? `Amount (${sym})` : row.field === "delivery_fee" ? `Base (${sym})`
              : row.field === "card_fee_estimate" ? "Card %" : "Percent", a, setA, `${meta.label} value`)}
            {row.field === "card_fee_estimate" ? input(`Card fixed (${sym})`, b, setB, "Fixed fee") : null}
            {row.field === "delivery_fee" ? input(`Per ${unit} (${sym})`, b, setB, "Per distance") : null}
            {row.field === "card_fee_estimate" ? METHODS.slice(1).map((m) => (
              <span key={m.key} className="flex gap-1">
                {input(`${m.label} %`, rates[`${m.key}.percent`] ?? "", (v) => setRates((r) => ({ ...r, [`${m.key}.percent`]: v })), `${m.label} percent`)}
                {input(`fixed (${sym})`, rates[`${m.key}.fixed`] ?? "", (v) => setRates((r) => ({ ...r, [`${m.key}.fixed`]: v })), `${m.label} fixed`)}
              </span>
            )) : null}
            {row.field === "card_fee_estimate" ? <span className="text-small text-muted">A method left empty uses the card rate.</span> : null}
            <label className="text-small">From <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} className="h-8 rounded-lg border border-line px-2" /></label>
            <label className="text-small">Until <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} className="h-8 rounded-lg border border-line px-2" /></label>
            <button type="button" disabled={busy || !a} onClick={() => void save()} className="h-8 rounded-lg bg-peacock px-3 text-label text-white disabled:opacity-50">Send for approval</button>
            <button type="button" onClick={() => setEditing(false)} className="h-8 px-2 text-label text-muted">Cancel</button>
          </div>
        ) : null}
      </td>
      <td className="p-3 text-right">
        {canEdit && !editing && row.pending.length === 0 ? (
          <button type="button" onClick={() => setEditing(true)} className="text-label text-peacock">{row.own ? "Change" : "Set here"}</button>
        ) : null}
        {canClear && row.own && !editing ? (
          <button type="button" disabled={busy} onClick={() => void clear()} className="ml-3 text-label text-danger">Clear (inherit)</button>
        ) : null}
      </td>
    </tr>
  );
}

export default function FeesPage() {
  return <Suspense><Fees /></Suspense>;
}
