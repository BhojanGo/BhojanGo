"use client";
// Finance: weekly payout runs for a country (prepare → a second finance admin
// approves and pays → retry what's waiting), each statement, and the week's
// reconciliation (money in vs owed). Each country in its own currency.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { apiMessage, money, useScope } from "@/lib/ops";

interface Run {
  id: string; country: string; currency: string; period_start: string; period_end: string; status: string; created_by: string;
  approved_by: string | null; paid_at: string | null;
  totals: { orders?: number; restaurants?: string; riders?: string; restaurant_statements?: number; rider_statements?: number };
}
interface Statement { id: string; payee_type: string; payee_name: string; amount: number; currency: string; status: string; error: string | null; summary: Record<string, unknown> }
interface Recon {
  currency: string; orders: { total: number; delivered: number; cancelled: number; open: number };
  money: Record<string, number>; issues: { order_id: string; issue: string }[]; refunds_not_settled: number;
}

interface Contribution {
  currency: string; fees_estimated: number;
  cities: { city: string; orders: number; totals: Record<string, string>; per_order: Record<string, string | null> }[];
  all: { orders: number; totals: Record<string, string>; per_order: Record<string, string | null> };
}

const CONTRIBUTION_ROWS: [string, string, number][] = [
  ["commission", "Commission", 1], ["customer_fees", "Customer fees", 1], ["platform_promos", "Offers we fund", -1],
  ["rider_pay", "Rider pay (tips excluded)", -1], ["payment_fees", "Payment fees", -1], ["refunds", "Refunds we pay", -1],
];

const RUN_STATUS: Record<string, string> = { draft: "Waiting for approval", approved: "Approved", paid: "Paid", partially_paid: "Partly paid" };

function lastWeek(): [string, string] {
  const d = new Date();
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((d.getDay() + 6) % 7) - 7);
  const next = new Date(monday);
  next.setDate(monday.getDate() + 7);
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  return [iso(monday), iso(next)];
}

function FinancePage() {
  const scope = useScope();
  const { country, region, city } = parseScope(scope);
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();
  const qc = useQueryClient();
  const target = country === "ALL" ? markets?.[0]?.code ?? "IN" : country;
  const runs = useQuery({ queryKey: ["payout-runs", target], queryFn: async () => (await adminApi.get<Run[]>("/user/finance/payout-runs", { params: { country: target } })).data });
  const [open, setOpen] = useState<string | null>(null);
  const run = useQuery({
    queryKey: ["payout-run", open], enabled: Boolean(open),
    queryFn: async () => (await adminApi.get<Run & { statements: Statement[] }>(`/user/finance/payout-runs/${open}`)).data,
  });
  const [[start, end], setPeriod] = useState(lastWeek);
  const recon = useQuery({
    queryKey: ["recon", target, start, end],
    queryFn: async () => (await adminApi.get<Recon>("/user/finance/reconciliation", { params: { country: target, start, end } })).data,
    enabled: can(me, "finance.view", target),
  });
  const contribution = useQuery({
    queryKey: ["contribution", scope, target, start, end],
    queryFn: async () => (await adminApi.get<Contribution>("/user/finance/contribution", { params: { scope: city ?? region ?? target, start, end } })).data,
    enabled: can(me, "finance.view", city ?? region ?? target),
  });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string) {
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      await qc.invalidateQueries({ queryKey: ["payout-runs"] });
      await qc.invalidateQueries({ queryKey: ["payout-run"] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    }
  }
  return (
    <ConsoleShell section="Finance" country={country} region={region} city={city} scopeHref={(s) => `/finance?scope=${s.split("-")[0]}`}>
      <div>
        <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">Finance · {markets?.find((c) => c.code === target)?.name ?? target}</h1>
        <p className="mt-1 text-sm text-muted">Payouts run weekly per country (Monday to Monday, local time). The admin who prepares a run can&apos;t approve it.</p>
      </div>
      <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Payout runs">
        <div className="flex flex-wrap items-end gap-3">
          <h2 className="m-0 flex-1 text-lg font-extrabold">Payout runs</h2>
          <label className="text-sm font-bold">From <input type="date" value={start} onChange={(e) => setPeriod([e.target.value, end])} className="ml-1 h-9 rounded-lg border border-line px-2" /></label>
          <label className="text-sm font-bold">to <input type="date" value={end} onChange={(e) => setPeriod([start, e.target.value])} className="ml-1 h-9 rounded-lg border border-line px-2" /></label>
          {can(me, "finance.edit", target) ? (
            <button type="button" onClick={() => void act(() => adminApi.post("/user/finance/payout-runs", { country: target, period_start: start, period_end: end }), "Run prepared: a second finance admin approves it.")}
              className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">Prepare payouts for this week</button>
          ) : null}
        </div>
        {msg ? <p role="status" className={`text-sm font-semibold ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
        <table className="w-full text-left text-sm tabular-nums">
          <thead className="text-[12px] uppercase tracking-wide text-muted"><tr><th className="py-2">Week</th><th>Status</th><th>Orders</th><th>Kitchens</th><th>Riders</th><th /></tr></thead>
          <tbody className="divide-y divide-line">
            {(runs.data ?? []).map((r) => (
              <tr key={r.id} className={open === r.id ? "bg-peacock-wash" : ""}>
                <td className="py-3 font-bold">{r.period_start} → {r.period_end}</td><td>{RUN_STATUS[r.status] ?? r.status}</td><td>{r.totals.orders ?? 0}</td>
                <td>{money(r.totals.restaurants, r.currency, 2)} · {r.totals.restaurant_statements ?? 0}</td><td>{money(r.totals.riders, r.currency, 2)} · {r.totals.rider_statements ?? 0}</td>
                <td className="space-x-2 text-right">
                  <button type="button" onClick={() => setOpen(r.id)} className="h-8 rounded-full border border-line-strong px-3 text-xs font-bold">Statements</button>
                  {r.status === "draft" && can(me, "payouts.approve", r.country) && r.created_by !== me?.user_id ? (
                    <button type="button" onClick={() => void act(() => adminApi.post(`/user/finance/payout-runs/${r.id}/approve`), "Approved and paid.")} className="h-8 rounded-full bg-peacock px-3 text-xs font-extrabold text-white">Approve and pay</button>
                  ) : null}
                  {r.status === "partially_paid" && can(me, "payouts.approve", r.country) ? (
                    <button type="button" onClick={() => void act(() => adminApi.post(`/user/finance/payout-runs/${r.id}/retry`), "Retried.")} className="h-8 rounded-full border border-line-strong px-3 text-xs font-bold">Retry unpaid</button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.data && runs.data.length === 0 ? <p className="text-sm text-muted">No payout runs yet.</p> : null}
      </section>
      {open && run.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Statements">
          <h2 className="m-0 mb-3 text-lg font-extrabold">Statements · {run.data.period_start} → {run.data.period_end}</h2>
          <table className="w-full text-left text-sm tabular-nums">
            <thead className="text-[12px] uppercase tracking-wide text-muted"><tr><th className="py-2">Payee</th><th>Type</th><th>Amount</th><th>Status</th></tr></thead>
            <tbody className="divide-y divide-line">
              {run.data.statements.map((s) => (
                <tr key={s.id}><td className="py-2.5 font-semibold">{s.payee_name}</td><td>{s.payee_type === "restaurant" ? "Kitchen" : "Rider"}</td>
                  <td>{money(s.amount / 100, s.currency, 2)}</td><td>{s.status}{s.error ? <span className="text-muted"> · {s.error}</span> : null}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
      {contribution.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Contribution per order">
          <h2 className="m-0 mb-1 text-lg font-extrabold">Contribution per order · {start} → {end}</h2>
          <p className="mb-3 text-sm text-muted">What the platform keeps of an average delivered order, after payment fees, rider pay (tips are the rider&apos;s), the offers we fund and the refunds we pay.
            {contribution.data.fees_estimated ? ` ${contribution.data.fees_estimated} older orders had no payment fee recorded; it's worked out from today's rule.` : ""}</p>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm">
            <thead className="text-[12px] uppercase tracking-wide text-muted"><tr><th className="py-2">Per order</th>
              {contribution.data.cities.map((c) => <th key={c.city} className="text-right">{c.city} · {c.orders} orders</th>)}</tr></thead>
            <tbody className="divide-y divide-line tabular-nums">
              {CONTRIBUTION_ROWS.map(([k, label, sign]) => (
                <tr key={k}><td className="py-2">{label}</td>{contribution.data!.cities.map((c) => <td key={c.city} className="text-right">{sign < 0 ? "−" : ""}{money(Number(c.per_order[k] ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
              ))}
              <tr className="font-extrabold" data-testid="platform-keeps"><td className="py-2">Platform keeps</td>{contribution.data.cities.map((c) => <td key={c.city} className="text-right">{money(Number(c.per_order.keeps ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
            </tbody>
          </table></div>
          {contribution.data.cities.length === 0 ? <p className="text-sm text-muted">No delivered orders in this period.</p> : null}
        </section>
      ) : null}
      {recon.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Reconciliation">
          <h2 className="m-0 mb-3 text-lg font-extrabold">Reconciliation · {start} → {end}</h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {[["Captured", recon.data.money.captured], ["Refunded", recon.data.money.refunded], ["Kitchens are owed", recon.data.money.restaurant_payable], ["Riders are owed", recon.data.money.rider_payable],
              ["Tax owed", recon.data.money.tax_owed], ["Platform revenue", recon.data.money.platform_revenue], ["Payment fees", recon.data.money.payment_fees],
              ["Platform after payment fees", recon.data.money.platform_after_payment_fees], ["Delivered GMV", recon.data.money.delivered_gmv], ["Net collected", recon.data.money.net_collected]]
              .map(([l, v]) => <div key={l as string} className="rounded-xl bg-porcelain p-3"><div className="text-[12px] font-semibold text-muted">{l}</div><div className="text-lg font-extrabold tabular-nums">{money(Number(v ?? 0) / 100, recon.data!.currency, 2)}</div></div>)}
          </div>
          <p className="mt-3 text-sm">{recon.data.orders.delivered} delivered · {recon.data.orders.cancelled} cancelled · {recon.data.orders.open} still open · {recon.data.refunds_not_settled} refunds not settled ·{" "}
            {recon.data.issues.length ? <b className="text-chili">{recon.data.issues.length} issues to look at</b> : <span className="text-peacock">everything lines up</span>}</p>
        </section>
      ) : null}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><FinancePage /></Suspense>;
}
