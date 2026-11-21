"use client";
// Operations: live orders, what needs attention, the dispatch map (delivery partners,
// orders waiting for one, SOS, hand an order to a delivery partner) and the support
// console (find an order, see its timeline, refund by item: AdminSupport.html).
import { formatPhone } from "@bhojango/i18n";
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
import { count } from "@/lib/count";

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
      <h2 className="m-0 text-label">Alerts · {data.length} firing</h2>
      {data.map((a) => (
        <div key={`${a.name}-${a.city ?? "all"}`} className="text-small">
          <b>{a.summary}</b> <span className="opacity-80">· since {clock(a.starts_at)}{a.description ? ` · ${a.description}` : ""}</span>
        </div>
      ))}
    </section>
  );
}

function Flags({ o, className = "" }: { o: OpsOrder; className?: string }) {
  if (!o.flags.length) return null;
  return (
    <span className={`flex flex-wrap gap-1 ${className}`}>
      {o.flags.includes("late") ? <span className="rounded-md bg-danger-tint px-1.5 py-0.5 text-caption text-danger-ink">{o.minutes_late} min late</span> : null}
      {o.flags.includes("waiting_for_rider") ? <span className="rounded-md bg-kesar-tint px-1.5 py-0.5 text-caption text-kesar-ink">no delivery partner · {o.waiting_for_rider_min} min</span> : null}
      {o.flags.includes("kitchen_not_answering") ? <span className="rounded-md bg-kesar-tint px-1.5 py-0.5 text-caption text-kesar-ink">kitchen not answering</span> : null}
    </span>
  );
}

function OrdersTable({ orders, onOpen, attention }: { orders: OpsOrder[]; onOpen: (id: string) => void; attention: boolean }) {
  if (!orders.length) {
    return (
      <div className="space-y-1 rounded-2xl bg-white p-6">
        <p className="m-0 font-bold">{attention ? "Nothing needs attention right now." : "No live orders here right now."}</p>
        <p className="m-0 text-small text-muted">{attention ? "Late orders, orders without a delivery partner and kitchens not answering show here." : "Orders show here from the moment they are placed until they are delivered."}</p>
      </div>
    );
  }
  return (
    <div className="table-scroll rounded-2xl">
      <table className="table-stack w-full text-left text-small tabular-nums [--stack-inset:1rem]">
        <thead className="text-caption text-muted"><tr>
          <th className="px-4 py-3">Order</th><th>Kitchen</th><th>Customer</th><th>Status</th><th>Delivery partner</th><th>Placed</th><th>Due</th><th>Total</th><th><span className="sr-only">Open</span></th>
        </tr></thead>
        <tbody className="divide-y divide-line">
          {orders.map((o) => (
            <tr key={o.id} className="hover:bg-porcelain">
              <td className="stack-title px-4 py-3 font-bold">{o.code}</td><td data-label="Kitchen">{o.restaurant_name}</td><td data-label="Customer">{o.customer}</td>
              <td data-label="Status"><span className="flex flex-wrap justify-end gap-1 md:justify-start"><span className="font-semibold">{STATUS[o.status] ?? o.status}</span> <Flags o={o} className="basis-full justify-end md:justify-start" /></span></td>
              <td data-label="Delivery partner">{o.rider ?? <span className="text-muted">—</span>}</td><td data-label="Placed">{clock(o.placed_at)}</td><td data-label="Due">{clock(o.estimated_delivery_time)}</td>
              <td data-label="Total">{money(o.total, o.currency, 2)}</td>
              <td className="stack-actions pr-4"><button type="button" onClick={() => onOpen(o.id)} className="h-9 rounded-full border border-line-strong px-3 text-label hover:border-peacock">Open</button></td>
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
  if (!city) return <p className="rounded-2xl bg-white p-6 text-muted">Pick a city above to see its delivery partners on the map.</p>;
  async function assign(orderId: string, riderId: string) {
    setMsg(null);
    try {
      await adminApi.post("/realtime/delivery/assign", { order_id: orderId, driver_id: riderId });
      setMsg("Assigned. The delivery partner sees it at once.");
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
        <p className="text-small text-muted">
          <span className="font-bold text-peacock">●</span> free · <span className="font-bold text-kesar">●</span> offered · <span className="font-bold">●</span> on a delivery · <span className="font-bold text-kesar">■</span> waiting for a delivery partner · <span className="font-bold text-chili">○</span> SOS
          {map.data ? ` · ${count(map.data.riders.length, "delivery partner")} online` : ""}
        </p>
      </div>
      <aside className="space-y-4">
        {(map.data?.sos.length ?? 0) > 0 ? (
          <section className="rounded-2xl bg-danger-tint p-4 text-danger-ink" aria-label="SOS">
            <h2 className="m-0 mb-2 text-label">SOS · call the delivery partner now</h2>
            {map.data!.sos.map((a) => <p key={a.id} className="text-small">Delivery partner {a.rider_id.slice(0, 4)} · {clock(a.at)}{a.order_id ? ` · on order #${a.order_id.replace(/-/g, "").slice(0, 6).toUpperCase()}` : ""}{a.note ? ` · “${a.note}”` : ""}</p>)}
          </section>
        ) : null}
        <section className="rounded-2xl bg-white p-4" aria-label="Waiting for a delivery partner">
          <h2 className="m-0 mb-2 text-label">Waiting for a delivery partner · {waiting.length}</h2>
          {waiting.length === 0 ? <p className="text-small text-muted">Every ready order has a delivery partner.</p> : null}
          {waiting.map((o) => (
            <div key={o.id} className="space-y-2 border-t border-line py-3">
              <div className="text-small"><b>{o.code}</b> · {o.restaurant_name} · {o.waiting_for_rider_min} min</div>
              {can(me, "dispatch.edit", city) ? (
                <select aria-label={`Give ${o.code} to a delivery partner`} defaultValue="" onChange={(e) => e.target.value && void assign(o.id, e.target.value)}
                  className="h-9 w-full rounded-lg border border-line px-2 text-small">
                  <option value="">{free.length ? "Give it to a free delivery partner…" : "No free delivery partner online"}</option>
                  {free.map((r) => <option key={r.rider_id} value={r.rider_id}>Delivery partner {r.rider_id.slice(0, 4)} · {r.km} km from the centre</option>)}
                </select>
              ) : null}
            </div>
          ))}
          {msg ? <p className="text-label text-peacock">{msg}</p> : null}
        </section>
      </aside>
    </div>
  );
}

function waited(iso: string): string {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? `${min} min` : min < 1440 ? `${Math.floor(min / 60)} h ${min % 60} min` : `${Math.floor(min / 1440)} d`;
}

/** What the person did, by ticket kind (the rest: "Reported a problem"). */
const TICKET_WORDS = {
  callback: "Asked for a call back", message: "Wrote to support from Help", contact: "Used the Help contact form",
  chat_report: "Reported a chat message",
};

function ticketTitle(t: OpsTicket): string {
  if (t.kind === "callback") return `Call back · ${t.restaurant_name ?? t.requester_name}`;
  // From Help (F9): a signed-in customer's message, or the contact form (not signed in).
  if (t.kind === "message") return `Message · ${t.order_code ? `${t.order_code} · ` : ""}${t.requester_name}`;
  if (t.kind === "contact") return `Contact form · ${t.requester_name}`;
  if (t.kind === "chat_report") return `Chat report · ${t.order_code ? `${t.order_code} · ` : ""}${t.requester_name}`;
  return `Problem · ${t.order_code ?? ""} · ${t.requester_name}`;
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
            <span className="text-label">{state === "open" ? "Open tickets" : "Resolved tickets"} · {tickets.data?.length ?? 0}</span>
            <button type="button" onClick={() => { setState(state === "open" ? "resolved" : "open"); setTicketId(null); }}
              className="text-small text-peacock">{state === "open" ? "Show resolved" : "Show open"}</button>
          </div>
          {tickets.data?.length === 0 ? <p className="px-3 pb-3 text-small text-muted">{state === "open" ? "No one is waiting on us." : "Nothing resolved yet."}</p> : null}
          {tickets.data?.map((t) => (
            <button key={t.id} type="button" onClick={() => { setTicketId(t.id); setOpenId(null); }}
              className={`block w-full rounded-xl px-3 py-2.5 text-left text-small ${ticketId === t.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
              <div className="flex justify-between gap-2"><b>{ticketTitle(t)}</b><span className="shrink-0 text-muted">{state === "open" ? waited(t.created_at) : clock(t.resolved_at)}</span></div>
              <div className="text-muted">About {TICKET_TOPIC[t.topic] ?? t.topic}{t.note ? ` · “${t.note}”` : ""}</div>
            </button>
          ))}
        </section>
        <input aria-label="Find an order" placeholder="Order code (#A9D1C2) or customer's phone" value={q} onChange={(e) => setQ(e.target.value)}
          className="h-11 w-full rounded-full border border-line-strong bg-white px-4 text-small" />
        <section className="rounded-2xl bg-white p-2" aria-label="Queue">
          <div className="px-3 py-2 text-label">{q.trim().length >= 3 ? `Found · ${found.data?.length ?? 0}` : `Needs attention · ${queue.data?.length ?? 0}`}</div>
          {(q.trim().length >= 3 ? found.data : queue.data)?.map((o) => (
            <button key={o.id} type="button" onClick={() => { setOpenId(o.id); setTicketId(null); }}
              className={`block w-full rounded-xl px-3 py-2.5 text-left text-small ${openId === o.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
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
        <h2 className="m-0 text-h2">{ticketTitle(t)}</h2>
        <p className="text-small text-muted">{(TICKET_WORDS as Record<string, string>)[t.kind] ?? "Reported a problem"} {clock(t.created_at)} · {t.status === "open" ? `waiting ${waited(t.created_at)}` : `resolved ${clock(t.resolved_at)}`}</p>
      </div>
      <dl className="grid gap-3 text-small sm:grid-cols-2">
        <div><dt className="font-bold">Who</dt><dd>{t.requester_name}{t.requester_role === "partner" && t.restaurant_name ? ` · ${t.restaurant_name}` : ""}</dd></div>
        {t.kind === "contact" ? (
          <div><dt className="font-bold">Reply to</dt><dd>{typeof t.details.email === "string" ? <a href={`mailto:${t.details.email}`} className="font-bold text-peacock">{t.details.email}</a> : <span className="text-muted">No email</span>}</dd></div>
        ) : (
          <div><dt className="font-bold">Call</dt><dd>{t.requester_phone ? <a href={`tel:${t.requester_phone}`} className="font-bold text-peacock" data-testid="ticket-phone">{formatPhone(t.requester_phone)}</a> : <span className="text-muted">No phone on the account</span>}</dd></div>
        )}
        <div><dt className="font-bold">About</dt><dd>{TICKET_TOPIC[t.topic] ?? t.topic}</dd></div>
        <div><dt className="font-bold">Their words</dt><dd>{t.note ? `“${t.note}”` : <span className="text-muted">No note</span>}</dd></div>
      </dl>
      {t.kind === "problem" ? <ProblemDetails t={t} /> : null}
      {t.kind === "chat_report" ? <ChatReportDetails t={t} /> : null}
      {t.status === "resolved" ? (
        <p className="rounded-xl bg-porcelain p-4 text-small"><b>Resolved:</b> {t.resolution}</p>
      ) : mayResolve ? (
        <div className="space-y-2">
          <label className="block text-label">What did you do?
            <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={500} rows={2}
              placeholder="e.g. Called Ravi; last week's payout covered 6 days, explained the cut-off"
              className="mt-1 block w-full rounded-lg border border-line p-2 font-normal" />
          </label>
          <button type="button" disabled={busy || text.trim().length < 3} onClick={resolve}
            className="h-11 rounded-full bg-peacock px-5 font-bold text-white disabled:opacity-40">{busy ? "Saving…" : "Mark resolved"}</button>
        </div>
      ) : <p className="text-small text-muted">You can see this ticket; city ops or support resolve it.</p>}
      {msg ? <p role="alert" className="text-label text-chili">{msg}</p> : null}
    </section>
  );
}

/** A reported quick message (R19, Apple 1.2): who wrote it, what it said, and the conversation around it. */
function ChatReportDetails({ t }: { t: OpsTicket }) {
  const d = t.details as {
    reported_role?: string; reported_user_id?: string; message_id?: string; message_text?: string; reason_words?: string; blocked?: boolean;
    conversation?: { id?: string; role: string; text: string; at: string }[];
  };
  const who = (role?: string) => (role === "rider" ? "Delivery partner" : role === "customer" ? "Customer" : role ?? "Unknown");
  return (
    <div className="space-y-3 rounded-xl bg-porcelain p-4 text-small" aria-label="The reported message">
      <p><b>{who(t.requester_role)}</b> reported a message from the order&apos;s <b>{who(d.reported_role).toLowerCase()}</b>
        {d.reported_user_id ? <span className="text-muted"> (user {d.reported_user_id.slice(0, 8)})</span> : null}
        {" "}for <b>{d.reason_words ?? t.topic}</b>.{d.blocked ? " They also blocked them." : ""}</p>
      <blockquote className="border-l-4 border-chili pl-3">“{d.message_text ?? ""}”</blockquote>
      {d.conversation?.length ? (
        <ol className="space-y-1" aria-label="The conversation">
          {d.conversation.map((m, i) => (
            <li key={m.id ?? i} className={m.id && m.id === d.message_id ? "font-bold" : undefined}>
              <span className="text-muted">{clock(m.at)} · {who(m.role)}:</span> {m.text}
            </li>
          ))}
        </ol>
      ) : null}
      <p className="text-muted">Contact the reported person if needed, and note what you did. Messages are only open while an order is on its way.</p>
    </div>
  );
}

/** What the customer reported (B5): over the automatic refund limit, so a person checks it. */
function ProblemDetails({ t }: { t: OpsTicket }) {
  const d = t.details as { items?: { name: string; quantity: number; amount: string }[]; amount?: string; currency?: string; photo_key?: string | null };
  const cur = d.currency ?? "INR";
  return (
    <div className="space-y-2 rounded-xl bg-porcelain p-4 text-small tabular-nums" aria-label="What they reported">
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
        <h2 className="m-0 text-h2">{STATUS[order.status] ?? order.status} · {code}</h2>
        <p className="text-small text-muted">{order.restaurant_name} → {order.delivery_address.area ?? order.delivery_address.city} · {money(order.total, order.currency, 2)}{order.rider?.first_name ? ` · delivery partner ${order.rider.first_name}` : ""}</p>
        {order.special_instructions ? <p className="mt-2 rounded-xl bg-kesar-tint p-3 text-small text-kesar-ink">Note: {order.special_instructions}</p> : null}
      </div>
      <ol className="flex flex-wrap gap-2 text-small" aria-label="Order timeline">
        {["placed", "accepted", "ready", "picked_up", "delivered", "cancelled"].filter((s) => at(s)).map((s) => (
          <li key={s} className="rounded-full bg-porcelain px-3 py-1"><b>{STATUS[s]}</b> {clock(at(s))}</li>
        ))}
      </ol>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-label">Pick what to refund</legend>
        {order.items.map((i) => (
          <label key={i.menu_item_id} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2 text-small">
            <input type="number" min={0} max={i.quantity} value={pick[i.menu_item_id] ?? 0} aria-label={`How many ${i.name} to refund`}
              onChange={(e) => setPick((p) => ({ ...p, [i.menu_item_id]: Math.max(0, Math.min(i.quantity, Number(e.target.value))) }))}
              className="h-9 w-16 rounded-lg border border-line px-2" />
            <span className="flex-1"><b>{i.name}</b>{i.options?.length ? <span className="text-muted"> · {i.options.join(", ")}</span> : null} <span className="text-muted">· ordered {i.quantity}</span></span>
            <span className="tabular-nums">{money(i.total / i.quantity, order.currency, 2)} each</span>
          </label>
        ))}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-label">Reason
          <select value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal">
            {REFUND_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </label>
        <label className="text-label">Note (on the kitchen&apos;s statement)
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal" />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-porcelain p-4 text-small">
        <span className="flex-1 tabular-nums">About <b>{money(estimate, order.currency, 2)}</b> plus its tax · charged to {fault === "kitchen" ? "the kitchen's payout" : "BhojanGo"} ({REFUND_REASONS.find((r) => r.value === reason)?.label.toLowerCase()})</span>
        <button type="button" disabled={!chosen.length || busy} onClick={refund}
          className="h-11 rounded-full bg-peacock px-5 font-bold text-white disabled:opacity-40">{busy ? "Refunding…" : "Refund to original payment"}</button>
      </div>
      {msg ? <p role="status" className={`text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
      {refunds.length ? (
        <div className="text-small"><b>Refunds on this order</b>
          <ul className="mt-1 space-y-1 tabular-nums text-muted">{refunds.map((r) => <li key={r.id}>{money(r.amount / 100, order.currency, 2)} · {r.reason ?? "refund"}{r.fault ? ` · ${r.fault}` : ""} · {r.status} · {clock(r.created_at)}</li>)}</ul>
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
        <h1 className="m-0 text-h1">Operations</h1>
        <nav aria-label="Operations" className="ml-auto flex max-w-full overflow-x-auto rounded-full bg-white p-1">
          {TABS.map((t) => (
            <button key={t.key} type="button" onClick={() => go(t.key)} aria-current={tab === t.key ? "page" : undefined}
              className={`h-9 shrink-0 whitespace-nowrap rounded-full px-4 text-label ${tab === t.key ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>{t.label}</button>
          ))}
        </nav>
      </div>
      <Alerts scope={scope} />
      {tab === "live" || tab === "attention" ? (
        live.isLoading ? (
          <ul aria-busy="true" className="space-y-2 rounded-2xl bg-white p-4">{[0, 1, 2, 3].map((i) => <li key={i} className="h-10 animate-pulse rounded-lg bg-porcelain" />)}</ul>
        ) : live.isError ? (
          <div role="alert" className="space-y-2 rounded-2xl bg-white p-6">
            <p className="m-0 font-bold">The orders didn&apos;t load.</p>
            <p className="m-0 text-small text-muted">{apiMessage(live.error)}</p>
            <button type="button" onClick={() => void live.refetch()} className="h-10 rounded-full border border-line px-4 font-bold text-peacock">Try again</button>
          </div>
        ) : <OrdersTable orders={live.data ?? []} attention={tab === "attention"} onOpen={(id) => { setOpenId(id); go("support"); }} />
      ) : null}
      {tab === "dispatch" ? (country === "ALL" && !city ? <p className="rounded-2xl bg-white p-6 text-muted">Pick a country and city above for the dispatch map.</p> : <Dispatch scope={scope} city={firstCity} />) : null}
      {tab === "support" ? <Support scope={scope} openId={openId} setOpenId={setOpenId} /> : null}
      <p className="text-small text-muted">Live data refreshes every 15 seconds. <Link href={`/overview?scope=${scope}`} className="font-bold text-peacock">Overview</Link></p>
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><OperationsPage /></Suspense>;
}
