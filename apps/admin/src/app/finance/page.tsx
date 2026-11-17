"use client";
// Finance: weekly payout runs for a country (prepare → a second finance admin
// approves and pays → retry what's waiting), each statement, and the week's
// reconciliation (money in vs owed). Each country in its own currency.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { type PayeeKind, SetupLinkButton, SetupPill, type SetupState } from "@/components/finance/PayoutSetup";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { apiMessage, money, useScope } from "@/lib/ops";

interface Run {
  id: string; country: string; currency: string; period_start: string; period_end: string; status: string; created_by: string;
  approved_by: string | null; paid_at: string | null;
  totals: { orders?: number; restaurants?: string; riders?: string; restaurant_statements?: number; rider_statements?: number };
}
interface Statement {
  id: string; payee_type: PayeeKind; payee_id: string; payee_name: string; amount: number; currency: string; status: string; error: string | null;
  summary: Record<string, unknown>; transfer_id: string | null; transferred_at: string | null; attempts: number; payout_setup: SetupState;
}
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
  ["rider_pay", "Delivery partner pay (tips excluded)", -1], ["payment_fees", "Payment fees", -1], ["refunds", "Refunds we pay", -1],
];

const RUN_STATUS: Record<string, string> = { draft: "Waiting for approval", approved: "Approved", paid: "Paid", partially_paid: "Partly paid" };
const STATEMENT_STATUS: Record<string, string> = {
  pending: "Not paid yet", paid: "Paid", failed: "Transfer failed", no_account: "No payout account", onboarding: "Waiting for onboarding", reversed: "Reversed",
};
const STATUS_STYLE: Record<string, string> = { paid: "text-peacock", failed: "text-chili", reversed: "text-chili", onboarding: "text-kesar-ink", no_account: "text-kesar-ink" };

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
  // Payouts are per country: the all-countries view shows the first country you may see, and says so.
  // A finance admin may not read Markets (403): then the first country their own finance scope names (R11:
  // the US finance admin saw an empty table and no error).
  const ownCountry = (me?.permissions["finance.view"] ?? []).map((s) => s.split("-")[0]).find((c) => /^[A-Z]{2}$/.test(c)) ?? "";
  const target = country === "ALL" ? markets?.[0]?.code ?? ownCountry : country;
  const runs = useQuery({ queryKey: ["payout-runs", target], enabled: Boolean(target), queryFn: async () => (await adminApi.get<Run[]>("/user/finance/payout-runs", { params: { country: target } })).data });
  const [open, setOpen] = useState<string | null>(null);
  const run = useQuery({
    queryKey: ["payout-run", open], enabled: Boolean(open),
    queryFn: async () => (await adminApi.get<Run & { statements: Statement[] }>(`/user/finance/payout-runs/${open}`)).data,
  });
  const [[start, end], setPeriod] = useState(lastWeek);
  const recon = useQuery({
    queryKey: ["recon", target, start, end],
    queryFn: async () => (await adminApi.get<Recon>("/user/finance/reconciliation", { params: { country: target, start, end } })).data,
    enabled: Boolean(target) && can(me, "finance.view", target),
  });
  const contribution = useQuery({
    queryKey: ["contribution", scope, target, start, end],
    queryFn: async () => (await adminApi.get<Contribution>("/user/finance/contribution", { params: { scope: city ?? region ?? target, start, end } })).data,
    enabled: Boolean(target) && can(me, "finance.view", city ?? region ?? target),
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
        <h1 className="m-0 text-h1">Finance{target ? ` · ${markets?.find((c) => c.code === target)?.name ?? target}` : ""}</h1>
        <p className="mt-1 text-small text-muted">Payouts run weekly per country (Monday to Monday, local time). The admin who prepares a run can&apos;t approve it.</p>
        {country === "ALL" && (markets?.length ?? 0) > 1 ? (
          <p className="mt-2 rounded-xl bg-kesar-tint px-3 py-2 text-small text-kesar-ink">Money stays in each country&apos;s currency, so Finance shows one country at a time. Pick a country above to see another.</p>
        ) : null}
      </div>
      <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Payout runs">
        <div className="flex flex-wrap items-end gap-3">
          <h2 className="m-0 flex-1 text-h3">Payout runs</h2>
          <label className="text-label">From <input type="date" value={start} onChange={(e) => setPeriod([e.target.value, end])} className="ml-1 h-9 rounded-lg border border-line px-2" /></label>
          <label className="text-label">to <input type="date" value={end} onChange={(e) => setPeriod([start, e.target.value])} className="ml-1 h-9 rounded-lg border border-line px-2" /></label>
          {can(me, "finance.edit", target) ? (
            <button type="button" onClick={() => void act(() => adminApi.post("/user/finance/payout-runs", { country: target, period_start: start, period_end: end }), "Run prepared: a second finance admin approves it.")}
              className="h-10 rounded-full bg-peacock px-4 font-bold text-white">Prepare payouts for this week</button>
          ) : null}
        </div>
        {msg ? <p role="status" className={`text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
        <div className="table-scroll"><table className="table-stack w-full text-left text-small tabular-nums [&_td]:pr-3 [&_th]:pr-3">
          <thead className="text-caption text-muted"><tr><th className="py-2">Week</th><th>Status</th><th>Orders</th><th>Kitchens</th><th>Delivery partners</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody className="divide-y divide-line">
            {(runs.data ?? []).map((r) => (
              <tr key={r.id} className={open === r.id ? "bg-peacock-wash" : ""}>
                <td className="stack-title py-3 font-bold"><span className="whitespace-nowrap">{r.period_start} →</span> <span className="whitespace-nowrap">{r.period_end}</span></td><td data-label="Status">{RUN_STATUS[r.status] ?? r.status}</td><td data-label="Orders">{r.totals.orders ?? 0}</td>
                <td data-label="Kitchens"><span>{money(r.totals.restaurants, r.currency, 2)} <span className="text-muted">· {r.totals.restaurant_statements ?? 0}</span></span></td><td data-label="Delivery partners"><span>{money(r.totals.riders, r.currency, 2)} <span className="text-muted">· {r.totals.rider_statements ?? 0}</span></span></td>
                <td className="stack-actions space-x-2 space-y-2 text-right">
                  <button type="button" onClick={() => setOpen(r.id)} className="h-8 rounded-full border border-line-strong px-3 text-label">Statements</button>
                  {r.status === "draft" && can(me, "payouts.approve", r.country) && r.created_by !== me?.user_id ? (
                    <button type="button" onClick={() => void act(() => adminApi.post(`/user/finance/payout-runs/${r.id}/approve`), "Approved and paid.")} className="h-8 rounded-full bg-peacock px-3 text-label text-white">Approve and pay</button>
                  ) : null}
                  {r.status === "partially_paid" && can(me, "payouts.approve", r.country) ? (
                    <button type="button" onClick={() => void act(() => adminApi.post(`/user/finance/payout-runs/${r.id}/retry`), "Retried.")} className="h-8 rounded-full border border-line-strong px-3 text-label">Retry unpaid</button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {runs.isLoading ? <p aria-busy="true" className="text-small text-muted">Loading payout runs…</p> : null}
        {!target && me ? <p className="text-small text-muted">Pick a country above to see its payout runs.</p> : null}
        {runs.isError ? <p role="alert" className="text-small">The payout runs didn&apos;t load. <button type="button" onClick={() => void runs.refetch()} className="font-bold text-peacock">Try again</button></p> : null}
        {runs.data && runs.data.length === 0 ? <p className="text-small text-muted">No payout runs yet. Prepare one for a week once it has delivered orders; a second finance admin approves and pays it.</p> : null}
      </section>
      {open && run.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Statements">
          <h2 className="m-0 mb-3 text-h3">Statements · {run.data.period_start} → {run.data.period_end}</h2>
          <p className="mb-3 text-small text-muted">Transfers go only to payout accounts that are ready. Anyone still onboarding waits and is paid as soon as their account is ready; send them a set-up link.</p>
          <div className="table-scroll"><table className="table-stack w-full text-left text-small tabular-nums [&_td]:pr-3 [&_th]:pr-3">
            <thead className="text-caption text-muted"><tr><th className="py-2">Payee</th><th>Type</th><th>Amount</th><th>Transfer</th><th>Payout set-up</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody className="divide-y divide-line">
              {run.data.statements.map((s) => (
                <tr key={s.id} data-testid="statement-row"><td className="stack-title py-2.5 font-semibold">{s.payee_name}</td>
                  <td data-label="Type">{s.payee_type === "restaurant" ? "Kitchen" : "Delivery partner"}</td>
                  <td data-label="Amount">{money(s.amount / 100, s.currency, 2)}</td>
                  <td data-label="Transfer"><div className="min-w-0 max-w-[300px] text-right md:text-left"><span className={`block font-semibold ${STATUS_STYLE[s.status] ?? ""}`}>{STATEMENT_STATUS[s.status] ?? s.status}</span>
                    {s.transfer_id ? <span className="block text-small text-muted">{s.transfer_id}{s.transferred_at ? ` · ${new Date(s.transferred_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : ""}</span> : null}
                    {s.error && ["failed", "reversed"].includes(s.status) ? <span className="block text-small text-muted">{s.error}</span> : null}</div></td>
                  <td data-label="Payout set-up"><SetupPill state={s.payout_setup} /></td>
                  <td className="stack-actions text-right">{s.payout_setup !== "ready" && s.status !== "paid" && can(me, "finance.edit", run.data!.country)
                    ? <SetupLinkButton kind={s.payee_type} id={s.payee_id} /> : null}</td></tr>
              ))}
            </tbody>
          </table></div>
          {run.data.statements.length === 0 ? <p className="text-small text-muted">No statements: nothing was delivered in this period.</p> : null}
        </section>
      ) : null}
      {open && run.isLoading ? <p aria-busy="true" className="rounded-2xl bg-white p-6 text-small text-muted">Loading statements…</p> : null}
      {open && run.isError ? <p role="alert" className="rounded-2xl bg-white p-6 text-small">The statements didn&apos;t load. <button type="button" onClick={() => void run.refetch()} className="font-bold text-peacock">Try again</button></p> : null}
      {contribution.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Contribution per order">
          <h2 className="m-0 mb-1 text-h3">Contribution per order · {start} → {end}</h2>
          <p className="mb-3 text-small text-muted">What the platform keeps of an average delivered order, after payment fees, delivery partner pay (tips are the delivery partner&apos;s), the offers we fund and the refunds we pay.
            {contribution.data.fees_estimated ? ` ${contribution.data.fees_estimated} older orders had no payment fee recorded; it's worked out from today's rule.` : ""}</p>
          <div className="table-scroll"><table className="w-full text-left text-small tabular-nums">
            <thead className="text-caption text-muted"><tr><th className="py-2">Per order</th>
              {contribution.data.cities.map((c) => <th key={c.city} className="text-right">{c.city} · {c.orders} orders</th>)}</tr></thead>
            <tbody className="divide-y divide-line tabular-nums">
              {CONTRIBUTION_ROWS.map(([k, label, sign]) => (
                <tr key={k}><td className="py-2">{label}</td>{contribution.data!.cities.map((c) => <td key={c.city} className="text-right">{sign < 0 ? "−" : ""}{money(Number(c.per_order[k] ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
              ))}
              <tr className="font-bold" data-testid="platform-keeps"><td className="py-2">Platform keeps</td>{contribution.data.cities.map((c) => <td key={c.city} className="text-right">{money(Number(c.per_order.keeps ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
            </tbody>
          </table></div>
          {contribution.data.cities.length === 0 ? <p className="text-small text-muted">No delivered orders in this period.</p> : null}
        </section>
      ) : null}
      {recon.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Reconciliation">
          <h2 className="m-0 mb-3 text-h3">Reconciliation · {start} → {end}</h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {[["Captured", recon.data.money.captured], ["Refunded", recon.data.money.refunded], ["Kitchens are owed", recon.data.money.restaurant_payable], ["Delivery partners are owed", recon.data.money.rider_payable],
              ["Tax owed", recon.data.money.tax_owed], ["Platform revenue", recon.data.money.platform_revenue], ["Payment fees", recon.data.money.payment_fees],
              ["Platform after payment fees", recon.data.money.platform_after_payment_fees], ["Delivered GMV", recon.data.money.delivered_gmv], ["Net collected", recon.data.money.net_collected]]
              .map(([l, v]) => <div key={l as string} className="rounded-xl bg-porcelain p-3"><div className="text-small text-muted">{l}</div><div className="text-h3 tabular-nums">{money(Number(v ?? 0) / 100, recon.data!.currency, 2)}</div></div>)}
          </div>
          <p className="mt-3 text-small">{recon.data.orders.delivered} delivered · {recon.data.orders.cancelled} cancelled · {recon.data.orders.open} still open · {recon.data.refunds_not_settled} refunds not settled ·{" "}
            {recon.data.issues.length ? <b className="text-chili">{recon.data.issues.length} issues to look at</b> : <span className="text-peacock">everything lines up</span>}</p>
        </section>
      ) : null}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><FinancePage /></Suspense>;
}
