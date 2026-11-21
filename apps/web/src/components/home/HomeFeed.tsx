"use client";
// The personal home's live parts (WebHome / MWebHome): the active order bar,
// the greeting (the delivery address's local time; name only when signed in), the filter
// chips over the kitchen grid, and "Order again". Kitchens, cuisines and
// offers come from the server (/discover for the address); orders from the
// signed-in customer's own list.
//
// Every count of kitchens on this page is a count of the one list from
// /discover for the address (all of it, open or not; the filter chips narrow
// what is shown): "N kitchens deliver to <address>", "See all N" (which shows
// that same list here, not the city page's city-wide one) and the cards.
import { ACTIVE_STATUSES, unwrap, type CoreSchemas, type OrderStatus } from "@bhojango/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { reorderToBag, type ReorderResponse } from "@bhojango/ui/reorder";

import { useKitchenBrief } from "@/components/account/shared";
import { KitchenCard } from "@/components/Cards";
import { kitchenPhoto, KitchenPhoto } from "@/components/KitchenPhoto";
import { AddressPill } from "@/components/HeaderParts";
import { api, authed, useBag, useHydrated, useSession } from "@/lib/client";
import { riderFirstName } from "@/lib/contract";
import { partOfDay, photo } from "@/lib/format";
import { useFormat, useT } from "@/lib/i18n";
import type { KitchenCard as Kitchen } from "@/lib/server";

type Order = CoreSchemas["OrderResponse"];
type Filter = "open" | "fast" | "offers" | "veg" | "free";
const FILTERS: Filter[] = ["open", "fast", "offers", "veg", "free"];
const SHOWN = 8;

const VEG = /(^|[-_\s])(pure[-_\s]?)?veg(etarian|an)?($|[-_\s])/i;
const isVeg = (k: Kitchen) => k.tags.some((x) => VEG.test(x)) || k.cuisine_types.some((x) => VEG.test(x));

const TEST: Record<Filter, (k: Kitchen) => boolean> = {
  open: (k) => k.open_now,
  fast: (k) => k.eta_max <= 30,
  offers: (k) => k.offer != null,
  veg: isVeg,
  free: (k) => k.free_delivery || (k.delivery_fee != null && Number(k.delivery_fee) === 0),
};


/** The customer's recent orders (signed in only). */
function useMyOrders() {
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const signedIn = hydrated && !!user;
  useEffect(() => {
    if (!signedIn) return;
    let live = true;
    api.core
      .GET("/api/v1/orders", { params: { query: { limit: 20 } } })
      .then((r) => live && setOrders(unwrap(r).items))
      .catch(() => live && setOrders([]));
    return () => {
      live = false;
    };
  }, [signedIn]);
  return { orders: signedIn ? orders : null, user: signedIn ? user : null, hydrated };
}

function ActiveOrderBar({ order, cover }: { order: Order; cover: string | null }) {
  const t = useT();
  const f = useFormat();
  const step = ACTIVE_STATUSES.indexOf(order.status as OrderStatus);
  const progress = Math.max(0.08, (step + 1) / (ACTIVE_STATUSES.length + 1));
  const onWay = order.status === "picked_up";
  const eta = order.estimated_delivery_time;
  // The ETA in minutes is read in the browser only (the page is not cached with it).
  const [now] = useState(() => Date.now());
  const minutes = eta ? Math.max(1, Math.round((new Date(eta).getTime() - now) / 60000)) : null;
  // The rider's first name and the door PIN come with the active order (GET /orders).
  const rider = riderFirstName(order);
  const pin = onWay ? (order as { pin?: string | null }).pin ?? null : null; // once picked up (R27)
  const sub = [rider ? t("home.order_rider", { rider }) : null, pin ? t("home.order_pin", { pin }) : null].filter(Boolean).join(" · ");
  return (
    <section aria-label={t("home.active_order")} className="order-1">
      <Link href={`/orders/${order.id}/track`} className="flex items-center gap-3 rounded-[16px] bg-[#111418] px-[14px] py-3 text-[#F2F5F5] hover:text-[#F2F5F5] md:gap-5 md:rounded-[20px] md:px-5 md:py-4">
        <OrderKitchenPhoto restaurantId={order.restaurant_id} known={cover} className="block h-10 w-10 shrink-0 overflow-hidden rounded-[10px] md:h-14 md:w-14 md:rounded-[14px]" />
        <span className="min-w-0 flex-grow">
          <b className="line-clamp-2 block text-h3 md:line-clamp-none md:truncate">
            {t(onWay ? "home.order_on_way" : "home.order_preparing", { kitchen: order.restaurant_name })}
          </b>
          {/* phone: the minutes go here (the big ETA block is desktop only) */}
          {(sub || (minutes != null && minutes < 600)) && (
            <span className="block truncate text-small text-[#A9B8BA]">
              <span className="md:hidden">{[minutes != null && minutes < 600 ? t("home.order_minutes", { count: minutes }) : null, sub].filter(Boolean).join(" · ")}</span>
              <span className="hidden md:inline">{sub}</span>
            </span>
          )}
        </span>
        {minutes != null && eta && minutes < 600 && (
          <span className="hidden text-right md:block">
            <b className="block text-h2">{t("home.order_minutes", { count: minutes })}</b>
            <span className="text-small text-[#A9B8BA]">{t("home.order_arriving", { time: f.zone(order.time_zone).time(eta) })}</span>
          </span>
        )}
        <span className="text-label text-[#E8A93C] md:flex md:h-12 md:items-center md:rounded-full md:bg-[#E8A93C] md:px-5 md:text-[#111418]">
          <span className="md:hidden">{t("home.track")}</span>
          <span className="hidden md:inline">{t("home.track_order")}</span>
        </span>
      </Link>
      <div className="mt-[10px] hidden h-[6px] overflow-hidden rounded-full bg-[#E2E7E8] md:flex" role="progressbar" aria-label={t("home.active_order")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
        <span className="bg-[#0B5D66]" style={{ width: `${progress * 100}%` }} />
      </div>
    </section>
  );
}

/** The kitchen of a past or current order: its photo from this address's kitchens, else
 * its public page (a kitchen that doesn't deliver here now), else the branded tile. */
function OrderKitchenPhoto({ restaurantId, known, className }: { restaurantId: string; known: string | null | undefined; className: string }) {
  const brief = useKitchenBrief(known ? null : restaurantId);
  return <KitchenPhoto src={photo(known ?? kitchenPhoto(brief), 400)} className={className} />;
}

function OrderAgain({ orders, covers, cityName }: { orders: Order[]; covers: Record<string, string | null>; cityName: string }) {
  const t = useT();
  const f = useFormat();
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const past = useMemo(() => {
    const seen = new Set<string>();
    return orders.filter((o) => o.status === "delivered" && !seen.has(o.restaurant_id) && seen.add(o.restaurant_id)).slice(0, 3);
  }, [orders]);
  if (!past.length) return null;

  async function again(o: Order) {
    setBusy(o.id);
    setProblem(null);
    try {
      // R27: the same items, options and quantities (packages/ui reorder.js); what changed is said, the rest added
      const r = await authed<ReorderResponse>("POST", `/api/v1/orders/${o.id}/reorder`);
      const { lines, notes } = reorderToBag(r);
      const said = notes.map((n) => t(n.key, n.values));
      if (!lines.length) {
        setProblem([...said, t("home.reorder_none")].join(" "));
        return;
      }
      const bag = useBag.getState();
      bag.clear();
      const restaurant = { id: r.restaurant.id, name: r.restaurant.name, slug: r.restaurant.slug ?? "", city: cityName, currency: o.currency };
      for (const line of lines) bag.add(restaurant, line);
      if (said.length) setProblem([...said, t("account.receipt.reorder.rest_added")].join(" "));
      else router.push("/checkout");
    } catch {
      setProblem(t("common.error"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-labelledby="order-again" className="order-4 md:order-3">
      <div className="flex items-baseline justify-between">
        <h2 id="order-again" className="m-0 text-h2">{t("home.order_again")}</h2>
        <Link href="/account/orders" className="font-bold">{t("home.all_orders")}</Link>
      </div>
      <div className="-mx-4 mt-3 flex gap-3 overflow-x-auto px-4 md:mx-0 md:mt-4 md:grid md:grid-cols-2 md:gap-4 md:overflow-visible md:px-0 xl:grid-cols-3">
        {past.map((o) => {
          const items = (o.items as { name?: string; quantity?: number }[]).map((i) => ((i.quantity ?? 1) > 1 ? `${i.quantity} ${i.name}` : i.name)).join(", ");
          return (
            <div key={o.id} className="flex w-[240px] shrink-0 items-center gap-[10px] rounded-[16px] border border-[#E2E7E8] p-[10px] md:w-auto md:gap-4 md:rounded-[20px] md:p-4">
              <OrderKitchenPhoto restaurantId={o.restaurant_id} known={covers[o.restaurant_id]}
                className="block h-[52px] w-[52px] shrink-0 overflow-hidden rounded-[12px] md:h-[88px] md:w-[88px] md:rounded-[14px]" />
              <span className="min-w-0 flex-grow">
                <b className="block truncate text-label">{o.restaurant_name}</b>
                <span className="mt-[2px] hidden truncate text-small text-muted md:block">{items}</span>
                <span className="mt-[2px] block text-small tabular-nums text-muted">
                  <span className="hidden md:inline">{f.zone(o.time_zone).date(o.created_at)} · </span>
                  {f.money(o.total, o.currency)}
                </span>
                {/* One compact action at every width: a big button beside the text left the kitchen's
                    name a few letters wide in a 3-up row (R8 audit, 1366 px at 125 %). */}
                <button
                  type="button"
                  onClick={() => void again(o)}
                  disabled={busy !== null}
                  aria-label={t("home.order_again_from", { kitchen: o.restaurant_name })}
                  className="mt-1 inline-flex min-h-[44px] items-center text-label text-[#0B5D66] hover:underline disabled:opacity-60 md:min-h-0"
                >
                  {busy === o.id ? t("common.loading") : t("home.order_again_button")}
                </button>
              </span>
            </div>
          );
        })}
      </div>
      {problem && <p role="alert" className="mt-2 text-small text-[#A3271F]">{problem}</p>}
    </section>
  );
}

export function HomeFeed({
  kitchens,
  placeLabel,
  placeCountry,
  cityName,
  currency,
  formatLocale,
  distanceUnit,
  timeZone,
  cravings,
  offers,
}: {
  kitchens: Kitchen[];
  placeLabel: string;
  /** The delivery address's country (ISO code), for the address search. */
  placeCountry?: string | null;
  cityName: string;
  currency: string;
  formatLocale: string;
  distanceUnit: string;
  /** The delivery address's city time zone (GET /discover), else the country's (Markets): the greeting's clock. */
  timeZone: string | null;
  cravings: React.ReactNode;
  offers: React.ReactNode;
}) {
  const t = useT();
  const { orders, user, hydrated } = useMyOrders();
  const [on, setOn] = useState<Set<Filter>>(new Set());
  const [all, setAll] = useState(false);
  const covers = useMemo(() => Object.fromEntries(kitchens.map((k) => [k.id, kitchenPhoto(k)])), [kitchens]);
  const active = orders?.find((o) => ACTIVE_STATUSES.includes(o.status as OrderStatus)) ?? null;
  const shown = kitchens.filter((k) => [...on].every((f) => TEST[f](k)));
  const pod = hydrated ? partOfDay(timeZone) : null; // the delivery address's clock, not the device's
  const first = user?.full_name?.trim().split(/\s+/)[0];
  const greeting = !pod ? t("home.greeting") : first ? t(`home.greeting_${pod}_name`, { name: first }) : t(`home.greeting_${pod}`);

  const toggle = (f: Filter) =>
    setOn((cur) => {
      const next = new Set(cur);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });

  return (
    <div className="flex container-page flex-col gap-6 pb-16 pt-4 md:gap-10 md:pb-24 md:pt-6">
      {active && <ActiveOrderBar order={active} cover={covers[active.restaurant_id] ?? null} />}

      <section aria-labelledby="greeting" className="order-2 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 id="greeting" className="m-0 text-h1">{greeting}</h1>
          <p className="mt-[6px] text-body text-muted">
            {t("home.kitchens_deliver", { count: kitchens.length, place: "\u0000" }).split("\u0000").map((part, i) => (
              <span key={i}>{i > 0 && <AddressPill inline label={placeLabel} country={placeCountry ?? null} />}{part}</span>
            ))}
          </p>
        </div>
        <div role="group" aria-label={t("home.filters")} className="-mx-4 flex gap-2 overflow-x-auto px-4 md:mx-0 md:px-0">
          {FILTERS.map((f) => {
            const pressed = on.has(f);
            return (
              <button
                key={f}
                type="button"
                aria-pressed={pressed}
                aria-controls="kitchens"
                onClick={() => toggle(f)}
                className={`flex h-10 shrink-0 items-center rounded-full px-4 text-label ${pressed ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
              >
                {t(`home.filter_${f}`)}
              </button>
            );
          })}
        </div>
      </section>

      {orders && <OrderAgain orders={orders} covers={covers} cityName={cityName} />}

      <div className="order-3 md:order-4">{cravings}</div>
      <div className="order-5">{offers}</div>

      <section id="kitchens" aria-labelledby="kitchens-near" className="order-6">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 id="kitchens-near" className="m-0 text-h2">{t("home.kitchens_near")}</h2>
            <p className="mt-1 hidden text-body text-muted md:block">{t("home.kitchens_near_note")}</p>
          </div>
          {/* the rest of the same list, here (with the filters on: the rest of what they keep) */}
          {!all && shown.length > SHOWN && (
            <button
              type="button"
              aria-controls="kitchens-list"
              aria-expanded={false}
              onClick={() => setAll(true)}
              className="shrink-0 font-bold text-[#0B5D66] hover:underline"
            >
              {t("home.see_all", { count: shown.length })}
            </button>
          )}
        </div>
        {shown.length ? (
          <div id="kitchens-list" className="mt-3 grid gap-[18px] sm:grid-cols-2 md:mt-5 md:gap-6 lg:grid-cols-3 xl:grid-cols-4" aria-live="polite">
            {(all ? shown : shown.slice(0, SHOWN)).map((k) => (
              <KitchenCard key={k.id} k={k} t={t} currency={currency} formatLocale={formatLocale} distanceUnit={distanceUnit} />
            ))}
          </div>
        ) : (
          <p role="status" className="mt-4 text-body text-muted">
            {kitchens.length ? t("home.no_filter_match") : t("home.no_kitchens")}
          </p>
        )}
      </section>
    </div>
  );
}
