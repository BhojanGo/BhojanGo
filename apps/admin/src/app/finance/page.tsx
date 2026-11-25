"use client";
// Finance: weekly payout runs for a country (prepare → a second finance admin
// approves and pays → retry what's waiting), each statement, and the week's
// reconciliation (money in vs owed). Each country in its own currency.
// R12: a run covers a week that has ended (Monday to Sunday in the country's time
// zone; the API lists them), and contribution and reconciliation show the week of
// the selected run. An empty figure is $0.00 (R13).
// R23: a kitchen's week below zero is carried into its next statement ("Carried from last
// week") and nothing is paid until it is covered; never written off, never charged. Four weeks
// below zero in a row: "Kitchens to collect from" (finance collects by arrangement).
// R24: below zero, a kitchen statement says this week's own result and what is still below zero
// from earlier weeks on separate lines (belowZeroLines, the same as the Kitchen app).
// R25: no legal entity name in Markets: a warning that commission tax invoices can't be issued.
import { belowZeroLines } from "@bhojango/ui/statement";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { Disputes } from "@/components/finance/Disputes";
import { type PayeeKind, SetupLinkButton, SetupPill, type SetupState } from "@/components/finance/PayoutSetup";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { apiMessage, money, useScope } from "@/lib/ops";
import { count } from "@/lib/count";

interface Run {
  id: string; country: string; currency: string; period_start: string; period_end: string; status: string; created_by: string;
  approved_by: string | null; paid_at: string | null;
  totals: { orders?: number; restaurants?: string; riders?: string; restaurant_statements?: number; rider_statements?: number;
    /** R23 (major units): carried in from last week (<= 0), carried on to next week (<= 0), paid to kitchens after them */
    kitchen_carried_in?: string; kitchen_carried_forward?: string; restaurants_to_pay?: string; kitchens_to_collect?: number };
}
interface Statement {
  id: string; payee_type: PayeeKind; payee_id: string; payee_name: string; amount: number; currency: string; status: string; error: string | null;
  summary: Record<string, unknown>; transfer_id: string | null; transferred_at: string | null; attempts: number; payout_setup: SetupState;
  /** R23: minor units, <= 0, already in amount; weeks below zero in a row */
  carried_in?: number; negative_weeks?: number; negative_since?: string | null;
  /** R27: the week's one status, the same words the payee's app shows (core_api statements.shown_status) */
  shown_status?: string; paid_on?: string | null;
}
/** R23: a kitchen below zero for 4 weeks or more (amount: what it owes, minor units). */
interface Collect { restaurant_id: string; kitchen: string; currency: string; amount: number; weeks: number; since: string; week_start: string; week_end: string }
interface Recon {
  currency: string; orders: { total: number; delivered: number; cancelled: number; open: number };
  money: Record<string, number>; issues: { order_id: string; issue: string }[]; refunds_not_settled: number;
  /** R40: orders whose card fee is the estimate, not what the provider reported. */
  card_fees_estimated?: number;
  /** R40: the week's money its payout run doesn't pay (yet), and why (minor units). */
  not_in_run?: { orders: number; restaurants: number; riders: number; reason: string | null; chargeback_holds: number } | null;
  /** R16: tax owed by type: what customers paid, GST on our commission, TDS on kitchen payouts. */
  tax_owed_by_type?: { customer: number; commission: number; tds: number };
}

interface Contribution {
  currency: string; fees_estimated: number;
  cities: { city: string; orders: number; totals: Record<string, string>; per_order: Record<string, string | null> }[];
  all: { orders: number; totals: Record<string, string>; per_order: Record<string, string | null> };
}

const CONTRIBUTION_ROWS: [string, string, number][] = [
  ["commission", "Commission", 1], ["customer_fees", "Customer fees", 1], ["platform_promos", "Offers we fund", -1],
  ["rider_pay", "Delivery partner pay (tips excluded)", -1], ["refunds", "Refunds we pay", -1],
  ["min_pay_top_ups", "Minimum pay top-ups", -1],
];

const RUN_STATUS: Record<string, string> = { draft: "Waiting for approval", approved: "Approved", paid: "Paid", partially_paid: "Partly paid" };
// R27: the week's status in the same words as BhojanGo Kitchen and BhojanGo Delivery (shown_status from the API).
const STATEMENT_STATUS: Record<string, string> = {
  waiting_approval: "Waiting for approval", no_account: "Waiting for payout account", onboarding: "Waiting for payout set-up to finish",
  on_its_way: "On its way", not_paid: "Not paid yet", paid: "Paid", nothing_due: "Nothing to pay this week", failed: "Transfer failed",
  reversed: "Reversed", carried: "Below zero: carried to next week",
};
const STATUS_STYLE: Record<string, string> = {
  paid: "text-peacock", failed: "text-chili", reversed: "text-chili", onboarding: "text-kesar-ink", no_account: "text-kesar-ink", carried: "text-kesar-ink",
};
/** "Paid on 17 Nov 2026" or the week's status (an older API: its own status). */
function statementStatus(s: Pick<Statement, "status" | "shown_status" | "paid_on">): string {
  const code = s.shown_status ?? (s.status === "pending" ? "not_paid" : s.status);
  if (code === "paid" && s.paid_on) return `Paid on ${dayLabel(s.paid_on)}`;
  return STATEMENT_STATUS[code] ?? code;
}
const COLLECT_AFTER_WEEKS = 4;

function dayLabel(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

interface Weeks { timezone: string; today: string; weeks: { start: string; end: string }[];
  /** R25: the country's legal entity has no name in Markets, so no commission tax invoice can be issued */
  legal_name_missing?: boolean; country_name?: string }

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
  // R23: kitchens below zero for 4 weeks or more (finance collects by arrangement; nothing is charged).
  const collect = useQuery({
    queryKey: ["to-collect", target], enabled: Boolean(target) && can(me, "finance.view", target),
    queryFn: async () => (await adminApi.get<Collect[]>("/user/finance/to-collect", { params: { country: target } })).data,
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
        <h1 className="m-0 text-h1">Finance{target ? ` · ${markets?.find((c) => c.code === target)?.name ?? weeks.data?.country_name ?? target}` : ""}</h1>
        {(() => {
          // R15: whose money this is: the country's legal entity (Markets), never a name in code.
          const legal = (markets?.find((c) => c.code === target)?.settings.legal ?? {}) as Record<string, string>;
          return legal.name ? <p data-testid="finance-entity" className="mt-1 text-label text-kohl">{legal.name}{legal.gstin ? ` · GSTIN ${legal.gstin}` : ""}</p> : null;
        })()}
        <p className="mt-1 text-small text-muted">Payouts run weekly per country, for a week that has ended: Monday to Sunday in the country&apos;s payout time zone{weeks.data ? ` (${weeks.data.timezone})` : ""}. The admin who prepares a run can&apos;t approve it.</p>
        {weeks.data?.legal_name_missing ? (
          // R25: an invoice never prints a placeholder for the supplier; the API refuses it until this is filled in.
          <p role="alert" data-testid="legal-name-missing" className="mt-2 rounded-xl bg-kesar-tint px-3 py-2 text-small text-kesar-ink">
            <b>Commission tax invoices can&apos;t be issued:</b> the legal entity name for {weeks.data.country_name ?? target} is missing in Markets.
            Restaurants asking for their invoice are told it isn&apos;t ready yet.{" "}
            <Link href={`/markets/${target}`} className="font-bold text-kesar-ink underline">Set it in Markets</Link>
          </p>
        ) : null}
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
          <thead className="text-caption text-muted"><tr><th className="py-2">Week</th><th>Status</th><th>Orders</th><th>Restaurants</th><th>Delivery partners</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody className="divide-y divide-line">
            {(runs.data ?? []).map((r) => (
              <tr key={r.id} className={selected === r.id ? "bg-peacock-wash" : ""}>
                <td className="stack-title py-3 font-bold"><span className="whitespace-nowrap">{weekLabel(r.period_start, r.period_end)}</span></td><td data-label="Status">{RUN_STATUS[r.status] ?? r.status}</td><td data-label="Orders">{r.totals.orders ?? 0}</td>
                <td data-label="Restaurants"><span>{money(r.totals.restaurants_to_pay ?? r.totals.restaurants, r.currency, 2)} <span className="text-muted">· {r.totals.restaurant_statements ?? 0}</span></span>
                  {Number(r.totals.kitchen_carried_in ?? 0) || Number(r.totals.kitchen_carried_forward ?? 0) ? (
                    // R23: earned this week, the balances carried in and on, and what is paid after them
                    <span data-testid="run-carry" className="block text-small text-muted">Earned {money(r.totals.restaurants, r.currency, 2)}
                      {Number(r.totals.kitchen_carried_in ?? 0) ? ` · carried in ${money(r.totals.kitchen_carried_in, r.currency, 2)}` : ""}
                      {Number(r.totals.kitchen_carried_forward ?? 0) ? ` · carried on ${money(r.totals.kitchen_carried_forward, r.currency, 2)}` : ""}</span>
                  ) : null}</td><td data-label="Delivery partners"><span>{money(r.totals.riders, r.currency, 2)} <span className="text-muted">· {r.totals.rider_statements ?? 0}</span></span></td>
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
                <tr key={s.id} data-testid="statement-row"><td className="stack-title py-2.5 font-semibold">
                  <Link href={`/finance/statements/${s.id}`} className="text-peacock">{s.payee_name}</Link></td>
                  <td data-label="Type">{s.payee_type === "restaurant" ? "Restaurant" : "Delivery partner"}</td>
                  <td data-label="Amount"><div className="text-right md:text-left">{money(s.amount / 100, s.currency, 2)}
                    {s.carried_in ? <span data-testid="carried-in" className="block text-small text-muted">Carried from last week {money(s.carried_in / 100, s.currency, 2)}</span> : null}
                    {s.payee_type === "restaurant" ? belowZeroLines(s.amount, s.carried_in).map((l) => (
                      <span key={l.kind} data-testid={`below-zero-${l.kind}`} className="block text-small text-kesar-ink">
                        {l.kind === "week" ? `This week came to ${money((l.amount ?? 0) / 100, s.currency, 2)} below zero.`
                          : l.kind === "earlier" ? `Still ${money((l.amount ?? 0) / 100, s.currency, 2)} below zero from earlier weeks · carried to next week.`
                          : "Carried to next week."}
                      </span>)) : null}
                    {(s.negative_weeks ?? 0) >= COLLECT_AFTER_WEEKS ? <span className="mt-1 inline-block rounded-full bg-kesar-tint px-2 py-0.5 text-caption text-kesar-ink">To collect · {count(s.negative_weeks ?? 0, "week")}</span> : null}</div></td>
                  <td data-label="Transfer"><div className="min-w-0 max-w-[300px] text-right md:text-left"><span data-testid="statement-status" className={`block font-semibold ${STATUS_STYLE[s.shown_status ?? s.status] ?? ""}`}>{statementStatus(s)}</span>
                    {s.transfer_id ? <span className="block text-small text-muted">{s.transfer_id}{s.transferred_at ? ` · ${new Date(s.transferred_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : ""}</span> : null}
                    {s.error && ["failed", "reversed"].includes(s.status) ? <span className="block text-small text-muted">{s.error}</span> : null}</div></td>
                  <td data-label="Payout set-up"><SetupPill state={s.payout_setup} /></td>
                  <td className="stack-actions text-right">{s.payout_setup !== "ready" && !["paid", "carried"].includes(s.status) && can(me, "finance.edit", run.data!.country)
                    ? <SetupLinkButton kind={s.payee_type} id={s.payee_id} /> : null}</td></tr>
              ))}
            </tbody>
          </table></div>
          {run.data.statements.length === 0 ? <p className="text-small text-muted">No statements: nothing was delivered in this period.</p> : null}
          {run.data.statements.some((s) => s.carried_in || s.status === "carried" || s.amount < 0) ? (
            <p className="mt-3 text-small text-muted">A restaurant statement below zero pays nothing: the balance is carried into its next week&apos;s statement as &ldquo;Carried from last week&rdquo; and comes off what that week pays. Nothing is written off and a restaurant is never charged.</p>
          ) : null}
        </section>
      ) : null}
      {target && can(me, "finance.view", target) ? <Disputes country={target} /> : null}
      {collect.data && collect.data.length > 0 ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Restaurants to collect from" data-testid="to-collect">
          <h2 className="m-0 mb-1 text-h3">Restaurants to collect from</h2>
          <p className="mb-3 text-small text-muted">These restaurants&apos; statements have been below zero for {COLLECT_AFTER_WEEKS} weeks or more in a row: their sales haven&apos;t covered the refunds and offers they owe. Nothing is charged automatically; agree with the restaurant how it pays. Until then each week&apos;s sales keep coming off the balance.</p>
          <div className="table-scroll"><table className="table-stack w-full text-left text-small tabular-nums [&_td]:pr-3 [&_th]:pr-3">
            <thead className="text-caption text-muted"><tr><th className="py-2">Restaurant</th><th>Owes</th><th>Weeks below zero</th><th>Since</th><th>Latest statement</th></tr></thead>
            <tbody className="divide-y divide-line">
              {collect.data.map((k) => (
                <tr key={k.restaurant_id} data-testid="collect-row"><td className="stack-title py-2.5 font-semibold">{k.kitchen}</td>
                  <td data-label="Owes" className="font-semibold text-chili">{money(k.amount / 100, k.currency, 2)}</td>
                  <td data-label="Weeks below zero">{k.weeks}</td>
                  <td data-label="Since">{dayLabel(k.since)}</td>
                  <td data-label="Latest statement">{weekLabel(k.week_start, k.week_end)}</td></tr>
              ))}
            </tbody>
          </table></div>
        </section>
      ) : null}
      {selected && run.isLoading ? <p aria-busy="true" className="rounded-2xl bg-white p-6 text-small text-muted">Loading statements…</p> : null}
      {selected && run.isError ? <p role="alert" className="rounded-2xl bg-white p-6 text-small">The statements didn&apos;t load. <button type="button" onClick={() => void run.refetch()} className="font-bold text-peacock">Try again</button></p> : null}
      {contribution.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Contribution per order">
          <h2 className="m-0 mb-1 text-h3">Contribution per order · {weekLabel(start, end)}</h2>
          <p className="mb-3 text-small text-muted">What BhojanGo keeps of an average delivered order: its platform fee (and any commission), less the offers it funds and the refunds it pays. The delivery fee and tips are the delivery partner&apos;s; card fees are paid by restaurants, out of their food and packaging.</p>
          <div className="table-scroll"><table className="w-full text-left text-small tabular-nums">
            <thead className="text-caption text-muted"><tr><th className="py-2">Per order</th>
              {contribution.data.cities.map((c) => <th key={c.city} className="text-right">{c.city} · {count(c.orders, "order")}</th>)}</tr></thead>
            <tbody className="divide-y divide-line tabular-nums">
              {CONTRIBUTION_ROWS.map(([k, label, sign]) => (
                <tr key={k}><td className="py-2">{label}</td>{contribution.data!.cities.map((c) => {
                  const v = Number(c.per_order[k] ?? 0);
                  return <td key={c.city} className="text-right">{v ? `${sign < 0 ? "−" : ""}${money(v, contribution.data!.currency, 2)}` : money(0, contribution.data!.currency, 2)}</td>;
                })}</tr>
              ))}
              <tr className="font-bold" data-testid="platform-keeps"><td className="py-2">BhojanGo keeps</td>{contribution.data.cities.map((c) => <td key={c.city} className="text-right">{money(Number(c.per_order.keeps ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
              {/* R40: for information: the restaurant pays it, never BhojanGo */}
              <tr className="text-muted" data-testid="card-fees-row"><td className="py-2">Card fees (paid by restaurants, not BhojanGo){contribution.data.fees_estimated ? <span data-testid="fees-estimated" className="ml-2 rounded-full bg-kesar-tint px-2 py-0.5 text-caption text-kesar-ink">estimated</span> : null}</td>
                {contribution.data.cities.map((c) => <td key={c.city} className="text-right">{money(Number(c.per_order.card_fees ?? 0), contribution.data!.currency, 2)}</td>)}</tr>
            </tbody>
          </table></div>
          {contribution.data.cities.length === 0 ? <p className="text-small text-muted">No delivered orders in this week, so there is nothing to average.</p> : null}
        </section>
      ) : null}
      {recon.data ? (
        <section className="rounded-2xl bg-white p-6" aria-label="Reconciliation">
          <h2 className="m-0 mb-3 text-h3">Reconciliation · {weekLabel(start, end)}</h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {([["Captured", "captured"], ["Refunded", "refunded"], ["Restaurants are owed", "restaurant_payable"], ["Delivery partners are owed", "rider_payable"], ["Minimum pay top-ups", "min_pay_top_ups"],
              ["Card fees (paid by restaurants)", "card_fees"], ["Tax owed", "tax_owed"], ["BhojanGo keeps", "platform_revenue"],
              ["Delivered GMV", "delivered_gmv"], ["Net collected", "net_collected"],
              // R23: kitchens paid = kitchens are owed + carried from last week - carried to next week
              ["Restaurants: carried from last week", "kitchen_carried_in"], ["Restaurants: carried to next week", "kitchen_carried_forward"],
              ["Restaurants are paid", "restaurant_to_pay"]] as const)
              .map(([l0, k]) => [k === "card_fees" && recon.data!.card_fees_estimated ? `${l0}, estimated` : l0, k] as const)
              .map(([l, k]) => <div key={k} className="rounded-xl bg-porcelain p-3"><div className="text-small text-muted">{l}</div>
                <div className="text-h3 tabular-nums">{money(Number(recon.data!.money[k] ?? 0) / 100, recon.data!.currency, 2)}</div>
                {k === "tax_owed" && recon.data!.tax_owed_by_type ? (
                  // R16: by type: customers' tax, GST on our commission, TDS (both taken from kitchen payouts)
                  <div data-testid="tax-by-type" className="mt-1 text-small text-muted">
                    Customers {money(recon.data!.tax_owed_by_type.customer / 100, recon.data!.currency, 2)}
                    {" · "}On commission {money(recon.data!.tax_owed_by_type.commission / 100, recon.data!.currency, 2)}
                    {" · "}TDS {money(recon.data!.tax_owed_by_type.tds / 100, recon.data!.currency, 2)}
                  </div>
                ) : null}</div>)}
          </div>
          <p className="m-0 mt-3 text-small text-muted" data-testid="recon-identity">Captured = refunded + restaurants are owed + card fees + delivery partners are owed + tax + BhojanGo keeps.</p>
          {recon.data.not_in_run ? (
            // R40: why the payout run pays less than "owed" for the same week
            <p className="mt-3 rounded-xl bg-kesar-tint p-3 text-small text-kesar-ink" data-testid="not-in-run">
              {recon.data.not_in_run.orders ? <>Not in this payout yet: {money((recon.data.not_in_run.restaurants + recon.data.not_in_run.riders) / 100, recon.data.currency, 2)} ({count(recon.data.not_in_run.orders, "order")}: restaurants {money(recon.data.not_in_run.restaurants / 100, recon.data.currency, 2)}, delivery partners {money(recon.data.not_in_run.riders / 100, recon.data.currency, 2)}). {recon.data.not_in_run.reason}.</> : null}
              {recon.data.not_in_run.chargeback_holds ? <> Held for open chargebacks: {money(recon.data.not_in_run.chargeback_holds / 100, recon.data.currency, 2)}.</> : null}
            </p>
          ) : null}
          <p className="mt-3 text-small text-muted">Restaurants are paid what they are owed this week, plus what earlier weeks left below zero (carried from last week), less what this week leaves below zero (carried to next week). Nothing below zero is written off or charged to a restaurant.</p>
          <p className="mt-3 text-small">{recon.data.orders.delivered} delivered · {recon.data.orders.cancelled} cancelled · {recon.data.orders.open} still open · {count(recon.data.refunds_not_settled, "refund")} not settled ·{" "}
            {recon.data.issues.length ? <b className="text-chili">{count(recon.data.issues.length, "issue")} to look at</b> : <span className="text-peacock">everything lines up</span>}</p>
        </section>
      ) : null}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><FinancePage /></Suspense>;
}
