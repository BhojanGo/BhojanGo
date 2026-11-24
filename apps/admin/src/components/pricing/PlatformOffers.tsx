"use client";

/**
 * R37: offers BhojanGo pays for (rules/api/v1/offers.py, pricing/service/offer_budget.py).
 *  - OfferBudgets: each place's monthly budget for them, what it has spent this month, and the
 *    pool it spends from (a city without its own budget shares its state's, then its country's).
 *    No budget anywhere is 0: those offers are off. Setting one needs rules.approve.
 *  - OfferEconomics: for one offer, the most it can cost an order next to the platform fee BhojanGo
 *    earns on that order, a warning when it can cost more, and whether its budget lets it run now.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { adminApi } from "@/lib/api";
import { can, useAdminMe } from "@/lib/markets";
import { apiMessage } from "@/lib/ops";
import type { Units } from "@/lib/ruleWords";

interface BudgetRow {
  level: "country" | "region" | "city";
  code: string;
  name: string;
  own: string | null;
  pool: string;
  pool_name: string;
  monthly: string;
  spent: string;
  orders: number;
  percent: number;
  left: string;
}

interface Budgets {
  country: string;
  currency: string;
  month: string;
  rows: BudgetRow[];
}

export interface Economics {
  template: string;
  funded_by: string;
  currency: string;
  order_food: string;
  cost_per_order: string | null;
  platform_fee: string;
  max_cost: string | null;
  warning: boolean;
  pool: string | null;
  pool_name: string | null;
  monthly: string | null;
  spent: string | null;
  left: string | null;
  running: boolean;
}

const LEVEL = { country: "Country", region: "State", city: "City" } as const;

function monthName(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
}

function Meter({ percent, label }: { percent: number; label: string }) {
  const p = Math.min(percent, 100);
  const tone = percent >= 100 ? "bg-chili" : percent >= 80 ? "bg-kesar" : "bg-peacock";
  return (
    <div role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={p} className="h-2 w-28 overflow-hidden rounded-full bg-line-soft">
      <div className={`h-full ${tone}`} style={{ width: `${p}%` }} />
    </div>
  );
}

function BudgetEditor({ row, units, mayEdit, onSaved }: { row: BudgetRow; units: Units; mayEdit: boolean; onSaved: () => Promise<void> }) {
  const [value, setValue] = useState(row.own ?? "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const changed = value.trim() !== (row.own ?? "");
  async function save() {
    const v = value.trim();
    if (v !== "" && !(Number(v) >= 0)) {
      setMsg({ ok: false, text: "An amount of 0 or more, or empty to share the level above's" });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await adminApi.put(`/user/rules/offers/budgets/${row.level}/${row.code}`, { monthly: v === "" ? null : v });
      await onSaved();
      setMsg({ ok: true, text: "Saved" });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  if (!mayEdit) return <span>{row.own != null ? units.money(Number(row.own), 2) : "Shares the level above's"}</span>;
  return (
    <span className="flex flex-wrap items-center gap-2">
      <input aria-label={`Monthly budget for ${row.name}`} inputMode="decimal" value={value} placeholder="Shares the level above's"
        onChange={(e) => setValue(e.target.value)} className="h-9 w-40 rounded-lg border border-line px-2 text-small" />
      <button type="button" disabled={busy || !changed} onClick={() => void save()}
        className="h-9 rounded-full bg-peacock px-3 text-caption font-bold text-white disabled:opacity-40">Save</button>
      {msg ? <span role="status" className={`text-caption ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</span> : null}
    </span>
  );
}

export function OfferBudgets({ country, scope, units }: { country: string; scope: string; units: Units }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["offer-budgets", country],
    queryFn: async () => (await adminApi.get<Budgets>("/user/rules/offers/budgets", { params: { country } })).data,
  });
  if (q.isLoading) return <section aria-busy="true" className="h-24 animate-pulse rounded-2xl bg-white" />;
  if (q.isError || !q.data) {
    return <section className="rounded-2xl bg-white p-4 text-small" role="alert">The offer budgets didn&apos;t load. <button type="button" onClick={() => void q.refetch()} className="font-bold text-peacock">Try again</button></section>;
  }
  const rows = q.data.rows.filter((r) => scope === "*" || r.code.startsWith(scope) || scope.startsWith(r.code));
  const reload = async () => {
    await qc.invalidateQueries({ queryKey: ["offer-budgets"] });
    await qc.invalidateQueries({ queryKey: ["offer-economics"] });
  };
  return (
    <section aria-label="BhojanGo offer budgets" className="space-y-3 rounded-2xl bg-white p-6">
      <div>
        <h2 className="m-0 text-h3">BhojanGo offer budgets · {monthName(q.data.month)}</h2>
        <p className="mt-1 text-small text-muted">
          Offers BhojanGo pays for run only while their place&apos;s monthly budget can pay for them; they stop by themselves when
          it&apos;s spent. Operations get an alert at 80% and at 100%. A city without its own budget shares its state&apos;s, then its
          country&apos;s; with none anywhere they don&apos;t run. Restaurants&apos; own offers aren&apos;t affected.
        </p>
      </div>
      <div className="table-scroll">
        <table className="w-full text-left text-small">
          <thead className="text-caption text-muted"><tr><th className="py-1">Place</th><th>Monthly budget</th><th>Spends from</th><th>Spent this month</th><th>Orders</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.code} data-testid={`budget-${r.code}`} className="border-t border-line-soft align-middle">
                <td className="py-2 pr-2"><b>{r.name}</b> <span className="text-caption text-muted">{LEVEL[r.level]}</span></td>
                <td className="pr-2"><BudgetEditor key={`${r.code}-${r.own}`} row={r} units={units} mayEdit={can(me, "rules.approve", r.code)} onSaved={reload} /></td>
                <td className="pr-2">{r.pool_name}{Number(r.monthly) === 0 ? <span className="ml-1 rounded-full bg-line-soft px-2 py-0.5 text-caption">Off: no budget</span> : null}</td>
                <td className="pr-2">
                  <span className="flex items-center gap-2" data-testid="budget-spent">
                    <Meter percent={r.percent} label={`${r.name}: ${r.percent}% of the month's budget spent`} />
                    {units.money(Number(r.spent), 2)} of {units.money(Number(r.monthly), 2)} · {r.percent}%
                  </span>
                </td>
                <td>{r.orders}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function OfferEconomics({ ruleId, units, paused }: { ruleId: string; units: Units; paused: boolean }) {
  const q = useQuery({
    queryKey: ["offer-economics", ruleId],
    queryFn: async () => (await adminApi.get<Economics>(`/user/rules/offers/${ruleId}/economics`)).data,
  });
  if (!q.data) return <p className="text-small text-muted">Working out what this offer costs…</p>;
  const e = q.data;
  const m = (v: string | null) => (v == null ? "—" : units.money(Number(v), 2));
  const platform = e.funded_by === "platform";
  return (
    <section aria-label="What this offer costs" className="space-y-2 rounded-xl border border-line p-4 text-small">
      <h3 className="m-0 text-label">What it costs {platform ? "BhojanGo" : "the restaurant"} per order</h3>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="text-muted">Cost per order</dt>
        <dd data-testid="offer-cost">{e.max_cost != null ? `up to ${m(e.max_cost)}` : "no ceiling"} · {m(e.cost_per_order)} on a {m(e.order_food)} order</dd>
        <dt className="text-muted">Platform fee earned</dt>
        <dd data-testid="offer-fee">{m(e.platform_fee)} on that order</dd>
        {platform ? (
          <>
            <dt className="text-muted">Budget</dt>
            <dd data-testid="offer-budget">{e.pool_name}: {m(e.spent)} of {m(e.monthly)} spent this month · {m(e.left)} left</dd>
          </>
        ) : null}
      </dl>
      {e.warning ? (
        <p role="alert" data-testid="offer-cost-warning" className="rounded-lg bg-kesar-tint px-3 py-2 text-kesar-ink">
          <b>This offer can cost more than the platform fee it earns:</b> {m(e.cost_per_order)} off a {m(e.order_food)} order that earns {m(e.platform_fee)}.
          {platform ? " BhojanGo loses money on those orders." : ""}
        </p>
      ) : null}
      {platform ? (
        <p data-testid="offer-running" className={e.running ? "text-peacock-dark" : "text-chili"}>
          {paused ? "Paused: customers don't see it." : e.running ? "Running: the budget can pay for it."
            : Number(e.monthly ?? 0) === 0 ? "Not running: no offer budget here. Set one in BhojanGo offer budgets."
            : "Not running: this month's budget is used up."}
        </p>
      ) : null}
    </section>
  );
}
