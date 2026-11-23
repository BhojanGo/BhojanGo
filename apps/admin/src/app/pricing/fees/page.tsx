"use client";
/**
 * R29 fee model v2: Pricing & Rules ▸ Fees. Pick a level (Country → State → City → Restaurant) and see each fee
 * setting's effective value and where it comes from ("Inherited from: United States"), the level's own value with
 * its dates, changes waiting for a second admin, and who changed what (old → new). Setting a value sends it for
 * approval (money rule); clearing it makes the level inherit again. API: /rules/fees (core_api rules/api/v1/fees.py).
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
type Value = Record<string, string>;
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
interface Kitchen { id: string; name: string }

const LEVELS: { key: Level; label: string }[] = [
  { key: "country", label: "Country" }, { key: "region", label: "State" }, { key: "city", label: "City" }, { key: "restaurant", label: "Restaurant" },
];
const FIELDS: Record<string, { label: string; hint: string }> = {
  platform_fee_pct: { label: "Platform fee", hint: "% of the food subtotal, paid by the customer to BhojanGo" },
  min_platform_fee: { label: "Minimum platform fee", hint: "the smallest platform fee charged" },
  restaurant_commission_pct: { label: "Restaurant commission", hint: "% of food, taken from the kitchen's payout" },
  card_fee_estimate: { label: "Card fee estimate", hint: "% + fixed of the charge less the tip, taken from the kitchen's payout" },
};
const ACTION: Record<string, string> = {
  "rule.created": "drafted", "rule.version_created": "drafted", "rule.edited": "edited", "rule.submitted": "sent for approval",
  "rule.approved": "approved", "rule.published": "published", "rule.rejected": "rejected", "rule.ended": "cleared", "rule.rolled_back": "rolled back",
};
// Steps of one change (no new value): show the value they're about, not "7% → 7%".
const STEPS = new Set(["rule.submitted", "rule.approved", "rule.rejected"]);
const LEVEL_WORD: Record<Level, string> = { country: "country", region: "state", city: "city", restaurant: "restaurant" };

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

function show(field: string, v: Value | null | undefined, sym: string): string {
  if (!v) return "—";
  if (field === "min_platform_fee") return `${sym}${Number(v.amount).toFixed(2)}`;
  if (field === "card_fee_estimate") return `${v.percent}% + ${sym}${Number(v.fixed ?? 0).toFixed(2)}`;
  return `${v.percent}%`;
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
  const kitchens = useQuery({
    queryKey: ["fees", "kitchens", cityName],
    enabled: level === "restaurant" && !!cityName,
    queryFn: async () => (await adminApi.get<{ items: Kitchen[] }>("/user/restaurants", { params: { city: cityName, limit: 100 } })).data.items,
  });
  const kitchen = params.get("restaurant") || kitchens.data?.[0]?.id || "";
  const scope = level === "country" ? country : level === "region" ? region : level === "city" ? city : kitchen;
  const sym = countryInfo?.currency === "INR" ? "₹" : "$";

  const data = useQuery({
    queryKey: ["fees", level, scope],
    enabled: !!scope,
    queryFn: async () => (await adminApi.get<FeeLevel>("/user/rules/fees", { params: { level, scope_id: scope } })).data,
  });
  const market = level === "restaurant" ? city : scope;
  const canEdit = can(me.data, "rules.edit", market);
  const canClear = can(me.data, "rules.approve", market);

  const go = (patch: Record<string, string>) => {
    const q = new URLSearchParams({ level, country, region, city, ...(kitchen ? { restaurant: kitchen } : {}), ...patch });
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
          <select aria-label="Restaurant" value={kitchen} onChange={(e) => go({ restaurant: e.target.value })}
            className="h-9 rounded-xl border border-line px-2 text-label">
            {(kitchens.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
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
                <FeeRow key={f.field} row={f} sym={sym} level={level} scope={data.data!.scope_id} canEdit={canEdit} canClear={canClear}
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
                    {STEPS.has(h.action) ? show(h.field, h.new, sym) : `${h.old ? show(h.field, h.old, sym) : "inherited"} → ${h.action === "rule.ended" ? "inherited" : show(h.field, h.new, sym)}`}
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

function FeeRow({ row, sym, level, scope, canEdit, canClear, onDone }: {
  row: FieldRow; sym: string; level: Level; scope: string; canEdit: boolean; canClear: boolean; onDone: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const meta = FIELDS[row.field];
  const src = row.source;
  const value = useMemo((): Value => {
    if (row.field === "min_platform_fee") return { amount: a };
    if (row.field === "card_fee_estimate") return { percent: a, fixed: b || "0" };
    return { percent: a };
  }, [row.field, a, b]);

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
      <td className="p-3 text-label tabular-nums" data-testid="effective">{show(row.field, row.effective, sym)}</td>
      <td className="p-3 text-small" data-testid="source">
        {src ? (row.inherited ? <>Inherited from: <b>{src.name}</b></> : <>Set here</>) : "Not set anywhere"}
        {src ? <div className="text-muted">version {src.version}</div> : null}
      </td>
      <td className="p-3 text-small">
        {row.own ? <>{show(row.field, row.own.value, sym)} · from {day(row.own.effective_from)}{row.own.effective_to ? ` to ${day(row.own.effective_to)}` : ""}</> : <span className="text-muted">—</span>}
        {row.scheduled.map((s) => <div key={s.rule_id} className="text-peacock-dark">Scheduled: {show(row.field, s.value, sym)} from {day(s.effective_from)}</div>)}
        {row.pending.map((p) => <div key={p.rule_id} className="text-kesar-ink">Waiting for approval: {show(row.field, p.value, sym)} from {day(p.effective_from)}</div>)}
        {problem ? <div role="alert" className="text-danger">{problem}</div> : null}
        {editing ? (
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <label className="text-small">{row.field === "min_platform_fee" ? `Amount (${sym})` : "Percent"}
              <input aria-label={`${meta.label} value`} value={a} onChange={(e) => setA(e.target.value)} inputMode="decimal" className="ml-1 h-8 w-20 rounded-lg border border-line px-2" />
            </label>
            {row.field === "card_fee_estimate" ? (
              <label className="text-small">Fixed ({sym})
                <input aria-label="Fixed fee" value={b} onChange={(e) => setB(e.target.value)} inputMode="decimal" className="ml-1 h-8 w-20 rounded-lg border border-line px-2" />
              </label>
            ) : null}
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
