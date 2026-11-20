"use client";
// Incidents (R17; docs/launch/incident-plan.md): what admin uses when something breaks.
// 1. Pause ordering for a city, a country or everywhere (customers see a note on the website and in the app).
// 2. Pause or resume a kitchen ("Closed for now" for customers; the kitchen can't undo it).
// 3. Bulk refund: pick orders by kitchen, zone and time window, preview the count and total, then refund in
//    full or a percentage. Above the city's auto-refund limit a second admin approves it.
// 4. Message customers in bulk: a bulk refund's customers or a city's, by push and email, in their language.
// Every action needs a reason and a confirmation step, and lands in the log at the bottom (the audit log).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useMemo, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useCity, useMarkets } from "@/lib/markets";
import { apiMessage, useScope } from "@/lib/ops";
import { unitsFor } from "@/lib/ruleWords";

interface Pause { id: string; scope: string; area: string; note: string | null; until: string | null; reason: string; created_at: string | null; ended_at: string | null; active: boolean }
interface PausedKitchen { id: string; name: string; city: string; reason: string | null; paused_at: string | null; back_at: string | null }
interface KitchenRef { id: string; name: string }
interface PreviewOrder { order_id: string; restaurant: string; status: string; placed_at: string | null; paid: number; amount: number; currency: string }
interface RefundPreview { orders: PreviewOrder[]; count: number; total: number; currency: string | null; auto_refund_limit: string; auto_refund_total_limit?: string; needs_approval: boolean; approval_reasons?: string[] }
interface BulkRefund { id: string; market_city: string; mode: string; percent: string | null; reason: string; count: number; total: number; currency: string; status: string; requested_by: string; refunded: number; failed: number; created_at: string | null }
interface Template { key: string; title: string; body: string; needs: string[]; per_order: boolean }
interface MessagePreview { city: string; recipients: number; skipped: number; only_test_accounts: boolean; sample: { title: string; body: string } }
interface LogEntry { at: string; action: string; scope: string; entity_type: string; entity_id: string; by: string; after: Record<string, unknown> | null }

const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");
const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const iso = (v: string) => (v ? new Date(v).toISOString() : null);
const ACTIONS: Record<string, string> = {
  "kitchen.paused": "Kitchen paused", "kitchen.resumed": "Kitchen resumed", "ordering.paused": "Ordering paused",
  "ordering.resumed": "Ordering resumed", "bulk_refund.requested": "Bulk refund asked for", "bulk_refund.approved": "Bulk refund approved",
  "bulk_refund.rejected": "Bulk refund rejected", "bulk_refund.done": "Bulk refund done", "customers.messaged": "Customers messaged",
};
const field = "mt-1 block h-10 rounded-lg border border-line px-2 font-normal";
const primary = "h-10 rounded-full bg-peacock px-4 font-bold text-white disabled:opacity-40";
const secondary = "h-10 rounded-full border border-line-strong px-4 font-bold disabled:opacity-40";
const danger = "h-10 rounded-full bg-chili px-4 font-bold text-white disabled:opacity-40";

/** A reason, then "Yes, …" / "Cancel": every incident action goes through this step. */
function Confirm({ title, children, yes, busy, onYes, onCancel, testId }: {
  title: string; children?: React.ReactNode; yes: string; busy: boolean; onYes: (reason: string) => void; onCancel: () => void; testId: string;
}) {
  const [reason, setReason] = useState("");
  return (
    <div role="dialog" aria-label={title} data-testid={testId} className="space-y-3 rounded-xl border-2 border-chili bg-danger-tint p-4">
      <p className="m-0 text-label">{title}</p>
      {children}
      <label className="block text-small font-bold">Reason (kept in the log)
        <input aria-label="Reason" value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} placeholder="What happened, in a few words"
          className="mt-1 block h-10 w-full rounded-lg border border-line bg-white px-2 font-normal" />
      </label>
      <div className="flex gap-2">
        <button type="button" disabled={busy || reason.trim().length < 5} onClick={() => onYes(reason.trim())} className={danger}>{yes}</button>
        <button type="button" onClick={onCancel} className={secondary}>Cancel</button>
      </div>
    </div>
  );
}

function useAct() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string): Promise<boolean> {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      await qc.invalidateQueries({ queryKey: ["incidents"] });
      return true;
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
      return false;
    } finally {
      setBusy(false);
    }
  }
  const note = msg ? <p role="status" className={`text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null;
  return { busy, act, note };
}

function OrderingPauses({ scope }: { scope: string }) {
  const { data: me } = useAdminMe();
  const { country, city } = parseScope(scope);
  const pauses = useQuery({ queryKey: ["incidents", "pauses"], queryFn: async () => (await adminApi.get<Pause[]>("/user/incidents/ordering-pauses")).data });
  const choices = [
    ...(city ? [{ code: city, label: "This city" }] : []),
    ...(country !== "ALL" ? [{ code: country, label: "This country" }] : []),
    { code: "*", label: "Everywhere" },
  ].filter((c) => can(me, "ordering.pause", c.code));
  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const [until, setUntil] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [ending, setEnding] = useState<string | null>(null);
  const { busy, act, note: status } = useAct();
  const pick = target || choices[0]?.code || "";
  const active = (pauses.data ?? []).filter((p) => p.active);
  return (
    <section aria-label="Pause ordering" className="space-y-3 rounded-2xl bg-white p-6">
      <h2 className="m-0 text-h2">Pause ordering</h2>
      <p className="m-0 text-small text-muted">New orders stop; orders already placed carry on. Customers see a note on the website and in the app.</p>
      {active.length ? (
        <ul className="space-y-2" aria-label="Paused now">
          {active.map((p) => (
            <li key={p.id} data-testid="pause-row" className="flex flex-wrap items-center gap-2 rounded-xl bg-danger-tint px-3 py-2 text-small">
              <b>{p.scope === "*" ? "Everywhere" : p.area}</b> paused {when(p.created_at)}{p.until ? ` until ${when(p.until)}` : ""} · {p.reason}{p.note ? ` · customers see “${p.note}”` : ""}
              {can(me, "ordering.pause", p.scope) ? (
                ending === p.id ? null : <button type="button" onClick={() => setEnding(p.id)} className={`ml-auto ${secondary}`}>Resume ordering</button>
              ) : null}
              {ending === p.id ? (
                <Confirm testId="confirm-resume-ordering" title={`Resume ordering in ${p.scope === "*" ? "every country" : p.area}?`} yes="Yes, resume ordering" busy={busy}
                  onCancel={() => setEnding(null)}
                  onYes={(reason) => void act(() => adminApi.post(`/user/incidents/ordering-pauses/${p.id}/end`, { reason, confirm: true }), "Ordering resumed.").then(() => setEnding(null))} />
              ) : null}
            </li>
          ))}
        </ul>
      ) : <p className="m-0 text-small" data-testid="no-pauses">Ordering is open everywhere you look after.</p>}
      {choices.length ? (
        <div className="flex flex-wrap items-end gap-3 text-small">
          <label className="font-bold">Where
            <select aria-label="Where" value={pick} onChange={(e) => setTarget(e.target.value)} className={field}>
              {choices.map((c) => <option key={c.code} value={c.code}>{c.label} ({c.code === "*" ? "all countries" : c.code})</option>)}
            </select>
          </label>
          <label className="font-bold">Note for customers (optional)
            <input aria-label="Note for customers" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Back by 9 pm" className={`${field} w-64`} />
          </label>
          <label className="font-bold">Until (optional)
            <input aria-label="Until" type="datetime-local" value={until} min={local(new Date())} onChange={(e) => setUntil(e.target.value)} className={field} />
          </label>
          {!confirming ? <button type="button" onClick={() => setConfirming(true)} className={danger}>Pause ordering…</button> : null}
        </div>
      ) : <p className="m-0 text-small text-muted">Pick a city or country in the scope bar to pause ordering there.</p>}
      {confirming ? (
        <Confirm testId="confirm-pause-ordering" title={`Pause new orders ${pick === "*" ? "in every country" : `in ${pick}`}${until ? ` until ${when(iso(until))}` : " until someone resumes it"}?`}
          yes="Yes, pause ordering" busy={busy} onCancel={() => setConfirming(false)}
          onYes={(reason) => void act(() => adminApi.post("/user/incidents/ordering-pauses", { scope: pick, reason, note: note || null, until: iso(until), confirm: true }),
            "Ordering paused. Customers see the note now.").then((ok) => ok && setConfirming(false))}>
          <p className="m-0 text-small">Customers see: “Ordering in … is paused for now while we fix a problem. Orders already on their way will still arrive.{note ? ` ${note}` : ""}”</p>
        </Confirm>
      ) : null}
      {status}
    </section>
  );
}

function Kitchens({ scope }: { scope: string }) {
  const { data: me } = useAdminMe();
  const { city } = parseScope(scope);
  const cityName = useCity(city ?? "").data?.name;
  const paused = useQuery({ queryKey: ["incidents", "kitchens"], queryFn: async () => (await adminApi.get<PausedKitchen[]>("/user/incidents/kitchens/paused")).data });
  const kitchens = useQuery({
    queryKey: ["incidents", "kitchen-refs", cityName], enabled: Boolean(cityName),
    queryFn: async () => (await adminApi.get<{ items: KitchenRef[] }>("/user/restaurants", { params: { city: cityName, limit: 100 } })).data.items,
  });
  const [q, setQ] = useState("");
  const [kitchen, setKitchen] = useState<KitchenRef | null>(null);
  const [backAt, setBackAt] = useState("");
  const [confirming, setConfirming] = useState<"pause" | string | null>(null);
  const { busy, act, note } = useAct();
  const mayPause = city ? can(me, "kitchens.pause", city) : false;
  const matches = (kitchens.data ?? []).filter((k) => !q || k.name.toLowerCase().includes(q.toLowerCase())).slice(0, 8);
  return (
    <section aria-label="Pause a kitchen" className="space-y-3 rounded-2xl bg-white p-6">
      <h2 className="m-0 text-h2">Pause a kitchen</h2>
      <p className="m-0 text-small text-muted">Customers see “Closed for now” and can&apos;t order; orders already placed carry on. The kitchen can&apos;t undo it from its tablet.</p>
      {(paused.data ?? []).length ? (
        <ul className="space-y-2" aria-label="Kitchens paused by an admin">
          {(paused.data ?? []).map((k) => (
            <li key={k.id} data-testid="paused-kitchen" className="flex flex-wrap items-center gap-2 rounded-xl bg-danger-tint px-3 py-2 text-small">
              <b>{k.name}</b> closed for now since {when(k.paused_at)}{k.back_at ? `, back at ${when(k.back_at)}` : ""} · {k.reason}
              {can(me, "kitchens.pause", k.city) && confirming !== k.id ? <button type="button" onClick={() => setConfirming(k.id)} className={`ml-auto ${secondary}`}>Resume</button> : null}
              {confirming === k.id ? (
                <Confirm testId="confirm-resume-kitchen" title={`Resume ${k.name}? Customers can order again at once.`} yes="Yes, resume" busy={busy} onCancel={() => setConfirming(null)}
                  onYes={(reason) => void act(() => adminApi.post(`/user/incidents/kitchens/${k.id}/resume`, { reason, confirm: true }), `${k.name} is open again.`).then(() => setConfirming(null))} />
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {mayPause ? (
        <>
          <div className="flex flex-wrap items-end gap-3 text-small">
            <label className="font-bold">Kitchen
              <input aria-label="Find a kitchen" value={q} onChange={(e) => { setQ(e.target.value); setKitchen(null); }} placeholder={`A kitchen in ${cityName ?? "this city"}`} className={`${field} w-72`} />
            </label>
            <label className="font-bold">Back at (optional)
              <input aria-label="Back at" type="datetime-local" value={backAt} min={local(new Date())} onChange={(e) => setBackAt(e.target.value)} className={field} />
            </label>
            {kitchen && confirming !== "pause" ? <button type="button" onClick={() => setConfirming("pause")} className={danger}>Pause {kitchen.name}…</button> : null}
          </div>
          {!kitchen && q ? (
            <div className="flex flex-wrap gap-2">
              {matches.map((k) => <button key={k.id} type="button" onClick={() => { setKitchen(k); setQ(k.name); }} className="h-9 rounded-full border border-line-strong px-3 text-small font-bold">{k.name}</button>)}
            </div>
          ) : null}
          {kitchen && confirming === "pause" ? (
            <Confirm testId="confirm-pause-kitchen" title={`Pause ${kitchen.name}${backAt ? ` until ${when(iso(backAt))}` : " until someone resumes it"}? Customers see “Closed for now”.`}
              yes="Yes, pause the kitchen" busy={busy} onCancel={() => setConfirming(null)}
              onYes={(reason) => void act(() => adminApi.post(`/user/incidents/kitchens/${kitchen.id}/pause`, { reason, back_at: iso(backAt), confirm: true }),
                `${kitchen.name} is closed for now.`).then((ok) => { if (ok) { setConfirming(null); setKitchen(null); setQ(""); } })} />
          ) : null}
        </>
      ) : <p className="m-0 text-small text-muted">Pick a city in the scope bar to pause one of its kitchens.</p>}
      {note}
    </section>
  );
}

function Refunds({ scope }: { scope: string }) {
  const { data: me } = useAdminMe();
  const { city } = parseScope(scope);
  const { data: markets } = useMarkets();
  const cityInfo = useCity(city ?? "").data;
  const units = unitsFor(city ?? scope, markets);
  const m = (minor: number) => units.money(minor / 100, 2);
  const list = useQuery({ queryKey: ["incidents", "refunds"], queryFn: async () => (await adminApi.get<BulkRefund[]>("/user/incidents/refunds")).data });
  const kitchens = useQuery({
    queryKey: ["incidents", "kitchen-refs", cityInfo?.name], enabled: Boolean(cityInfo?.name),
    queryFn: async () => (await adminApi.get<{ items: KitchenRef[] }>("/user/restaurants", { params: { city: cityInfo?.name, limit: 100 } })).data.items,
  });
  const now = useMemo(() => new Date(), []);
  const [kitchen, setKitchen] = useState("");
  const [zone, setZone] = useState("");
  const [from, setFrom] = useState(local(new Date(now.getTime() - 2 * 3600_000)));
  const [to, setTo] = useState(local(now));
  const [mode, setMode] = useState<"full" | "percent">("full");
  const [percent, setPercent] = useState("50");
  const [preview, setPreview] = useState<RefundPreview | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [deciding, setDeciding] = useState<{ id: string; approve: boolean } | null>(null);
  const { busy, act, note } = useAct();
  const pick = { city, restaurant_id: kitchen || null, zone_id: zone || null, placed_from: iso(from), placed_to: iso(to), mode, percent: mode === "percent" ? percent : null };
  const mayRefund = city ? can(me, "refunds.bulk", city) : false;
  return (
    <section aria-label="Bulk refund" className="space-y-3 rounded-2xl bg-white p-6">
      <h2 className="m-0 text-h2">Bulk refund</h2>
      <p className="m-0 text-small text-muted">Refund the paid orders of a kitchen, a zone or the whole city in a time window (7 days at most), in full or a percentage. BhojanGo pays it: kitchens&apos; payouts don&apos;t change. Above the city&apos;s automatic refund limit per order, a second admin approves it first.</p>
      {mayRefund ? (
        <div className="flex flex-wrap items-end gap-3 text-small">
          <label className="font-bold">Kitchen
            <select aria-label="Kitchen" value={kitchen} onChange={(e) => { setKitchen(e.target.value); setPreview(null); }} className={field}>
              <option value="">Every kitchen</option>
              {(kitchens.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </label>
          <label className="font-bold">Zone
            <select aria-label="Zone" value={zone} onChange={(e) => { setZone(e.target.value); setPreview(null); }} className={field}>
              <option value="">Every zone</option>
              {(cityInfo?.zones ?? []).map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
            </select>
          </label>
          <label className="font-bold">Placed from
            <input aria-label="Placed from" type="datetime-local" value={from} onChange={(e) => { setFrom(e.target.value); setPreview(null); }} className={field} />
          </label>
          <label className="font-bold">to
            <input aria-label="Placed to" type="datetime-local" value={to} onChange={(e) => { setTo(e.target.value); setPreview(null); }} className={field} />
          </label>
          <label className="font-bold">Refund
            <select aria-label="Refund" value={mode} onChange={(e) => { setMode(e.target.value as "full" | "percent"); setPreview(null); }} className={field}>
              <option value="full">In full (what is left)</option>
              <option value="percent">A percentage</option>
            </select>
          </label>
          {mode === "percent" ? (
            <label className="font-bold">Percent
              <input aria-label="Percent" inputMode="decimal" value={percent} onChange={(e) => { setPercent(e.target.value); setPreview(null); }} className={`${field} w-20`} />
            </label>
          ) : null}
          <button type="button" disabled={busy} className={secondary}
            onClick={() => void act(async () => setPreview((await adminApi.post<RefundPreview>("/user/incidents/refunds/preview", pick)).data), "Preview ready.")}>Preview</button>
        </div>
      ) : <p className="m-0 text-small text-muted">Pick a city in the scope bar to refund its orders.</p>}
      {preview ? (
        <div className="space-y-2 rounded-xl border border-line p-4 text-small" data-testid="refund-preview">
          <p className="m-0"><b>{preview.count} order{preview.count === 1 ? "" : "s"} · {m(preview.total)}</b>
            {preview.needs_approval ? <> · <span className="rounded-full bg-kesar-tint px-2 py-0.5 text-kesar-ink">needs a second admin ({[
              ...(preview.approval_reasons ?? ["order_over_limit"]).includes("order_over_limit") ? [`above ${units.money(Number(preview.auto_refund_limit), 2)} per order`] : [],
              ...(preview.approval_reasons ?? []).includes("total_over_limit") && preview.auto_refund_total_limit ? [`above ${units.money(Number(preview.auto_refund_total_limit), 2)} in all`] : [],
            ].join(" and ")})</span></> : " · runs at once (within the city's limits)"}</p>
          {preview.count ? (
            <div className="table-scroll max-h-64 overflow-auto"><table className="w-full text-left"><thead className="text-caption text-muted"><tr><th>Order</th><th>Kitchen</th><th>Status</th><th>Placed</th><th>Paid</th><th>Refund</th></tr></thead>
              <tbody>{preview.orders.map((o) => <tr key={o.order_id}><td>#{o.order_id.replace(/-/g, "").slice(0, 6).toUpperCase()}</td><td>{o.restaurant}</td><td>{o.status}</td><td>{when(o.placed_at)}</td><td>{m(o.paid)}</td><td>{m(o.amount)}</td></tr>)}</tbody></table></div>
          ) : null}
          {preview.count && !confirming ? <button type="button" onClick={() => setConfirming(true)} className={danger}>Refund {preview.count} order{preview.count === 1 ? "" : "s"}…</button> : null}
          {confirming ? (
            <Confirm testId="confirm-bulk-refund" title={`Refund ${m(preview.total)} on ${preview.count} order${preview.count === 1 ? "" : "s"}${preview.needs_approval ? " once a second admin approves" : " now"}?`}
              yes={preview.needs_approval ? "Yes, send for approval" : "Yes, refund now"} busy={busy} onCancel={() => setConfirming(false)}
              onYes={(reason) => void act(() => adminApi.post("/user/incidents/refunds", { ...pick, reason, confirm: true }),
                preview.needs_approval ? "Sent to a second admin to approve." : "Refunded.").then((ok) => { if (ok) { setConfirming(false); setPreview(null); } })} />
          ) : null}
        </div>
      ) : null}
      {(list.data ?? []).length ? (
        <div className="table-scroll"><table className="w-full text-left text-small" aria-label="Bulk refunds"><thead className="text-caption text-muted"><tr><th>Asked</th><th>City</th><th>Orders</th><th>Total</th><th>Refund</th><th>Reason</th><th>Status</th><th /></tr></thead>
          <tbody>{(list.data ?? []).map((b) => (
            <tr key={b.id} data-testid="bulk-refund-row">
              <td>{when(b.created_at)}</td><td>{b.market_city}</td><td>{b.count}</td><td>{unitsFor(b.market_city, markets).money(b.total / 100, 2)}</td>
              <td>{b.mode === "full" ? "In full" : `${Number(b.percent)}%`}</td><td>{b.reason}</td>
              <td>{b.status.replace(/_/g, " ")}{b.failed ? ` (${b.failed} failed)` : ""}</td>
              <td>{b.status === "pending_approval" && can(me, "refunds.approve", b.market_city) && b.requested_by !== me?.user_id ? (
                deciding?.id === b.id ? (
                  <Confirm testId="confirm-decide-refund" title={deciding.approve ? `Approve: refund ${unitsFor(b.market_city, markets).money(b.total / 100, 2)} on ${b.count} orders now?` : "Reject this bulk refund?"}
                    yes={deciding.approve ? "Yes, approve and refund" : "Yes, reject"} busy={busy} onCancel={() => setDeciding(null)}
                    onYes={(reason) => void act(() => adminApi.post(`/user/incidents/refunds/${b.id}/${deciding.approve ? "approve" : "reject"}`, { note: reason, confirm: true }),
                      deciding.approve ? "Approved and refunded." : "Rejected.").then(() => setDeciding(null))} />
                ) : (
                  <span className="flex gap-1">
                    <button type="button" onClick={() => setDeciding({ id: b.id, approve: true })} className="h-8 rounded-full bg-peacock px-3 text-caption font-bold text-white">Approve…</button>
                    <button type="button" onClick={() => setDeciding({ id: b.id, approve: false })} className="h-8 rounded-full border border-line-strong px-3 text-caption font-bold">Reject…</button>
                  </span>
                )
              ) : b.status === "pending_approval" ? <span className="text-muted">waiting for a second admin</span> : null}</td>
            </tr>
          ))}</tbody></table></div>
      ) : null}
      {note}
    </section>
  );
}

function Messages({ scope }: { scope: string }) {
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();
  const { city: scopeCity } = parseScope(scope);
  // R18: who gets it comes only from "To": a city the admin looks after (from Markets), or a bulk refund's customers.
  const cities = (markets ?? []).flatMap((c) => c.regions.flatMap((r) => r.cities))
    .filter((c) => can(me, "customers.message", c.code));
  const templates = useQuery({ queryKey: ["incidents", "templates"], queryFn: async () => (await adminApi.get<Template[]>("/user/incidents/messages/templates")).data,
    enabled: cities.length > 0 });
  const refunds = useQuery({ queryKey: ["incidents", "refunds"], queryFn: async () => (await adminApi.get<BulkRefund[]>("/user/incidents/refunds")).data });
  const done = (refunds.data ?? []).filter((b) => b.refunded > 0 && can(me, "customers.message", b.market_city));
  const [to, setTo] = useState("");
  const [template, setTemplate] = useState("area_paused");
  const [time, setTime] = useState("");
  const [days, setDays] = useState("1");
  const [preview, setPreview] = useState<MessagePreview | null>(null);
  const [confirming, setConfirming] = useState(false);
  const { busy, act, note } = useAct();
  const audience = to || (scopeCity && cities.some((c) => c.code === scopeCity) ? `city:${scopeCity}` : cities[0] ? `city:${cities[0].code}` : "");
  const isCity = audience.startsWith("city:");
  const t = (templates.data ?? []).find((x) => x.key === template);
  const usable = (templates.data ?? []).filter((x) => !isCity || !x.per_order);
  const params = t?.needs.includes("time") ? { time } : {};
  const body = isCity ? { city: audience.slice(5), days: Number(days) || 1, template, params } : { bulk_refund_id: audience, template, params };
  if (!cities.length) {
    return (
      <section aria-label="Message customers" className="space-y-2 rounded-2xl bg-white p-6">
        <h2 className="m-0 text-h2">Message customers</h2>
        <p className="m-0 text-small text-muted">Your role doesn&apos;t include messaging customers.</p>
      </section>
    );
  }
  return (
    <section aria-label="Message customers" className="space-y-3 rounded-2xl bg-white p-6">
      <h2 className="m-0 text-h2">Message customers</h2>
      <p className="m-0 text-small text-muted">One of the incident plan&apos;s messages, by push and email, each customer in their own language. Outside production it only reaches test accounts.</p>
      <div className="flex flex-wrap items-end gap-3 text-small">
        <label className="font-bold">To
          <select aria-label="To" value={audience} onChange={(e) => {
            setTo(e.target.value); setPreview(null);
            if (e.target.value.startsWith("city:") && t?.per_order) setTemplate("area_paused");
          }} className={field}>
            {cities.map((c) => <option key={c.code} value={`city:${c.code}`}>Customers who ordered in {c.name}</option>)}
            {done.map((b) => <option key={b.id} value={b.id}>Customers of the bulk refund of {when(b.created_at)} ({b.count} orders, {b.market_city})</option>)}
          </select>
        </label>
        {isCity ? (
          <label className="font-bold">In the last
            <select aria-label="In the last" value={days} onChange={(e) => { setDays(e.target.value); setPreview(null); }} className={field}>
              {["1", "7", "30"].map((d) => <option key={d} value={d}>{d === "1" ? "day" : `${d} days`}</option>)}
            </select>
          </label>
        ) : null}
        <label className="font-bold">Message
          <select aria-label="Message" value={template} onChange={(e) => { setTemplate(e.target.value); setPreview(null); }} className={field}>
            {usable.map((x) => <option key={x.key} value={x.key}>{x.title}</option>)}
          </select>
        </label>
        {t?.needs.includes("time") ? (
          <label className="font-bold">Arrives by
            <input aria-label="Arrives by" value={time} onChange={(e) => { setTime(e.target.value); setPreview(null); }} placeholder="e.g. 8:30 pm" className={`${field} w-40`} />
          </label>
        ) : null}
        <button type="button" disabled={busy || !audience} className={secondary}
          onClick={() => void act(async () => setPreview((await adminApi.post<MessagePreview>("/user/incidents/messages/preview", body)).data), "Preview ready.")}>Preview</button>
      </div>
      {preview ? (
        <div className="space-y-2 rounded-xl border border-line p-4 text-small" data-testid="message-preview">
          <p className="m-0"><b>{preview.recipients} customer{preview.recipients === 1 ? "" : "s"}</b>{preview.only_test_accounts ? ` · test accounts only (${preview.skipped} other${preview.skipped === 1 ? "" : "s"} left out outside production)` : ""}</p>
          <div className="rounded-lg bg-porcelain p-3"><b>{preview.sample.title}</b><br />{preview.sample.body}</div>
          <p className="m-0 text-muted">Shown here in English; each customer gets it in their own language.</p>
          {preview.recipients && !confirming ? <button type="button" onClick={() => setConfirming(true)} className={danger}>Send to {preview.recipients}…</button> : null}
          {confirming ? (
            <Confirm testId="confirm-send-message" title={`Send “${preview.sample.title}” to ${preview.recipients} customer${preview.recipients === 1 ? "" : "s"} by push and email?`}
              yes="Yes, send" busy={busy} onCancel={() => setConfirming(false)}
              onYes={(reason) => void act(() => adminApi.post("/user/incidents/messages", { ...body, reason, confirm: true }), "Sending now.")
                .then((ok) => { if (ok) { setConfirming(false); setPreview(null); } })} />
          ) : null}
        </div>
      ) : null}
      {note}
    </section>
  );
}

function Log() {
  const log = useQuery({ queryKey: ["incidents", "log"], queryFn: async () => (await adminApi.get<LogEntry[]>("/user/incidents/log")).data });
  return (
    <section aria-label="Incident log" className="space-y-2 rounded-2xl bg-white p-6">
      <h2 className="m-0 text-h2">Log</h2>
      {(log.data ?? []).length ? (
        <ul className="space-y-1 text-small" data-testid="incident-log">
          {(log.data ?? []).map((e, i) => (
            <li key={i}><b>{when(e.at)}</b> · {ACTIONS[e.action] ?? e.action} · {e.scope} · {e.by}
              {e.after && typeof e.after.reason === "string" ? ` · “${e.after.reason}”` : ""}</li>
          ))}
        </ul>
      ) : <p className="m-0 text-small text-muted">Nothing yet.</p>}
    </section>
  );
}

function IncidentsPage() {
  const scope = useScope();
  const { country, region, city } = parseScope(scope);
  return (
    <ConsoleShell section="Incidents" country={country} region={region} city={city} scopeHref={(s) => `/incidents?scope=${s}`}>
      <div>
        <h1 className="m-0 text-h1">Incidents</h1>
        <p className="m-0 mt-1 text-small text-muted">When something breaks: stop new damage, refund, tell customers. The plan: docs/launch/incident-plan.md.</p>
      </div>
      <OrderingPauses scope={scope} />
      <Kitchens scope={scope} />
      <Refunds scope={scope} />
      <Messages scope={scope} />
      <Log />
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><IncidentsPage /></Suspense>;
}
