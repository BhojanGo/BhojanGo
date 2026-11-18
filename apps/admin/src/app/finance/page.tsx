"use client";
// Finance: weekly payout runs for a country (prepare → a second finance admin
// approves and pays → retry what's waiting), each statement, and the week's
// reconciliation (money in vs owed). Each country in its own currency.
// R12: a run covers a week that has ended (Monday to Sunday in the country's time
// zone; the API lists them), and contribution and reconciliation show the week of
// the selected run. An empty figure is $0.00 (R13).
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
  ["min_pay_top_ups", "Minimum pay top-ups", -1],
];

const RUN_STATUS: Record<string, string> = { draft: "Waiting for approval", approved: "Approved", paid: "Paid", partially_paid: "Partly paid" };
const STATEMENT_STATUS: Record<string, string> = {
  pending: "Not paid yet", paid: "Paid", failed: "Transfer failed", no_account: "No payout account", onboarding: "Waiting for onboarding", reversed: "Reversed",
};
const STATUS_STYLE: Record<string, string> = { paid: "text-peacock", failed: "text-chili", reversed: "text-chili", onboarding: "text-kesar-ink", no_account: "text-kesar-ink" };

interface Weeks { timezone: string; today: string; weeks: { start: string; end: string }[] }

/** "Mon 9 Nov – Sun 15 Nov" for a run's period (end is the next Monday, not included). */
function weekLabel(start: string, end: string): string {
  const day = (iso: string, back = 0) => {
    const d = new Date(`${iso}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() - back);
    return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }).replace(",", "");
  };
  return `${day(start)} – ${day(end, 1)}`;
}

function addDays(iso: string, n: number): string {
  return new Date(Date.parse(`${iso}T12:00:00Z`) + n * 864e5).toISOString().slice(0, 10);
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
  // The selected run (the newest until another is picked): its statements, and the reports' week.
  const selected = open ?? runs.data?.[0]?.id ?? null;
  const run = useQuery({
    queryKey: ["payout-run", selected], enabled: Boolean(selected),
    queryFn: async () => (await adminApi.get<Run & { statements: Statement[] }>(`/user/finance/payout-runs/${selected}`)).data,
  });
  // The weeks a run may cover (ended, Monday to Sunday in the country's zone), newest first.
  const weeks = useQuery({ queryKey: ["payout-weeks", target], enabled: Boolean(target),
    queryFn: async () => (await adminApi.get<Weeks>("/user/finance/payout-weeks", { params: { country: target } })).data });
  const [picked, setPicked] = useState<string | null>(null);
  const week = weeks.data?.weeks.find((w) => w.start === picked) ?? weeks.data?.weeks[0] ?? null;
  const prepared = new Set((runs.data ?? []).map((r) => r.period_start));
  // The reports follow the selected run (the newest one until another is picked); no run: the picked week.
  const shown = (runs.data ?? []).find((r) => r.id === selected);
  const [start, end] = shown ? [shown.period_start, shown.period_end] : week ? [week.start, week.end] : ["", ""];
  const recon = useQuery({
    queryKey: ["recon", target, start, end],
    queryFn: async () => (await adminApi.get<Recon>("/user/finance/reconciliation", { params: { country: target, start, end } })).data,
    enabled: Boolean(target && start) && can(me, "finance.view", target),
  });
  const contribution = useQuery({
    queryKey: ["contribution", scope, target, start, end],
    queryFn: async () => (await adminApi.get<Contribution>("/user/finance/contribution", { params: { scope: city ?? region ?? target, start, end } })).data,
    enabled: Boolean(target && start) && can(me, "finance.view", city ?? region ?? target),
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
        <p className="mt-1 text-small text-muted">Payouts run weekly per country, for a week that has ended: Monday to Sunday in the country&apos;s time zone{weeks.data ? ` (${weeks.data.timezone})` : ""}. The admin who prepares a run can&apos;t approve it.</p>
        {country === "ALL" && (markets?.length ?? 0) > 1 ? (
          <p className="mt-2 rounded-xl bg-kesar-tint px-3 py-2 text-small text-kesar-ink">Money stays in each country&apos;s currency, so Finance shows one country at a time. Pick a country above to see another.</p>
        ) : null}
      </div>
      <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Payout runs">
        <div className="flex flex-wrap items-end gap-3">
          <h2 className="m-0 flex-1 text-h3">Payout runs</h2>
          {can(me, "finance.edit", target) && weeks.data ? (
            <>
              <label className="text-label">Week{" "}
                <select data-testid="payout-week" value={week?.start ?? ""} onChange={(e) => setPicked(e.target.value)} className="ml-1 h-10 rounded-lg border border-line bg-white px-2">
                  {weeks.data.weeks.map((w) => <option key={w.start} value={w.start}>{weekLabel(w.start, w.end)}{prepared.has(w.start) ? " · prepared" : ""}</option>)}
                </select>
              </label>
              <button type="button" disabled={!week || prepared.has(week.start)}
                onClick={() => week && void act(() => adminApi.post("/user/finance/payout-runs", { country: target, period_start: week.start, period_end: week.end }), "Run prepared: a second finance admin approves it.")}
                className="h-10 rounded-full bg-peacock px-4 font-bold text-white disabled:bg-[#8FB3B7]">
                {week && prepared.has(week.start) ? "Already prepared" : "Prepare payouts"}
              </button>
            </>
          ) : null}
        </div>
        {can(me, "finance.edit", target) && weeks.data ? <p className="m-0 text-small text-muted">This week ({weekLabel(weeks.data.weeks[0].end, addDays(weeks.data.weeks[0].end, 7))}) can be prepared once it ends.</p> : null}
        {msg ? <p role="status" className={`text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
        <div className="table-scroll"><table className="table-stack w-full text-left text-small tabular-nums [&_td]:pr-3 [&_th]:pr-3">
          <thead className="text-caption text-muted"><tr><th className="py-2">Week</th><th>Status</th><th>Orders</th><th>Kitchens</th><th>Delivery partners</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody className="divide-y divide-line">
            {(runs.data ?? []).map((r) => (
              <tr key={r.id} className={selected === r.id ? "bg-peacock-wash" : ""}>
                <td className="stack-title py-3 font-bold"><span className="whitespace-nowrap">{weekLabel(r.period_start, r.period_end)}</span></td><td data-label="Status">{RUN_STATUS[r.status] ?? r.status}</td><td data-label="Orders">{r.totals.orders ?? 0}</td>
                <td data-label="Kitchens"><span>{money(r.totals.restaurants, r.currency, 2)} <span className="text-muted">· {r.totals.restaurant_statements ?? 0}</span></span></td><td data-label="Delivery partners"><span>{money(r.totals.riders, r.currency, 2)} <span className="text-muted">· {r.totals.rider_statements ?? 0}</span></span></td>
                <td className="stack-actions space-x-2 space-y-2 text-right">
                  <button type="button" aria-pressed={selected === r.id} onClick={() => setOpen(r.id)} className="h-8 rounded-full border border-line-strong px-3 text-label">{selected === r.id ? "Selected" : "Select"}</button>
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
      {selected && run.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Statements">
          <h2 className="m-0 mb-3 text-h3">Statements · {weekLabel(run.data.period_start, run.data.period_end)}</h2>
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
      {selected && run.isLoading ? <p aria-busy="true" className="rounded-2xl bg-white p-6 text-small text-muted">Loading statements…</p> : null}
      {selected && run.isError ? <p role="alert" className="rounded-2xl bg-white p-6 text-small">The statements didn&apos;t load. <button type="button" onClick={() => void run.refetch()} className="font-bold text-peacock">Try again</button></p> : null}
      {contribution.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Contribution per order">
          <h2 className="m-0 mb-1 text-h3">Contribution per order · {weekLabel(start, end)}</h2>
          <p className="mb-3 text-small text-muted">What the platform keeps of an average delivered order, after payment fees, delivery partner pay (tips are the delivery partner&apos;s), the offers we fund and the refunds we pay.
            {contribution.data.fees_estimated ? ` ${contribution.data.fees_estimated} older orders had no payment fee recorded; it's worked out from today's rule.` : ""}</p>
          <div className="table-scroll"><table className="w-full text-left text-small tabular-nums">
            <thead className="text-caption text-muted"><tr><th className="py-2">Per order</th>
              {contribution.data.cities.map((c) => <th key={c.city} className="text-right">{c.city} · {c.orders} orders</th>)}</tr></thead>
            <tbody className="divide-y divide-line tabular-nums">
              {CONTRIBUTION_ROWS.map(([k, label, sign]) => (
                <tr key={k}><td className="py-2">{label}</td>{contribution.data!.cities.map((c) => {
                  const v = Number(c.per_order[k] ?? 0);
                  return <td key={c.city} className="text-right">{v ? `${sign < 0 ? "−" : ""}${money(v, contribution.data!.currency, 2)}` : money(0, contribution.data!.currency, 2)}</td>;
                })}</tr>
              ))}
              <tr className="font-bold" data-testid="platform-keeps"><td className="py-2">Platform keeps</td>{contribution.data.cities.map((c) => <td key={c.city} className="text-right">{money(Number(c.per_order.keeps ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
            </tbody>
          </table></div>
          {contribution.data.cities.length === 0 ? <p className="text-small text-muted">No delivered orders in this week, so there is nothing to average.</p> : null}
        </section>
      ) : null}
      {recon.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Reconciliation">
          <h2 className="m-0 mb-3 text-h3">Reconciliation · {weekLabel(start, end)}</h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {([["Captured", "captured"], ["Refunded", "refunded"], ["Kitchens are owed", "restaurant_payable"], ["Delivery partners are owed", "rider_payable"], ["Minimum pay top-ups", "min_pay_top_ups"],
              ["Tax owed", "tax_owed"], ["Platform revenue", "platform_revenue"], ["Payment fees", "payment_fees"],
              ["Platform after payment fees", "platform_after_payment_fees"], ["Delivered GMV", "delivered_gmv"], ["Net collected", "net_collected"]] as const)
              .map(([l, k]) => <div key={k} className="rounded-xl bg-porcelain p-3"><div className="text-small text-muted">{l}</div>
                <div className="text-h3 tabular-nums">{money(Number(recon.data!.money[k] ?? 0) / 100, recon.data!.currency, 2)}</div></div>)}
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
