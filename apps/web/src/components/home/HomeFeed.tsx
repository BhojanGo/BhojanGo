"use client";
// The personal home's live parts (WebHome / MWebHome): the active order bar,
// the greeting (visitor's local time; name only when signed in), the filter
// chips over the kitchen grid, and "Order again". Kitchens, cuisines and
// offers come from the server (/discover for the address); orders from the
// signed-in customer's own list.
import { ACTIVE_STATUSES, unwrap, type CoreSchemas, type OrderStatus } from "@bhojango/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { KitchenCard } from "@/components/Cards";
import { api, authed, useBag, useHydrated, useSession, type Pick } from "@/lib/client";
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

interface Reorder {
  restaurant: { id: string; slug: string; name: string };
  items: { menu_item_id: string; name: string; quantity: number; options?: Pick[] | null; price: number | string; available?: boolean }[];
  unavailable?: unknown[];
}

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
  const rider = (order.rider?.name as string | undefined) ?? null;
  const sub = [rider ? t("home.order_rider", { rider }) : null, order.pin ? t("home.order_pin", { pin: order.pin }) : null].filter(Boolean).join(" · ");
  const img = photo(cover, 400);
  return (
    <section aria-label={t("home.active_order")} className="order-1">
      <Link href={`/orders/${order.id}/track`} className="flex items-center gap-3 rounded-[16px] bg-[#111418] px-[14px] py-3 text-[#F2F5F5] hover:text-[#F2F5F5] md:gap-5 md:rounded-[20px] md:px-5 md:py-4">
        <span className="block h-10 w-10 shrink-0 overflow-hidden rounded-[10px] bg-[#24383B] md:h-14 md:w-14 md:rounded-[14px]">
          {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
          {img && <img src={img} alt="" className="block h-full w-full object-cover" />}
        </span>
        <span className="min-w-0 flex-grow">
          <b className="block truncate text-sm md:text-[17px]">
            {t(onWay ? "home.order_on_way" : "home.order_preparing", { kitchen: order.restaurant_name })}
          </b>
          {sub && <span className="block truncate text-xs text-[#A9B8BA] md:text-sm">{sub}</span>}
        </span>
        {minutes != null && eta && minutes < 600 && (
          <span className="hidden text-right md:block">
            <b className="block font-display text-[26px] font-semibold">{t("home.order_minutes", { count: minutes })}</b>
            <span className="text-[13px] text-[#A9B8BA]">{t("home.order_arriving", { time: f.time(eta) })}</span>
          </span>
        )}
        <span className="text-sm font-extrabold text-[#E8A93C] md:flex md:h-12 md:items-center md:rounded-full md:bg-[#E8A93C] md:px-5 md:text-base md:text-[#111418]">
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
      const r = await authed<Reorder>("POST", `/api/v1/orders/${o.id}/reorder`);
      const bag = useBag.getState();
      bag.clear();
      const restaurant = { id: r.restaurant.id, name: r.restaurant.name, slug: r.restaurant.slug, city: cityName, currency: o.currency };
      for (const it of r.items.filter((x) => x.available !== false)) {
        const picks = it.options ?? [];
        bag.add(restaurant, { menuItemId: it.menu_item_id, name: it.name, unitPrice: Number(it.price), quantity: it.quantity, picks, summary: picks.map((p) => p.option).join(", ") });
      }
      if (!useBag.getState().lines.length) {
        setProblem(t("home.reorder_none"));
        return;
      }
      router.push("/checkout");
    } catch {
      setProblem(t("common.error"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-labelledby="order-again" className="order-4 md:order-3">
      <div className="flex items-baseline justify-between">
        <h2 id="order-again" className="m-0 font-display text-xl font-semibold tracking-[-0.5px] md:text-[26px]">{t("home.order_again")}</h2>
        <Link href="/account/orders" className="font-bold">{t("home.all_orders")}</Link>
      </div>
      <div className="-mx-5 mt-3 flex gap-3 overflow-x-auto px-5 md:mx-0 md:mt-4 md:grid md:grid-cols-3 md:gap-4 md:overflow-visible md:px-0">
        {past.map((o) => {
          const img = photo(covers[o.restaurant_id] ?? null, 400);
          const items = (o.items as { name?: string; quantity?: number }[]).map((i) => ((i.quantity ?? 1) > 1 ? `${i.quantity} ${i.name}` : i.name)).join(", ");
          return (
            <div key={o.id} className="flex w-[240px] shrink-0 items-center gap-[10px] rounded-[16px] border border-[#E2E7E8] p-[10px] md:w-auto md:gap-4 md:rounded-[20px] md:p-4">
              <span className="block h-[52px] w-[52px] shrink-0 overflow-hidden rounded-[12px] bg-[#EFF6F6] md:h-[88px] md:w-[88px] md:rounded-[14px]">
                {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
                {img && <img src={img} alt="" loading="lazy" className="block h-full w-full object-cover" />}
              </span>
              <span className="min-w-0 flex-grow">
                <b className="block truncate text-sm md:text-base">{o.restaurant_name}</b>
                <span className="mt-[2px] hidden truncate text-sm text-[#4C5A5E] md:block">{items}</span>
                <span className="mt-[2px] block text-xs text-[#4C5A5E] md:text-[13px]">
                  <span className="hidden md:inline">{f.date(o.created_at)} · </span>
                  {f.money(o.total, o.currency)}
                </span>
                <button type="button" onClick={() => void again(o)} disabled={busy !== null} className="text-[13px] font-extrabold text-[#0B5D66] disabled:opacity-60 md:hidden">
                  {t("home.order_again_button")}
                </button>
              </span>
              <button
                type="button"
                onClick={() => void again(o)}
                disabled={busy !== null}
                aria-label={t("home.order_again_from", { kitchen: o.restaurant_name })}
                className="hidden h-11 shrink-0 items-center rounded-full bg-[#0B5D66] px-[18px] text-sm font-extrabold text-white hover:bg-[#083F46] disabled:opacity-60 md:flex"
              >
                {busy === o.id ? t("common.loading") : t("home.order_again_button")}
              </button>
            </div>
          );
        })}
      </div>
      {problem && <p role="alert" className="mt-2 text-sm text-[#A3271F]">{problem}</p>}
    </section>
  );
}

export function HomeFeed({
  kitchens,
  placeLabel,
  cityPath,
  cityName,
  currency,
  formatLocale,
  distanceUnit,
  cravings,
  offers,
}: {
  kitchens: Kitchen[];
  placeLabel: string;
  cityPath: string;
  cityName: string;
  currency: string;
  formatLocale: string;
  distanceUnit: string;
  cravings: React.ReactNode;
  offers: React.ReactNode;
}) {
  const t = useT();
  const { orders, user, hydrated } = useMyOrders();
  const [on, setOn] = useState<Set<Filter>>(new Set());
  const covers = useMemo(() => Object.fromEntries(kitchens.map((k) => [k.id, k.cover_url])), [kitchens]);
  const active = orders?.find((o) => ACTIVE_STATUSES.includes(o.status as OrderStatus)) ?? null;
  const shown = kitchens.filter((k) => [...on].every((f) => TEST[f](k)));
  const openCount = kitchens.filter((k) => k.open_now).length;
  const pod = hydrated ? partOfDay() : null;
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
    <div className="mx-auto flex max-w-[1440px] flex-col gap-6 px-5 pb-16 pt-4 md:gap-10 md:px-16 md:pb-24 md:pt-6">
      {active && <ActiveOrderBar order={active} cover={covers[active.restaurant_id] ?? null} />}

      <section aria-labelledby="greeting" className="order-2 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 id="greeting" className="m-0 font-display text-[28px] font-semibold tracking-[-0.8px] md:text-[40px] md:tracking-[-1px]">{greeting}</h1>
          <p className="mt-[6px] text-[15px] text-[#4C5A5E] md:text-base">{t("home.kitchens_deliver", { count: openCount, place: placeLabel })}</p>
        </div>
        <div role="group" aria-label={t("home.filters")} className="-mx-5 flex gap-2 overflow-x-auto px-5 md:mx-0 md:px-0">
          {FILTERS.map((f) => {
            const pressed = on.has(f);
            return (
              <button
                key={f}
                type="button"
                aria-pressed={pressed}
                aria-controls="kitchens"
                onClick={() => toggle(f)}
                className={`flex h-10 shrink-0 items-center rounded-full px-4 text-sm font-bold ${pressed ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
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
            <h2 id="kitchens-near" className="m-0 font-display text-xl font-semibold tracking-[-0.5px] md:text-[26px]">{t("home.kitchens_near")}</h2>
            <p className="mt-1 hidden text-[15px] text-[#4C5A5E] md:block">{t("home.kitchens_near_note")}</p>
          </div>
          {kitchens.length > SHOWN && (
            <Link href={cityPath} className="shrink-0 font-bold">
              {t("home.see_all", { count: kitchens.length })}
            </Link>
          )}
        </div>
        {shown.length ? (
          <div className="mt-3 grid gap-[18px] md:mt-5 md:grid-cols-2 md:gap-6 lg:grid-cols-4" aria-live="polite">
            {shown.slice(0, SHOWN).map((k) => (
              <KitchenCard key={k.id} k={k} t={t} currency={currency} formatLocale={formatLocale} distanceUnit={distanceUnit} />
            ))}
          </div>
        ) : (
          <p role="status" className="mt-4 text-[15px] text-[#4C5A5E]">
            {kitchens.length ? t("home.no_filter_match") : t("home.no_kitchens")}
          </p>
        )}
      </section>
    </div>
  );
}
