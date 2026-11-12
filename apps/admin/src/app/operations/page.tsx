"use client";
// Operations: live orders, what needs attention, the dispatch map (riders,
// orders waiting for a rider, SOS, hand an order to a rider) and the support
// console (find an order, see its timeline, refund by item: AdminSupport.html).
import { useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import {
  apiMessage, clock, money, REFUND_REASONS, TICKET_TOPIC, useAlerts, useDispatch, useOpsOrders, useScope, useTickets, type OpsOrder,
  type OpsTicket, type OrderDetail, type Refund,
} from "@/lib/ops";

const DispatchMap = dynamic(() => import("@/components/ops/DispatchMap").then((m) => m.DispatchMap), { ssr: false });

const TABS = [
  { key: "live", label: "Live orders" },
  { key: "attention", label: "Needs attention" },
  { key: "dispatch", label: "Dispatch map" },
  { key: "support", label: "Support" },
] as const;

const STATUS: Record<string, string> = {
  placed: "Waiting for kitchen", accepted: "Accepted", preparing: "Cooking", almost_ready: "Almost ready", ready: "Ready",
  picked_up: "On the way", delivered: "Delivered", cancelled: "Cancelled", pending_payment: "Not paid",
};

/** Alerts firing now (P23): payment failures, orders without a rider, error spikes. */
function Alerts({ scope }: { scope: string }) {
  const { data } = useAlerts(scope);
  if (!data?.length) return null;
  return (
    <section aria-label="Alerts" className="space-y-2 rounded-2xl bg-danger-tint p-4 text-danger-ink">
      <h2 className="m-0 text-base font-extrabold">Alerts · {data.length} firing</h2>
      {data.map((a) => (
        <div key={`${a.name}-${a.city ?? "all"}`} className="text-sm">
          <b>{a.summary}</b> <span className="opacity-80">· since {clock(a.starts_at)}{a.description ? ` · ${a.description}` : ""}</span>
        </div>
      ))}
    </section>
  );
}

function Flags({ o }: { o: OpsOrder }) {
  return (
    <span className="flex flex-wrap gap-1">
      {o.flags.includes("late") ? <span className="rounded-md bg-danger-tint px-1.5 py-0.5 text-[11px] font-bold text-danger-ink">{o.minutes_late} min late</span> : null}
      {o.flags.includes("waiting_for_rider") ? <span className="rounded-md bg-kesar-tint px-1.5 py-0.5 text-[11px] font-bold text-kesar-ink">no rider · {o.waiting_for_rider_min} min</span> : null}
      {o.flags.includes("kitchen_not_answering") ? <span className="rounded-md bg-kesar-tint px-1.5 py-0.5 text-[11px] font-bold text-kesar-ink">kitchen not answering</span> : null}
    </span>
  );
}

function OrdersTable({ orders, onOpen }: { orders: OpsOrder[]; onOpen: (id: string) => void }) {
  if (!orders.length) return <p className="rounded-2xl bg-white p-6 text-muted">No orders here right now.</p>;
  return (
    <div className="overflow-x-auto rounded-2xl bg-white">
      <table className="w-full text-left text-sm tabular-nums">
        <thead className="text-[12px] uppercase tracking-wide text-muted"><tr>
          <th className="px-4 py-3">Order</th><th>Kitchen</th><th>Customer</th><th>Status</th><th>Rider</th><th>Placed</th><th>Due</th><th>Total</th><th />
        </tr></thead>
        <tbody className="divide-y divide-line">
          {orders.map((o) => (
            <tr key={o.id} className="hover:bg-porcelain">
              <td className="px-4 py-3 font-extrabold">{o.code}</td><td>{o.restaurant_name}</td><td>{o.customer}</td>
              <td><span className="font-semibold">{STATUS[o.status] ?? o.status}</span> <Flags o={o} /></td>
              <td>{o.rider ?? <span className="text-muted">—</span>}</td><td>{clock(o.placed_at)}</td><td>{clock(o.estimated_delivery_time)}</td>
              <td>{money(o.total, o.currency, 2)}</td>
              <td className="pr-4"><button type="button" onClick={() => onOpen(o.id)} className="h-8 rounded-full border border-line-strong px-3 text-xs font-bold hover:border-peacock">Open</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Dispatch({ scope, city }: { scope: string; city: string | null }) {
  const { data: me } = useAdminMe();
  const waitingQ = useOpsOrders(scope, "attention");
  const map = useDispatch(city);
  const [msg, setMsg] = useState<string | null>(null);
  const waiting = (waitingQ.data ?? []).filter((o) => o.flags.includes("waiting_for_rider"));
  const free = (map.data?.riders ?? []).filter((r) => r.status === "available");
  if (!city) return <p className="rounded-2xl bg-white p-6 text-muted">Pick a city above to see its riders on the map.</p>;
  async function assign(orderId: string, riderId: string) {
    setMsg(null);
    try {
      await adminApi.post("/realtime/delivery/assign", { order_id: orderId, driver_id: riderId });
      setMsg("Assigned. The rider sees it at once.");
      await Promise.all([waitingQ.refetch(), map.refetch()]);
    } catch (e) {
      setMsg(apiMessage(e));
    }
  }
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-3">
        {map.data ? (
          <DispatchMap centre={map.data.centre} riders={map.data.riders} sos={map.data.sos}
            waiting={waiting.filter((o) => o.pickup).map((o) => ({ id: o.id, code: o.code, lat: o.pickup![0], lng: o.pickup![1], label: o.restaurant_name }))} />
        ) : <div className="h-[460px] rounded-2xl bg-white p-6 text-muted">{map.error ? "Can't load the map for this city." : "Loading the map…"}</div>}
        <p className="text-sm text-muted">
          <span className="font-bold text-peacock">●</span> free · <span className="font-bold text-kesar">●</span> offered · <span className="font-bold">●</span> on a delivery · <span className="font-bold text-kesar">■</span> waiting for a rider · <span className="font-bold text-chili">○</span> SOS
          {map.data ? ` · ${map.data.riders.length} riders online` : ""}
        </p>
      </div>
      <aside className="space-y-4">
        {(map.data?.sos.length ?? 0) > 0 ? (
          <section className="rounded-2xl bg-danger-tint p-4 text-danger-ink" aria-label="SOS">
            <h2 className="m-0 mb-2 text-base font-extrabold">SOS · call the rider now</h2>
            {map.data!.sos.map((a) => <p key={a.id} className="text-sm">Rider {a.rider_id.slice(0, 4)} · {clock(a.at)}{a.order_id ? ` · on order #${a.order_id.replace(/-/g, "").slice(0, 6).toUpperCase()}` : ""}{a.note ? ` · “${a.note}”` : ""}</p>)}
          </section>
        ) : null}
        <section className="rounded-2xl bg-white p-4" aria-label="Waiting for a rider">
          <h2 className="m-0 mb-2 text-base font-extrabold">Waiting for a rider · {waiting.length}</h2>
          {waiting.length === 0 ? <p className="text-sm text-muted">Every ready order has a rider.</p> : null}
          {waiting.map((o) => (
            <div key={o.id} className="space-y-2 border-t border-line py-3">
              <div className="text-sm"><b>{o.code}</b> · {o.restaurant_name} · {o.waiting_for_rider_min} min</div>
              {can(me, "dispatch.edit", city) ? (
                <select aria-label={`Give ${o.code} to a rider`} defaultValue="" onChange={(e) => e.target.value && void assign(o.id, e.target.value)}
                  className="h-9 w-full rounded-lg border border-line px-2 text-sm">
                  <option value="">{free.length ? "Give it to a free rider…" : "No free rider online"}</option>
                  {free.map((r) => <option key={r.rider_id} value={r.rider_id}>Rider {r.rider_id.slice(0, 4)} · {r.km} km from the centre</option>)}
                </select>
              ) : null}
            </div>
          ))}
          {msg ? <p className="text-sm font-semibold text-peacock">{msg}</p> : null}
        </section>
      </aside>
    </div>
  );
}

function waited(iso: string): string {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? `${min} min` : min < 1440 ? `${Math.floor(min / 60)} h ${min % 60} min` : `${Math.floor(min / 1440)} d`;
}

function ticketTitle(t: OpsTicket): string {
  return t.kind === "callback" ? `Call back · ${t.restaurant_name ?? t.requester_name}` : `Problem · ${t.order_code ?? ""} · ${t.requester_name}`;
}

function Support({ scope, openId, setOpenId }: { scope: string; openId: string | null; setOpenId: (id: string | null) => void }) {
  const [q, setQ] = useState("");
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [state, setState] = useState<"open" | "resolved">("open");
  const found = useOpsOrders(scope, "search", q.trim());
  const queue = useOpsOrders(scope, "attention");
  const tickets = useTickets(scope, state);
  const ticket = tickets.data?.find((t) => t.id === ticketId) ?? null;
  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <aside className="space-y-3">
        <section className="rounded-2xl bg-white p-2" aria-label="Tickets">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-sm font-extrabold">{state === "open" ? "Open tickets" : "Resolved tickets"} · {tickets.data?.length ?? 0}</span>
            <button type="button" onClick={() => { setState(state === "open" ? "resolved" : "open"); setTicketId(null); }}
              className="text-xs font-bold text-peacock">{state === "open" ? "Show resolved" : "Show open"}</button>
          </div>
          {tickets.data?.length === 0 ? <p className="px-3 pb-3 text-sm text-muted">{state === "open" ? "No one is waiting on us." : "Nothing resolved yet."}</p> : null}
          {tickets.data?.map((t) => (
            <button key={t.id} type="button" onClick={() => { setTicketId(t.id); setOpenId(null); }}
              className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${ticketId === t.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
              <div className="flex justify-between gap-2"><b>{ticketTitle(t)}</b><span className="shrink-0 text-muted">{state === "open" ? waited(t.created_at) : clock(t.resolved_at)}</span></div>
              <div className="text-muted">About {TICKET_TOPIC[t.topic] ?? t.topic}{t.note ? ` · “${t.note}”` : ""}</div>
            </button>
          ))}
        </section>
        <input aria-label="Find an order" placeholder="Order code (#A9D1C2) or customer's phone" value={q} onChange={(e) => setQ(e.target.value)}
          className="h-11 w-full rounded-full border border-line-strong bg-white px-4 text-sm" />
        <section className="rounded-2xl bg-white p-2" aria-label="Queue">
          <div className="px-3 py-2 text-sm font-extrabold">{q.trim().length >= 3 ? `Found · ${found.data?.length ?? 0}` : `Needs attention · ${queue.data?.length ?? 0}`}</div>
          {(q.trim().length >= 3 ? found.data : queue.data)?.map((o) => (
            <button key={o.id} type="button" onClick={() => { setOpenId(o.id); setTicketId(null); }}
              className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${openId === o.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
              <div className="flex justify-between"><b>{o.customer} · {STATUS[o.status] ?? o.status}</b><span className="text-muted">{clock(o.placed_at)}</span></div>
              <div className="text-muted">{o.code} · {o.restaurant_name}</div>
              <Flags o={o} />
            </button>
          ))}
        </section>
      </aside>
      {ticket ? (
        <div className="space-y-4">
          <TicketCase t={ticket} onDone={() => { setTicketId(null); void tickets.refetch(); }} />
          {ticket.order_id ? <OrderCase id={ticket.order_id} /> : null}
        </div>
      ) : openId ? <OrderCase id={openId} /> : <div className="rounded-2xl bg-white p-6 text-muted">Pick a ticket, or an order to see its timeline and refund by item.</div>}
    </div>
  );
}

function TicketCase({ t, onDone }: { t: OpsTicket; onDone: () => void }) {
  const qc = useQueryClient();
  const { data: me } = useAdminMe();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const where = t.city ?? "*";
  const mayResolve = ["orders.edit", "customers.edit", "partners.edit"].some((p) => can(me, p, where));
  async function resolve() {
    setBusy(true);
    setMsg(null);
    try {
      await adminApi.post(`/user/ops/tickets/${t.id}/resolve`, { resolution: text.trim() });
      await qc.invalidateQueries({ queryKey: ["ops", "tickets"] });
      onDone();
    } catch (e) {
      setMsg(apiMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="space-y-4 rounded-2xl bg-white p-6" aria-label={ticketTitle(t)}>
      <div>
        <h2 className="m-0 font-display text-2xl font-semibold">{ticketTitle(t)}</h2>
        <p className="text-sm text-muted">{t.kind === "callback" ? "Asked for a call back" : "Reported a problem"} {clock(t.created_at)} · {t.status === "open" ? `waiting ${waited(t.created_at)}` : `resolved ${clock(t.resolved_at)}`}</p>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="font-bold">Who</dt><dd>{t.requester_name}{t.requester_role === "partner" && t.restaurant_name ? ` · ${t.restaurant_name}` : ""}</dd></div>
        <div><dt className="font-bold">Call</dt><dd>{t.requester_phone ? <a href={`tel:${t.requester_phone}`} className="font-extrabold text-peacock">{t.requester_phone}</a> : <span className="text-muted">No phone on the account</span>}</dd></div>
        <div><dt className="font-bold">About</dt><dd>{TICKET_TOPIC[t.topic] ?? t.topic}</dd></div>
        <div><dt className="font-bold">Their words</dt><dd>{t.note ? `“${t.note}”` : <span className="text-muted">No note</span>}</dd></div>
      </dl>
      {t.kind === "problem" ? <ProblemDetails t={t} /> : null}
      {t.status === "resolved" ? (
        <p className="rounded-xl bg-porcelain p-4 text-sm"><b>Resolved:</b> {t.resolution}</p>
      ) : mayResolve ? (
        <div className="space-y-2">
          <label className="block text-sm font-bold">What did you do?
            <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={500} rows={2}
              placeholder="e.g. Called Ravi; last week's payout covered 6 days, explained the cut-off"
              className="mt-1 block w-full rounded-lg border border-line p-2 font-normal" />
          </label>
          <button type="button" disabled={busy || text.trim().length < 3} onClick={resolve}
            className="h-11 rounded-full bg-peacock px-5 font-extrabold text-white disabled:opacity-40">{busy ? "Saving…" : "Mark resolved"}</button>
        </div>
      ) : <p className="text-sm text-muted">You can see this ticket; city ops or support resolve it.</p>}
      {msg ? <p role="alert" className="text-sm font-semibold text-chili">{msg}</p> : null}
    </section>
  );
}

/** What the customer reported (B5): over the automatic refund limit, so a person checks it. */
function ProblemDetails({ t }: { t: OpsTicket }) {
  const d = t.details as { items?: { name: string; quantity: number; amount: string }[]; amount?: string; currency?: string; photo_key?: string | null };
  const cur = d.currency ?? "INR";
  return (
    <div className="space-y-2 rounded-xl bg-porcelain p-4 text-sm" aria-label="What they reported">
      <ul className="space-y-1">{(d.items ?? []).map((i) => <li key={i.name}><b>{i.quantity} × {i.name}</b> · {money(Number(i.amount), cur, 2)}</li>)}</ul>
      <p>Comes to <b>{money(Number(d.amount ?? 0), cur, 2)}</b>, over the city&apos;s automatic refund limit, so it waits for you. Refund by item below if it checks out.</p>
      {d.photo_key ? (
        <button type="button" className="font-bold text-peacock" onClick={async () => {
          const r = await adminApi.get("/user/uploads/view", { params: { key: d.photo_key }, responseType: "blob" });
          window.open(URL.createObjectURL(r.data as Blob), "_blank", "noopener");
        }}>See their photo</button>
      ) : <p className="text-muted">No photo.</p>}
    </div>
  );
}

function OrderCase({ id }: { id: string }) {
  const qc = useQueryClient();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [pick, setPick] = useState<Record<string, number>>({});
  const [reason, setReason] = useState("missing_item");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    let live = true;
    Promise.all([adminApi.get<OrderDetail>(`/user/orders/${id}`), adminApi.get<Refund[]>(`/user/payments/orders/${id}/refunds`)])
      .then(([o, r]) => {
        if (!live) return;
        setOrder(o.data);
        setRefunds(r.data);
        setPick({});
        setMsg(null);
      }).catch((e) => live && setMsg({ ok: false, text: apiMessage(e) }));
    return () => {
      live = false;
    };
  }, [id]);
  if (!order) return <div className="rounded-2xl bg-white p-6 text-muted">{msg?.text ?? "Loading…"}</div>;
  const chosen = order.items.filter((i) => (pick[i.menu_item_id] ?? 0) > 0);
  const estimate = chosen.reduce((n, i) => n + (i.total / i.quantity) * (pick[i.menu_item_id] ?? 0), 0);
  const fault = REFUND_REASONS.find((r) => r.value === reason)?.fault;
  async function refund() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await adminApi.post<{ amount?: number; refund?: { amount: number } }>(`/user/payments/orders/${id}/refunds`, {
        items: chosen.map((i) => ({ menu_item_id: i.menu_item_id, quantity: pick[i.menu_item_id] })), reason, note: note || null,
      });
      const amount = (r.data.refund?.amount ?? r.data.amount ?? 0) / 100;
      setMsg({ ok: true, text: `Refunded ${money(amount, order!.currency, 2)} to the customer's original payment.` });
      setPick({});
      setRefunds((await adminApi.get<Refund[]>(`/user/payments/orders/${id}/refunds`)).data);
      await qc.invalidateQueries({ queryKey: ["ops"] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  const at = (s: string) => order.status_history.find((h) => h.status === s)?.at;
  const code = "#" + order.id.replace(/-/g, "").slice(0, 6).toUpperCase();
  return (
    <section className="space-y-4 rounded-2xl bg-white p-6" aria-label={`Order ${code}`}>
      <div>
        <h2 className="m-0 font-display text-2xl font-semibold">{STATUS[order.status] ?? order.status} · {code}</h2>
        <p className="text-sm text-muted">{order.restaurant_name} → {order.delivery_address.area ?? order.delivery_address.city} · {money(order.total, order.currency, 2)}{order.rider?.first_name ? ` · rider ${order.rider.first_name}` : ""}</p>
        {order.special_instructions ? <p className="mt-2 rounded-xl bg-kesar-tint p-3 text-sm text-kesar-ink">Note: {order.special_instructions}</p> : null}
      </div>
      <ol className="flex flex-wrap gap-2 text-sm" aria-label="Order timeline">
        {["placed", "accepted", "ready", "picked_up", "delivered", "cancelled"].filter((s) => at(s)).map((s) => (
          <li key={s} className="rounded-full bg-porcelain px-3 py-1"><b>{STATUS[s]}</b> {clock(at(s))}</li>
        ))}
      </ol>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-extrabold">Pick what to refund</legend>
        {order.items.map((i) => (
          <label key={i.menu_item_id} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2 text-sm">
            <input type="number" min={0} max={i.quantity} value={pick[i.menu_item_id] ?? 0} aria-label={`How many ${i.name} to refund`}
              onChange={(e) => setPick((p) => ({ ...p, [i.menu_item_id]: Math.max(0, Math.min(i.quantity, Number(e.target.value))) }))}
              className="h-9 w-16 rounded-lg border border-line px-2" />
            <span className="flex-1"><b>{i.name}</b>{i.options?.length ? <span className="text-muted"> · {i.options.join(", ")}</span> : null} <span className="text-muted">· ordered {i.quantity}</span></span>
            <span className="tabular-nums">{money(i.total / i.quantity, order.currency, 2)} each</span>
          </label>
        ))}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-bold">Reason
          <select value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal">
            {REFUND_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </label>
        <label className="text-sm font-bold">Note (on the kitchen&apos;s statement)
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal" />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-porcelain p-4 text-sm">
        <span className="flex-1">About <b>{money(estimate, order.currency, 2)}</b> plus its tax · charged to {fault === "kitchen" ? "the kitchen's payout" : "BhojanGo"} ({REFUND_REASONS.find((r) => r.value === reason)?.label.toLowerCase()})</span>
        <button type="button" disabled={!chosen.length || busy} onClick={refund}
          className="h-11 rounded-full bg-peacock px-5 font-extrabold text-white disabled:opacity-40">{busy ? "Refunding…" : "Refund to original payment"}</button>
      </div>
      {msg ? <p role="status" className={`text-sm font-semibold ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
      {refunds.length ? (
        <div className="text-sm"><b>Refunds on this order</b>
          <ul className="mt-1 space-y-1 text-muted">{refunds.map((r) => <li key={r.id}>{money(r.amount / 100, order.currency, 2)} · {r.reason ?? "refund"}{r.fault ? ` · ${r.fault}` : ""} · {r.status} · {clock(r.created_at)}</li>)}</ul>
        </div>
      ) : null}
    </section>
  );
}

function OperationsPage() {
  const scope = useScope();
  const params = useSearchParams();
  const router = useRouter();
  const tab = (params.get("tab") ?? "live") as (typeof TABS)[number]["key"];
  const { country, region, city } = parseScope(scope);
  const { data: markets } = useMarkets();
  const [openId, setOpenId] = useState<string | null>(params.get("order"));
  const live = useOpsOrders(scope, tab === "attention" ? "attention" : "live");
  const firstCity = city ?? markets?.find((c) => c.code === country)?.regions.flatMap((r) => r.cities).find((c) => c.status === "live" || c.status === "beta")?.code ?? null;
  const go = (t: string) => router.replace(`/operations?scope=${scope}&tab=${t}`);
  return (
    <ConsoleShell section="Operations" country={country} region={region} city={city} scopeHref={(s) => `/operations?scope=${s}&tab=${tab}`}>
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">Operations</h1>
        <nav aria-label="Operations" className="ml-auto flex rounded-full bg-white p-1">
          {TABS.map((t) => (
            <button key={t.key} type="button" onClick={() => go(t.key)} aria-current={tab === t.key ? "page" : undefined}
              className={`h-9 rounded-full px-4 text-sm ${tab === t.key ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>{t.label}</button>
          ))}
        </nav>
      </div>
      <Alerts scope={scope} />
      {tab === "live" || tab === "attention" ? (
        live.error ? <p className="text-chili">{apiMessage(live.error)}</p> :
          <OrdersTable orders={live.data ?? []} onOpen={(id) => { setOpenId(id); go("support"); }} />
      ) : null}
      {tab === "dispatch" ? (country === "ALL" && !city ? <p className="rounded-2xl bg-white p-6 text-muted">Pick a country and city above for the dispatch map.</p> : <Dispatch scope={scope} city={firstCity} />) : null}
      {tab === "support" ? <Support scope={scope} openId={openId} setOpenId={setOpenId} /> : null}
      <p className="text-xs text-muted">Live data refreshes every 15 seconds. <Link href={`/overview?scope=${scope}`} className="font-bold text-peacock">Overview</Link></p>
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><OperationsPage /></Suspense>;
}
