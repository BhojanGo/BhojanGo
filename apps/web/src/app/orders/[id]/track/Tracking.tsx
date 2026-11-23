"use client";
// WebTracking / MWebTracking: when it arrives, the PIN for the door, each step
// with its time, the rider (first name) and quick messages, the route, the
// items and the fair bill. Live from the realtime WebSocket (/ws/track), with a
// slow poll as a safety net. The map is MapLibre GL over OpenFreeMap's free
// tiles (LiveMap, loaded in the browser only).
import { ApiError, unwrap, type CoreSchemas } from "@bhojango/api-client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { FairBill } from "@/components/FairBill";
import { RateOrder } from "@/components/order/RateOrder";
import { api, liveSocket, useHydrated, useSession } from "@/lib/client";
import { riderFirstName } from "@/lib/contract";
import { useFormat, useLanguage, useT } from "@/lib/i18n";
import type { BillLine } from "@/lib/server";
import { slugify } from "../../../[country]/[city]/[kitchen]/data";

type Order = CoreSchemas["OrderResponse"];
type Pt = [number, number];
/** From realtime (dispatch.eta_for): minutes from the distance the rider still has to go, and that distance in the order's unit. */
interface Eta { to_pickup_minutes: number; to_customer_minutes: number; arrives_at: string; distance_left?: number; distance_unit?: string }
interface Live { status: string | null; pickup: Pt | null; dropoff: Pt | null; rider: Pt | null; trail: Pt[]; eta: Eta | null; etaAt: number | null; searching: boolean; slow: boolean; at: number | null }
interface Bill { lines: BillLine[]; currency: string; total?: string }

// WebGL map: browser only, and only on this page (it is a large script).
const LiveMap = dynamic(() => import("./LiveMap"), { ssr: false, loading: () => <div className="h-full w-full bg-[#E9EEEE]" /> });

// Where each status sits on the five steps (placed, cooking, picked up, on the way, delivered).
const STAGE: Record<string, number> = { pending_payment: 0, placed: 1, accepted: 1, preparing: 1, almost_ready: 1, ready: 2, picked_up: 3, delivered: 5 };

function kmBetween(a: Pt, b: Pt): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(rad(b[0] - a[0]) / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

export function Tracking({ id }: { id: string }) {
  const t = useT();
  const f = useFormat();
  const { country } = useLanguage();
  const router = useRouter();
  const ready = useHydrated();
  const user = useSession((s) => s.user);
  const [order, setOrder] = useState<Order | null>(null);
  const [kitchenPath, setKitchenPath] = useState<string | null>(null);
  const [bill, setBill] = useState<Bill | null>(null);
  const [missing, setMissing] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [live, setLive] = useState<Live>({ status: null, pickup: null, dropoff: null, rider: null, trail: [], eta: null, etaAt: null, searching: false, slow: false, at: null });

  useEffect(() => {
    if (ready && !user) router.replace(`/signin?next=${encodeURIComponent(`/orders/${id}/track`)}`);
  }, [ready, user, router, id]);

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    if (!ready || !user) return;
    let alive = true;
    const load = () =>
      api.core
        .GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
        .then((r) => alive && setOrder(unwrap(r)))
        .catch(() => alive && setMissing(true));
    const loadBill = () =>
      api.core
        .GET("/api/v1/pricing/orders/{order_id}/bill", { params: { path: { order_id: id } } })
        .then((r) => alive && setBill(unwrap(r) as unknown as Bill))
        .catch(() => undefined);
    void load();
    void loadBill();
    // Live updates; reopens with a fresh socket ticket when one expires (R22 S8, S10).
    const stopSocket = liveSocket(`/ws/track/${id}`, (e) => {
      const m = JSON.parse(String(e.data)) as { type: string; payload: Record<string, unknown> };
      const p = m.payload ?? {};
      if (m.type === "rider_assigned" || m.type === "status_change") void load();
      setLive((s) => {
        const at = Date.now();
        switch (m.type) {
          case "connected": {
            const loc = p.location as { lat: number; lng: number } | null;
            return {
              ...s, at,
              status: (p.status as string) ?? s.status,
              pickup: (p.pickup as Pt) ?? null,
              dropoff: (p.dropoff as Pt) ?? null,
              rider: loc ? [loc.lat, loc.lng] : null,
              eta: (p.eta as Eta) ?? null,
              etaAt: p.eta ? at : null,
              trail: ((p.trail as [number, number, string][]) ?? []).map((x) => [x[0], x[1]] as Pt),
              slow: !!p.searching_slow,
            };
          }
          case "searching_rider":
            return { ...s, at, searching: true };
          case "partner_search_slow": // R28: no partner after the city's minutes: said honestly, with the later time
            return p.eta ? { ...s, at, slow: true, eta: p.eta as Eta, etaAt: at } : { ...s, at, slow: true };
          case "rider_assigned":
            return p.eta ? { ...s, at, searching: false, slow: false, eta: p.eta as Eta, etaAt: at } : { ...s, at, searching: false, slow: false };
          case "location_update": {
            const pt: Pt = [Number(p.lat), Number(p.lng)];
            const fresh = p.eta ? { eta: p.eta as Eta, etaAt: at } : {};
            return { ...s, at, rider: pt, trail: [...s.trail, pt].slice(-200), ...fresh };
          }
          case "status_change":
            return { ...s, at, status: (p.status as string) ?? s.status };
          case "eta_update": // the ETA again after a status change (e.g. picked up), from the rider's last fix
            return p.eta ? { ...s, at, eta: p.eta as Eta, etaAt: at } : s;
          default:
            return s;
        }
      });
    });
    const poll = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(poll);
      stopSocket();
    };
  }, [id, ready, user]);

  // The kitchen's page (its path comes from the kitchen's own city and country).
  const restaurantId = order?.restaurant_id;
  useEffect(() => {
    if (!restaurantId) return;
    api.core
      .GET("/api/v1/restaurants/{restaurant_id}", { params: { path: { restaurant_id: restaurantId } } })
      .then((r) => {
        const k = unwrap(r);
        setKitchenPath(`/${k.country.toLowerCase()}/${slugify(k.city)}/${k.slug}`);
      })
      .catch(() => undefined);
  }, [restaurantId]);

  if (missing) {
    return (
      <div className="mx-auto max-w-md px-5 py-20 text-center">
        <h1 className="text-h1">{t("track.not_found")}</h1>
        <Link href="/account/orders" className="mt-6 inline-flex h-12 items-center rounded-full bg-[#0B5D66] px-6 font-bold text-white hover:text-white">{t("track.your_orders")}</Link>
      </div>
    );
  }
  if (!order) return <div className="container-page py-14 text-muted">{t("track.loading")}</div>;

  const status = order.status === "delivered" || order.status === "cancelled" || !live.status ? order.status : live.status;
  const cancelled = status === "cancelled";
  const delivered = status === "delivered";
  const stage = STAGE[status] ?? 1;
  const rider = riderFirstName(order);
  // R28: a partner who accepted is heading to the kitchen at once, named or not; never "Finding a
  // delivery partner" after someone took the order.
  const assigned = !!order.driver_id || !!(order as { rider?: unknown }).rider;
  const who = rider ?? (assigned ? t("track.your_rider") : null);
  const kitchen = order.restaurant_name;
  const stamp = (...states: string[]) => (order.status_history as { status: string; at: string }[] | undefined)?.find((x) => states.includes(x.status))?.at ?? null;
  const arrivesAt = live.eta?.arrives_at ?? order.estimated_delivery_time;
  const z = f.zone(order.time_zone); // the order's city clock, never the visitor's device
  // The live ETA comes from the distance left (each GPS fix); between fixes it counts down.
  // (`now` ticks once a second, so it can be just before etaAt: never count that as -1 minute)
  const minutes = live.eta
    ? Math.max(1, live.eta.to_customer_minutes - Math.floor(Math.max(0, now - (live.etaAt ?? now)) / 60000))
    : arrivesAt ? Math.max(1, Math.round((Date.parse(arrivesAt) - now) / 60000)) : null;
  // "N km left": the same distance the ETA was worked out from, in the order's unit
  // (straight line to the door only until the first ETA arrives).
  const unit = live.eta?.distance_unit ?? country?.distance_unit ?? "km";
  const left = live.eta?.distance_left != null
    ? live.eta.distance_left
    : live.rider && live.dropoff ? (unit === "mi" ? kmBetween(live.rider, live.dropoff) * 0.621371 : kmBetween(live.rider, live.dropoff)) : null;
  const leftText = left != null ? t(unit === "mi" ? "common.mi" : "common.km", { n: f.number(left) }) : null;
  const items = (order.items as { name?: string; quantity?: number }[]).filter((i) => i.name);
  const count = (order.items as { quantity?: number }[]).reduce((n, i) => n + Number(i.quantity ?? 1), 0);
  const ago = live.at ? Math.max(0, Math.round((now - live.at) / 1000)) : null;

  const sub = cancelled
    ? t("track.s_cancelled")
    : delivered
      ? t("track.s_delivered")
      : status === "pending_payment"
        ? t("track.s_payment")
        : status === "picked_up"
          ? t("track.s_picked_up", { rider: rider ?? t("track.your_rider") })
          : status === "ready" && order.fulfillment === "pickup"
            ? t("track.s_pickup_ready")  // R32: the customer collects it
          : status === "ready"
            ? who ? t("track.s_heading", { rider: who }) : t("track.s_finding")
            : who
              ? t("track.s_heading", { rider: who })
              : status === "placed"
              ? t("track.s_placed", { kitchen })
              : t("track.s_cooking", { kitchen });

  const steps = [
    { label: t("track.step_placed"), at: stamp("placed") },
    { label: t("track.step_cooking", { kitchen }), at: stamp("accepted", "preparing") },
    { label: t("track.step_picked", { rider: rider ?? t("track.your_rider") }), at: stamp("picked_up") },
    { label: leftText && stage === 3 ? t("track.step_on_way_left", { left: leftText }) : t("track.step_on_way"), at: null as string | null, now: stage === 3 },
    { label: t("track.step_delivered"), at: stamp("delivered"), eta: !delivered && arrivesAt ? arrivesAt : null },
  ];

  // The door PIN only once the rider has the food (R27; the API holds it back before that too).
  const pin = order.pin && status === "picked_up" ? order.pin : null;
  const bigEta = cancelled ? t("track.cancelled") : delivered ? t("track.delivered") : minutes != null ? t("track.minutes", { count: minutes }) : "—";

  return (
    <div className="container-page grid max-md:px-0 md:grid-cols-[minmax(0,1fr)_440px] md:gap-6 md:py-6">
      {/* the map */}
      {/* phone: the sheet below overlaps the map's last 32 px, so the map's controls and credits sit above it */}
      <div className="relative h-[400px] overflow-hidden md:h-[760px] md:rounded-[28px] [&_.maplibregl-ctrl-bottom-left]:bottom-8 [&_.maplibregl-ctrl-bottom-right]:bottom-8 md:[&_.maplibregl-ctrl-bottom-left]:bottom-0 md:[&_.maplibregl-ctrl-bottom-right]:bottom-0">
        <LiveMap
          pickup={live.pickup}
          dropoff={live.dropoff}
          rider={delivered || cancelled ? null : live.rider}
          trail={live.trail}
          heading={delivered || cancelled ? null : status === "picked_up" ? "home" : "kitchen"}
          labels={{ map: t("track.map"), kitchen: t("track.map_kitchen", { kitchen }), home: t("track.map_home"), rider: rider ? t("track.map_rider", { rider }) : t("track.your_rider"), failed: t("track.map_failed") }}
        />
        <Link href="/account/orders" aria-label={t("track.back")} className="absolute left-4 top-3 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-[0_2px_8px_rgba(17,20,24,0.18)] md:hidden">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#111418" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
        </Link>
        {ago != null && !delivered && !cancelled && (
          <span className="absolute left-5 top-5 z-10 hidden h-10 items-center rounded-full bg-white px-[14px] text-label shadow-[0_2px_8px_rgba(17,20,24,0.12)] md:flex" aria-live="off">
            {t("track.live_ago", { s: ago })}
          </span>
        )}
      </div>

      <div className="relative z-10 -mt-8 flex flex-col gap-4 rounded-t-[28px] bg-white px-5 pb-10 pt-6 md:mt-0 md:rounded-none md:p-0">
        {/* the page's title for screen readers: the big ETA below is what sighted people read first */}
        <h1 className="sr-only">{t("track.title")}</h1>
        {/* phone: the summary */}
        <section className="md:hidden" aria-label={t("track.status")}>
          <div className="flex items-start justify-between gap-4">
            <span>
              <span className="text-small text-muted">{cancelled || delivered ? t("track.order") : t("track.arriving")}</span>
              <b className="block text-h1 leading-none" data-testid="eta">{bigEta}</b>
            </span>
            {pin && (
              <span className="text-right">
                <span className="text-small text-muted">{t("track.pin_short")}</span>
                <b className="block text-h2 tracking-[0.3em]" data-testid="delivery-pin">{pin}</b>
              </span>
            )}
          </div>
          {!cancelled && (
            <div className="mt-4 grid grid-cols-5 gap-[6px]" role="progressbar" aria-valuemin={0} aria-valuemax={5} aria-valuenow={Math.min(stage, 5)} aria-label={t("track.progress")}>
              {steps.map((s, i) => (
                <span key={i} className={`h-[6px] rounded-full ${i < stage ? "bg-[#0B5D66]" : i === stage ? "bg-[#E8A93C]" : "bg-[#E2E7E8]"}`} />
              ))}
            </div>
          )}
          <p className="m-0 mt-3 text-body text-muted">{[sub, stage === 3 ? leftText && t("track.away", { left: leftText }) : null].filter(Boolean).join(" · ")}</p>
        </section>

        {/* desktop: the dark card */}
        <section className="hidden rounded-[28px] bg-[#111418] p-6 text-white md:block" aria-label={t("track.status")}>
          <span className="text-body text-[#C9D3D4]">{cancelled || delivered ? t("track.order") : t("track.arriving")}</span>
          <b className="block text-display leading-[1.05]" data-testid="eta">{bigEta}</b>
          <p className="m-0 mt-2 text-body text-[#E2E7E8]">{[!cancelled && !delivered && arrivesAt ? t("track.around", { time: z.time(arrivesAt) }) : null, sub].filter(Boolean).join(" · ")}</p>
          {pin && (
            <div className="mt-5 rounded-[18px] bg-[#1C3A3E] px-[14px] py-3">
              <span className="text-small text-[#C9D3D4]">{t("track.pin_long")}</span>
              <b className="block text-h1 tracking-[0.3em]" data-testid="delivery-pin">{pin}</b>
            </div>
          )}
          {live.slow && !assigned && <p data-testid="slow-search" className="m-0 mt-3 text-small text-[#FFB4A8]">{t("track.s_slow_search")}</p>}
          {live.searching && !live.slow && !assigned && <p className="m-0 mt-3 text-small text-[#C9D3D4]">{t("track.s_finding")}</p>}
        </section>

        {/* R32: a pickup order: where to collect it and, once it's ready, the code to show at the counter */}
        {order.fulfillment === "pickup" && !cancelled && (
          <section className="rounded-[24px] border-2 border-[#0B5D66] bg-[#EFF6F6] p-[22px]" data-testid="pickup-card" aria-label={t("checkout.pickup_at")}>
            <span className="text-small text-muted">{t("checkout.pickup_at")}</span>
            <b className="block text-label">{kitchen}</b>
            {order.pickup_address && (
              <span className="block text-small text-muted">{[order.pickup_address.street, order.pickup_address.city].filter(Boolean).join(", ")}</span>
            )}
            {order.pickup_address?.lat != null && order.pickup_address?.lng != null && (
              <a href={`https://www.google.com/maps/search/?api=1&query=${order.pickup_address.lat},${order.pickup_address.lng}`} target="_blank"
                rel="noopener noreferrer" className="mt-1 inline-block font-bold text-[#0B5D66]">{t("checkout.open_in_maps")}</a>
            )}
            {delivered ? (
              <p className="m-0 mt-3 text-label">{t("track.collected")}</p>
            ) : order.pickup_locked ? (
              <p className="m-0 mt-3 text-small text-[#B3261E]">{t("track.pickup_locked")}</p>
            ) : order.pickup_code ? (
              <div className="mt-4 rounded-[18px] bg-[#111418] px-[14px] py-3 text-white">
                <span className="text-small text-[#C9D3D4]">{t("track.pickup_code")} · {t("track.pickup_code_note")}</span>
                <b className="block text-h1 tracking-[0.3em]" data-testid="pickup-code">{order.pickup_code}</b>
              </div>
            ) : (
              <p className="m-0 mt-3 text-small text-muted">{t("track.pickup_waiting")}</p>
            )}
          </section>
        )}

        {/* the steps */}
        {!cancelled && (
          <section className="rounded-[24px] border border-[#E2E7E8] p-[22px]" aria-label={t("track.timeline")}>
            <ol className="m-0 flex list-none flex-col gap-4 p-0">
              {steps.map((s, i) => {
                const done = i < stage;
                const current = i === stage;
                return (
                  <li key={i} className="flex items-center gap-[14px]" aria-current={current ? "step" : undefined}>
                    <span aria-hidden="true" className={`h-[14px] w-[14px] shrink-0 rounded-full ${done ? "bg-[#0B5D66]" : current ? "bg-[#E8A93C] shadow-[0_0_0_5px_#F6E7CC]" : "bg-[#C9D3D4]"}`} />
                    <b className={`flex-grow text-body ${done || current ? "" : "text-muted"}`}>{s.label}</b>
                    <span className="text-small text-muted">
                      {s.at ? z.time(s.at) : current && s.now ? t("track.now") : s.eta ? `~${z.time(s.eta)}` : ""}
                    </span>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {/* R8: cancel while the API says the customer may; after it, the refund line */}
        {!cancelled && !delivered && (
          <CancelOrder order={order} onDone={(o) => setOrder(o)} onRefresh={() => {
            void api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } }).then((r) => setOrder(unwrap(r))).catch(() => undefined);
          }} />
        )}
        {cancelled && <RefundLine order={order} />}

        {/* after delivery: rate it */}
        {delivered && <RateOrder orderId={id} order={order} />}

        {/* the rider */}
        {rider && !cancelled && (
          <Messages orderId={id} rider={rider} />
        )}

        {/* the order */}
        <section className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[24px] border border-[#E2E7E8] px-[22px] py-[18px] text-body">
          <span className="min-w-0 flex-grow tabular-nums">
            {kitchenPath ? <Link href={kitchenPath} className="font-bold text-[#111418]">{kitchen}</Link> : <b>{kitchen}</b>}
            {" · "}
            {t("kitchen.items", { count })} · {f.money(bill?.total ?? order.total, order.currency)}
          </span>
          <a href="#receipt" className="font-bold">{t("track.receipt")}</a>
          <Link href={`/account/orders/${id}/report`} className="font-bold">{t("track.help")}</Link>
        </section>

        <section id="receipt" className="scroll-mt-28 rounded-[24px] border border-[#E2E7E8] p-[22px]" aria-labelledby="receipt-h">
          <h2 id="receipt-h" className="m-0 text-h3">{t("track.your_order")}</h2>
          <ul className="m-0 mt-3 flex list-none flex-col gap-1 p-0 text-body">
            {items.map((i, n) => (
              <li key={n}>{t("kitchen.line", { count: Number(i.quantity ?? 1), name: i.name ?? "" })}</li>
            ))}
          </ul>
          {bill && (
            <div className="mt-4 border-t border-[#E2E7E8] pt-4">
              <div className="mb-2 text-caption text-muted">{t("checkout.fair_bill")}</div>
              <FairBill lines={bill.lines} total={bill.total ?? order.total} currency={bill.currency} formatLocale={f.formatLocale} t={t} totalLabel={t("track.you_paid")} compact />
            </div>
          )}
          <Link href={`/account/orders/${id}/report`} className="mt-4 inline-block text-label">{t("track.report")}</Link>
        </section>
      </div>
    </div>
  );
}

// ── quick messages with the rider (no phone numbers; closed once delivered) ──
// Quick messages come from the API in the page's language (`lang`): each side
// reads them in their own.

type Chat = CoreSchemas["QuickMessagesOut"];
type ChatMessage = CoreSchemas["QuickMessage"];

async function fetchChat(orderId: string, lang: string): Promise<Chat | null> {
  try {
    return unwrap(await api.core.GET("/api/v1/orders/{order_id}/messages", { params: { path: { order_id: orderId }, query: { lang } } }));
  } catch {
    return null;
  }
}

function Messages({ orderId, rider }: { orderId: string; rider: string }) {
  const t = useT();
  const { language } = useLanguage();
  const [chat, setChat] = useState<Chat | null>(null);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef(new Set<string>());
  useEffect(() => {
    let alive = true;
    // Fetches can finish out of order (a poll, a status change, a quick message): only
    // the newest one applies, so an older list never replaces a newer one.
    let latest = 0;
    const refresh = () => {
      const n = ++latest;
      return fetchChat(orderId, language).then((c) => {
        if (!alive || !c || n !== latest) return;
        c.messages.forEach((m) => seen.current.add(m.id));
        setChat(c);
      });
    };
    void refresh();
    const stopSocket = liveSocket(`/ws/track/${orderId}`, (e) => {
      const m = JSON.parse(String(e.data)) as {
        type: string; payload: { id: string; sender_role: string; text: string; at: string; preset?: string | null };
      };
      if (m.type === "status_change" || m.type === "rider_assigned") void refresh();
      if (m.type !== "chat_message" || seen.current.has(m.payload.id)) return;
      if (m.payload.preset) {
        void refresh(); // a quick message: the API has it in this page's language
        return;
      }
      seen.current.add(m.payload.id);
      setChat((c) => c && { ...c, messages: [...c.messages, { ...m.payload, mine: m.payload.sender_role === c.me } as ChatMessage] });
    });
    const poll = setInterval(refresh, 20000);
    return () => {
      alive = false;
      clearInterval(poll);
      stopSocket();
    };
  }, [orderId, language]);

  async function send(body: { preset: string } | { text: string }) {
    setBusy(true);
    setError(null);
    try {
      const m = unwrap(await api.core.POST("/api/v1/orders/{order_id}/messages", {
        params: { path: { order_id: orderId }, query: { lang: language } }, body,
      }));
      if (!seen.current.has(m.id)) {
        seen.current.add(m.id);
        setChat((c) => c && { ...c, messages: [...c.messages, m] });
      }
      if ("text" in body) setText("");
    } catch {
      setError(t("track.send_failed"));
    } finally {
      setBusy(false);
    }
  }

  const name = chat?.other_name || rider;
  return (
    <section className="rounded-[24px] border border-[#E2E7E8] p-4 md:p-[22px]" aria-label={t("track.rider_card", { rider: name })}>
      <div className="flex items-center gap-[14px]">
        <span aria-hidden="true" className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full bg-[#E8A93C] text-h3 text-[#111418]">{name.trim()[0]?.toUpperCase()}</span>
        <span className="min-w-0 flex-grow">
          <b className="block text-h3">{name}</b>
          <span className="text-small text-muted">{t("track.your_rider")}</span>
        </span>
        {chat?.open && (
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="h-11 shrink-0 rounded-full border-[1.5px] border-[#C9D3D4] px-[22px] font-bold hover:border-[#0B5D66]">
            {t("track.message")}
          </button>
        )}
      </div>
      {chat?.open && (
        <>
          {open && (
            <ol className="m-0 mt-4 flex max-h-64 list-none flex-col gap-2 overflow-y-auto p-0" aria-live="polite">
              {chat.messages.length === 0 ? (
                <li className="text-small text-muted">{t("track.no_messages")}</li>
              ) : (
                chat.messages.map((m) => (
                  <li key={m.id} className={`max-w-[85%] rounded-2xl px-4 py-2 text-label ${m.mine ? "self-end bg-[#0B5D66] text-white" : "self-start bg-[#F4F6F6]"}`}>
                    <span className="sr-only">{m.mine ? t("track.you_said") : t("track.they_said", { name })}</span>
                    {m.text}
                  </li>
                ))
              )}
            </ol>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            {chat.presets.map((p) => (
              <button key={p.key} type="button" disabled={busy} onClick={() => void send({ preset: p.key })} className="h-11 rounded-full border-[1.5px] border-[#C9D3D4] px-[14px] text-label hover:border-[#0B5D66] disabled:opacity-50">
                {p.text}
              </button>
            ))}
          </div>
          {open && (
            <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (text.trim()) void send({ text: text.trim() }); }}>
              <label className="sr-only" htmlFor="chat-text">{t("track.write")}</label>
              <input id="chat-text" value={text} maxLength={140} onChange={(e) => setText(e.target.value)} placeholder={t("track.write")} className="h-11 min-w-0 flex-1 rounded-full border-[1.5px] border-[#C9D3D4] px-4 outline-none focus:border-[#0B5D66]" />
              <button type="submit" disabled={busy || !text.trim()} className="h-11 rounded-full bg-[#0B5D66] px-5 font-bold text-white disabled:opacity-50">{t("track.send")}</button>
            </form>
          )}
          {error && <p role="alert" className="m-0 mt-2 text-label text-[#8C1D18]">{error}</p>}
          <p className="m-0 mt-3 text-small text-muted">{t("track.private")}</p>
        </>
      )}
    </section>
  );
}

// ── cancelling (R8): only while GET /orders/{id} says the customer may (customer_cancel) ──

function payLabel(t: ReturnType<typeof useT>, method: string): string {
  const key = `account.pay.${method}`;
  return t(key) === key ? method : t(key);
}

function CancelOrder({ order, onDone, onRefresh }: { order: Order; onDone: (o: Order) => void; onRefresh: () => void }) {
  const t = useT();
  const f = useFormat();
  const c = order.customer_cancel;
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const z = f.zone(order.time_zone);
  // Not (or no longer) allowed: nothing, or why the cancel just failed (the kitchen started meanwhile).
  if (!c) return problem ? <p role="alert" className="m-0 rounded-[18px] bg-[#FBEAE9] px-[18px] py-[14px] text-body text-[#8C1D18]">{problem}</p> : null;
  const refund = Number(c.refund);

  async function cancel() {
    setBusy(true);
    setProblem(null);
    try {
      const r = await api.core.POST("/api/v1/orders/{order_id}/cancel", {
        params: { path: { order_id: order.id } }, body: { reason: "customer_cancelled" },
      });
      onDone(unwrap(r));
    } catch (e) {
      // The kitchen started cooking (or the order moved on) while the page was open.
      const late = e instanceof ApiError && e.status === 409;
      setProblem(late ? t("track.cancel_too_late") : t("track.cancel_failed"));
      setAsking(false);
      if (late) onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-[24px] border border-[#E2E7E8] p-[22px]" aria-labelledby="cancel-h" data-testid="cancel-order">
      {!asking ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p id="cancel-h" className="m-0 text-small text-[#3D4A4E]">
            {c.until ? t("track.cancel_until", { time: z.time(c.until) }) : t("track.cancel_before_accept")}
          </p>
          <button type="button" onClick={() => setAsking(true)}
            className="inline-flex min-h-11 items-center rounded-full border-[1.5px] border-[#C9D3D4] px-5 text-label font-bold text-[#B3261E] hover:border-[#B3261E]">
            {t("track.cancel")}
          </button>
        </div>
      ) : (
        <div role="alertdialog" aria-labelledby="cancel-h" aria-describedby="cancel-money">
          <h2 id="cancel-h" className="m-0 text-h3">{t("track.cancel_title")}</h2>
          <p id="cancel-money" className="m-0 mt-2 text-body text-[#3D4A4E]">
            {refund > 0
              ? t("track.cancel_refund", { amount: f.money(refund, order.currency), method: payLabel(t, c.refund_to) })
              : t("track.cancel_nothing")}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={() => void cancel()} disabled={busy} data-testid="cancel-confirm"
              className="inline-flex min-h-12 items-center rounded-full bg-[#B3261E] px-6 text-label font-bold text-white hover:bg-[#8C1D18] disabled:opacity-60">
              {busy ? t("track.cancelling") : t("track.cancel_yes")}
            </button>
            <button type="button" onClick={() => setAsking(false)} disabled={busy}
              className="inline-flex min-h-12 items-center rounded-full border-[1.5px] border-[#C9D3D4] px-6 text-label font-bold text-[#111418]">
              {t("track.cancel_keep")}
            </button>
          </div>
        </div>
      )}
      {problem && <p role="alert" className="m-0 mt-3 text-small text-[#B3261E]">{problem}</p>}
    </section>
  );
}

/** A cancelled order: what came back, and where (nothing when nothing was charged). */
function RefundLine({ order }: { order: Order }) {
  const t = useT();
  const f = useFormat();
  const paid = (order.status_history as { status: string }[] | undefined)?.some((h) => h.status === "placed");
  if (order.refunded) {
    return <p className="m-0 rounded-[18px] bg-[#EFF6F6] px-[18px] py-[14px] text-body text-[#083F46]" data-testid="refund-line">
      {t("track.refunded", { amount: f.money(order.refunded, order.currency), method: payLabel(t, order.payment_method) })}</p>;
  }
  if (!paid) return null;
  return <p className="m-0 rounded-[18px] bg-[#EFF6F6] px-[18px] py-[14px] text-body text-[#083F46]" data-testid="refund-line">
    {t("track.refund_pending", { amount: f.money(order.total, order.currency), method: payLabel(t, order.payment_method) })}</p>;
}
