"use client";
// CustomerTracking.html on the web: when it arrives, the four steps, who's
// bringing it, the PIN for the door, and the route, live from /ws/track.
import { unwrap, type CoreSchemas } from "@bhojango/api-client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api, useHydrated, useSession, wsUrl } from "@/lib/client";
import { FairBill, StatusPill } from "@bhojango/ui";

type Order = CoreSchemas["OrderResponse"];
type Pt = [number, number];
interface Eta { to_pickup_minutes: number; to_customer_minutes: number; arrives_at: string }
interface Live { status: string | null; pickup: Pt | null; dropoff: Pt | null; rider: Pt | null; trail: Pt[]; eta: Eta | null; searching: boolean }

const STEPS = [
  { label: "Placed", states: ["placed", "accepted"] },
  { label: "Cooked", states: ["preparing", "almost_ready", "ready"] },
  { label: "Picked up", states: ["picked_up"] },
  { label: "Home", states: ["delivered"] },
];

function time(iso?: string | null) {
  return iso ? new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase() : "--:--";
}

export default function Tracking() {
  const { id } = useParams<{ id: string }>();
  const ready = useHydrated();
  const user = useSession((s) => s.user);
  const [order, setOrder] = useState<Order | null>(null);
  const [bill, setBill] = useState<{ lines: unknown[]; currency: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<Live>({ status: null, pickup: null, dropoff: null, rider: null, trail: [], eta: null, searching: false });

  useEffect(() => {
    if (!ready || !user) return;
    let alive = true;
    const load = () => api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
      .then((r) => alive && setOrder(unwrap(r))).catch(() => alive && setError("We couldn't find this order."));
    void load();
    api.core.GET("/api/v1/pricing/orders/{order_id}/bill", { params: { path: { order_id: id } } })
      .then((r) => alive && setBill(unwrap(r) as never)).catch(() => undefined);
    const ws = new WebSocket(wsUrl(`/ws/track/${id}`));
    ws.onmessage = (e) => {
      const m = JSON.parse(String(e.data)) as { type: string; payload: Record<string, unknown> };
      const p = m.payload;
      if (m.type === "rider_assigned" || m.type === "status_change") void load();
      setLive((s) => {
        switch (m.type) {
          case "connected": {
            const loc = p.location as { lat: number; lng: number } | null;
            return { ...s, status: (p.status as string) ?? s.status, pickup: (p.pickup as Pt) ?? null, dropoff: (p.dropoff as Pt) ?? null,
              rider: loc ? [loc.lat, loc.lng] : null, eta: (p.eta as Eta) ?? null,
              trail: ((p.trail as [number, number, string][]) ?? []).map((t) => [t[0], t[1]] as Pt) };
          }
          case "searching_rider": return { ...s, searching: true };
          case "rider_assigned": return { ...s, searching: false, eta: (p.eta as Eta) ?? s.eta };
          case "location_update": {
            const pt: Pt = [Number(p.lat), Number(p.lng)];
            return { ...s, rider: pt, trail: [...s.trail, pt].slice(-200), eta: (p.eta as Eta) ?? s.eta };
          }
          case "status_change": return { ...s, status: (p.status as string) ?? s.status };
          default: return s;
        }
      });
    };
    const poll = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(poll);
      ws.close();
    };
  }, [id, ready, user]);

  if (ready && !user) return <Gate />;
  if (error) return <div className="mx-auto max-w-md px-5 py-20 text-center text-muted">{error}</div>;
  if (!order) return <div className="mx-auto max-w-content px-5 py-14 text-muted">Loading your order…</div>;

  const status = order.status === "delivered" || order.status === "cancelled" || !live.status ? order.status : live.status;
  const step = Math.max(0, STEPS.findIndex((s) => s.states.includes(status)));
  const progress = status === "delivered" ? 1 : [0.12, 0.42, 0.78, 1][step] ?? 0.12;
  const rider = (order.rider as { first_name?: string } | null)?.first_name;
  const headline = status === "delivered" ? "Delivered. Enjoy your meal." : status === "cancelled" ? "This order was cancelled"
    : status === "picked_up" ? `${rider ?? "Your rider"} is on the way` : rider ? `${rider} is heading to the kitchen`
    : status === "placed" ? `${order.restaurant_name} has your order` : `${order.restaurant_name} is cooking`;
  const stamp = (state: string) => (order.status_history as { status: string; at: string }[]).find((x) => x.status === state)?.at;

  return (
    <div className="mx-auto grid max-w-content gap-8 px-5 py-10 md:grid-cols-[1fr_400px] md:px-8">
      <div className="space-y-6">
        <RouteMap live={live} />
        <section className="space-y-5 rounded-sheet bg-white p-6" aria-label="Order status">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-semibold text-muted">{headline}</p>
              {status !== "cancelled" ? (
                <p className="font-display text-6xl font-semibold tracking-[-2px]" data-testid="eta">{time(live.eta?.arrives_at ?? order.estimated_delivery_time)}</p>
              ) : null}
            </div>
            <p className="text-right text-sm text-muted">{live.eta ? `${live.eta.to_customer_minutes} min` : ""}{live.searching ? <><br />finding a rider</> : null}</p>
          </div>
          <div aria-label={`Progress: ${STEPS[step]?.label}, ${step + 1} of 4`}>
            <div className="relative h-2 rounded-pill bg-line-divider">
              <div className="h-2 rounded-pill bg-peacock" style={{ width: `${progress * 100}%` }} />
              <div className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-pill border-[3px] border-white bg-kesar" style={{ left: `${progress * 100}%` }} />
            </div>
            <div className="mt-3 flex justify-between text-xs font-semibold text-muted">
              {STEPS.map((s, i) => (
                <span key={s.label} className={i === step ? "font-extrabold text-kohl" : ""}>
                  {s.label} {i === 0 ? time(stamp("placed")) : i === 1 && stamp("preparing") ? time(stamp("preparing")) : i === 2 && stamp("picked_up") ? time(stamp("picked_up")) : ""}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill status={status} />
            <span className="text-sm text-muted">{order.restaurant_name}{rider ? ` · ${rider} is your rider` : ""}</span>
          </div>
          {order.pin && status !== "delivered" && status !== "cancelled" ? (
            <div className="flex items-center justify-between rounded-card bg-peacock-mist px-5 py-4">
              <span className="text-sm font-semibold text-muted">Give your rider this PIN at the door</span>
              <span className="text-2xl font-extrabold tracking-[0.4em]" data-testid="delivery-pin">{order.pin}</span>
            </div>
          ) : null}
        </section>
      </div>
      <aside className="space-y-4">
        <Messages orderId={id} />
        {bill ? <FairBill lines={bill.lines as never} currency={bill.currency} totalLabel="You paid" /> : null}
        {status === "delivered" ? (
          <Link href={`/orders/${id}/report`} className="block rounded-card bg-white p-5 font-bold hover:text-peacock">Something wrong with this order? Report a problem →</Link>
        ) : (
          <Link href="/help" className="block rounded-card bg-white p-5 font-bold hover:text-peacock">Something wrong with this order? Get help →</Link>
        )}
      </aside>
    </div>
  );
}

type Chat = CoreSchemas["QuickMessagesOut"];
type ChatMessage = CoreSchemas["QuickMessage"];

async function fetchChat(orderId: string): Promise<Chat | null> {
  try {
    return unwrap(await api.core.GET("/api/v1/orders/{order_id}/messages", { params: { path: { order_id: orderId } } }));
  } catch {
    return null;
  }
}

/** Quick messages with the rider while the order is on its way (B2). No phone
 *  numbers; hidden once the order is delivered. */
function Messages({ orderId }: { orderId: string }) {
  const [chat, setChat] = useState<Chat | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef(new Set<string>());
  useEffect(() => {
    let alive = true;
    const refresh = () => fetchChat(orderId).then((c) => {
      if (!alive || !c) return;
      c.messages.forEach((m) => seen.current.add(m.id));
      setChat(c);
    });
    void refresh();
    const ws = new WebSocket(wsUrl(`/ws/track/${orderId}`));
    ws.onmessage = (e) => {
      const m = JSON.parse(String(e.data)) as { type: string; payload: { id: string; sender_role: string; text: string; at: string } };
      if (m.type === "status_change" || m.type === "rider_assigned") void refresh();
      if (m.type !== "chat_message" || seen.current.has(m.payload.id)) return;
      seen.current.add(m.payload.id);
      setChat((c) => c && { ...c, messages: [...c.messages, { ...m.payload, mine: m.payload.sender_role === c.me } as ChatMessage] });
    };
    const poll = setInterval(refresh, 20000);
    return () => {
      alive = false;
      clearInterval(poll);
      ws.close();
    };
  }, [orderId]);

  async function send(body: { preset: string } | { text: string }) {
    setBusy(true);
    setError(null);
    try {
      const m = unwrap(await api.core.POST("/api/v1/orders/{order_id}/messages", { params: { path: { order_id: orderId } }, body }));
      if (!seen.current.has(m.id)) {
        seen.current.add(m.id);
        setChat((c) => c && { ...c, messages: [...c.messages, m] });
      }
      if ("text" in body) setText("");
    } catch {
      setError("Couldn't send. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!chat?.open) return null;
  return (
    <section aria-label={`Messages with ${chat.other_name}`} className="space-y-3 rounded-card bg-white p-5">
      <div>
        <h2 className="font-extrabold">Message {chat.other_name}</h2>
        <p className="text-sm text-muted">Your number stays private. Messages close once the order is delivered.</p>
      </div>
      <ol className="flex max-h-64 flex-col gap-2 overflow-y-auto" aria-live="polite">
        {chat.messages.length === 0 ? <li className="text-sm text-muted">No messages yet.</li> : chat.messages.map((m) => (
          <li key={m.id} className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm font-semibold ${m.mine ? "self-end bg-peacock text-white" : "self-start bg-porcelain"}`}>
            <span className="sr-only">{m.mine ? "You: " : `${chat.other_name}: `}</span>{m.text}
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        {chat.presets.map((p) => (
          <button key={p.key} type="button" disabled={busy} onClick={() => void send({ preset: p.key })}
            className="rounded-pill bg-peacock-mist px-3 py-2 text-sm font-bold text-peacock-deep hover:bg-peacock-tint disabled:opacity-50">{p.text}</button>
        ))}
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (text.trim()) void send({ text: text.trim() }); }}>
        <label className="sr-only" htmlFor="chat-text">Write a short message</label>
        <input id="chat-text" value={text} maxLength={140} onChange={(e) => setText(e.target.value)} placeholder="Write a short message"
          className="h-11 flex-1 rounded-pill border-[1.5px] border-line-strong px-4" />
        <button type="submit" disabled={busy || !text.trim()} className="h-11 rounded-pill bg-peacock px-5 font-extrabold text-white disabled:opacity-50">Send</button>
      </form>
      {error ? <p role="alert" className="text-sm font-semibold text-chili">{error}</p> : null}
    </section>
  );
}

function Gate() {
  return (
    <div className="mx-auto max-w-md px-5 py-20 text-center">
      <h1 className="font-display text-3xl font-semibold">Sign in to see your order</h1>
      <Link href="/sign-in?next=/orders" className="mt-6 inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white">Sign in</Link>
    </div>
  );
}

/** The route, drawn (no map provider key): kitchen, rider, home. */
function RouteMap({ live }: { live: Live }) {
  const W = 800, H = 320;
  const pts = [live.pickup, live.dropoff, live.rider, ...live.trail].filter(Boolean) as Pt[];
  if (!pts.length) return <div className="h-[320px] rounded-sheet bg-[#E9EEEE]" aria-hidden />;
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  const [a, b, c, d] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const span = Math.max(b - a, d - c, 0.005);
  const xy = (p: Pt) => [80 + ((p[1] - c) / span) * (W - 160), H - 40 - ((p[0] - a) / span) * (H - 80)] as const;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-sheet" role="img" aria-label="Map of your order's route">
      <rect width={W} height={H} fill="#E9EEEE" />
      {[80, 160, 240].map((y) => <path key={y} d={`M0 ${y} H${W}`} stroke="#DDE4E4" strokeWidth={10} />)}
      {[160, 400, 640].map((x) => <path key={x} d={`M${x} 0 V${H}`} stroke="#DDE4E4" strokeWidth={10} />)}
      {live.trail.length > 1 ? <polyline points={live.trail.map((p) => xy(p).join(",")).join(" ")} fill="none" stroke="#0B5D66" strokeWidth={4} strokeLinecap="round" /> : null}
      {live.pickup && live.dropoff ? <path d={`M${xy(live.pickup).join(" ")} L${xy(live.dropoff).join(" ")}`} stroke="#C9D3D4" strokeWidth={3} strokeDasharray="2 10" strokeLinecap="round" /> : null}
      {live.pickup ? <circle cx={xy(live.pickup)[0]} cy={xy(live.pickup)[1]} r={10} fill="#111418" /> : null}
      {live.dropoff ? <rect x={xy(live.dropoff)[0] - 10} y={xy(live.dropoff)[1] - 10} width={20} height={20} rx={5} fill="#D4932A" /> : null}
      {live.rider ? <circle cx={xy(live.rider)[0]} cy={xy(live.rider)[1]} r={11} fill="#0B5D66" stroke="#fff" strokeWidth={4} /> : null}
    </svg>
  );
}
