"use client";
// WebFavourites: saved kitchens (cards) and saved dishes (with their kitchen).
// The heart removes one; a dish opens its kitchen's page, where it's added
// with its options.

import Link from "next/link";
import { useEffect, useState } from "react";

import { kitchenPath, Thumb } from "@/components/account/shared";
import { FavouriteHeart, useFavourites } from "@/components/FavouriteHeart";
import { authed, useSession } from "@/lib/client";
import { photo } from "@/lib/format";
import { useFormat, useT } from "@/lib/i18n";

interface FavKitchen {
  id: string;
  slug: string;
  name: string;
  cuisine_types: string[];
  cover_url: string | null;
  city: string;
  country: string;
  delivery_time_min: number;
  delivery_time_max: number;
  delivery_fee: number | string | null;
  currency: string;
  is_open?: boolean;
  open_now?: boolean;
  is_new?: boolean;
}

interface FavDish {
  id: string;
  name: string;
  price: number | string;
  currency: string;
  image_url: string | null;
  available: boolean;
  restaurant: { id: string; slug: string; name: string; city?: string; country?: string };
}

interface Favourites {
  restaurants: FavKitchen[];
  items: FavDish[];
}

type Show = "kitchens" | "dishes" | null;

function KitchenFav({ k }: { k: FavKitchen }) {
  const t = useT();
  const f = useFormat();
  const open = k.open_now ?? k.is_open;
  const fee = k.delivery_fee != null ? Number(k.delivery_fee) : null;
  return (
    <div className="relative">
      <Link href={kitchenPath(k.country, k.city, k.slug)} className="block text-[#111418] hover:text-[#111418]">
        <div className="relative aspect-[4/3] overflow-hidden rounded-[20px]">
          <Thumb src={photo(k.cover_url, 800)} name={k.name} className="h-full w-full rounded-[20px]" />
          {open != null && (
            <span className="absolute left-3 top-3 flex h-7 items-center rounded-full bg-[#111418] px-[10px] text-caption text-white">
              {open ? t("favourites.open_now") : t("favourites.closed_now")}
            </span>
          )}
        </div>
        <div className="mt-3 flex items-baseline justify-between gap-2">
          <b className="truncate text-h3">{k.name}</b>
          {k.is_new && <span className="shrink-0 rounded-md bg-[#DDEBEC] px-2 py-[3px] text-caption text-[#083F46]">{t("common.new")}</span>}
        </div>
        <div className="mt-1 truncate text-small text-[#4C5A5E]">{[...k.cuisine_types.slice(0, 2), k.city].filter(Boolean).join(" · ")}</div>
        <div className="mt-1 text-small">
          <b>{t("common.minutes", { min: k.delivery_time_min, max: k.delivery_time_max })}</b>
          {fee !== null && (
            <>
              {" · "}
              {fee === 0 ? <b className="text-[#0B5D66]">{t("common.free_delivery")}</b> : <span className="tabular-nums">{t("common.delivery_fee", { fee: f.money(fee, k.currency, { whole: true }) })}</span>}
            </>
          )}
        </div>
      </Link>
      <div className="absolute right-3 top-3">
        <FavouriteHeart kind="restaurant" id={k.id} name={k.name} />
      </div>
    </div>
  );
}

function DishFav({ d, href }: { d: FavDish; href: string | null }) {
  const t = useT();
  const f = useFormat();
  const body = (
    <>
      <Thumb src={photo(d.image_url, 400)} className="h-[72px] w-[72px] shrink-0 rounded-[14px] md:h-[84px] md:w-[84px]" />
      <span className="min-w-0 flex-grow">
        <b className="block truncate text-label">{d.name}</b>
        <span className="block truncate text-small text-[#4C5A5E]">{d.restaurant.name}</span>
        <b className="mt-1 block tabular-nums">{f.money(d.price, d.currency, { whole: true })}</b>
      </span>
    </>
  );
  return (
    <div className="flex items-center gap-[14px] rounded-[18px] border border-[#E2E7E8] p-[14px]">
      {href ? (
        <Link href={href} className="flex min-w-0 flex-grow items-center gap-[14px] text-[#111418] hover:text-[#111418]">{body}</Link>
      ) : (
        <span className="flex min-w-0 flex-grow items-center gap-[14px]">{body}</span>
      )}
      <span className="flex shrink-0 flex-col items-end gap-2 md:flex-row md:items-center">
        <FavouriteHeart kind="item" id={d.id} name={d.name} size={32} />
        {d.available && href ? (
          <Link
            href={href}
            aria-label={t("favourites.add_dish", { name: d.name, kitchen: d.restaurant.name })}
            className="flex h-10 items-center justify-center whitespace-nowrap rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-[22px] text-label text-[#111418] hover:text-[#111418]"
          >
            {t("favourites.add")}
          </Link>
        ) : (
          !d.available && <span className="text-label text-[#4C5A5E]">{t("favourites.sold_out")}</span>
        )}
      </span>
    </div>
  );
}

export function FavouritesView() {
  const t = useT();
  const user = useSession((s) => s.user);
  const { ids, loaded, load } = useFavourites();
  const [data, setData] = useState<Favourites | null | "error">(null);
  const [show, setShow] = useState<Show>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let live = true;
    authed<Favourites>("GET", "/api/v1/me/favourites")
      .then((r) => live && setData(r))
      .catch(() => live && setData("error"));
    return () => {
      live = false;
    };
  }, [retry]);

  // The hearts share one store; once it's loaded, an unsaved one leaves the page.
  useEffect(() => {
    if (user) void load(user.id);
  }, [user, load]);
  const kept = (kind: string, id: string) => loaded !== user?.id || ids.has(`${kind}:${id}`);

  if (data === null) return <p role="status" className="text-[#4C5A5E]">{t("account.loading")}</p>;
  if (data === "error") {
    return (
      <div>
        <h1 className="text-h1 tracking-[-0.8px]">{t("favourites.title")}</h1>
        <p role="alert" className="mt-4 text-[#4C5A5E]">
          {t("favourites.error")}{" "}
          <button type="button" onClick={() => { setData(null); setRetry((n) => n + 1); }} className="font-bold text-[#0B5D66]">{t("common.retry")}</button>
        </p>
      </div>
    );
  }

  const kitchens = data.restaurants.filter((k) => kept("restaurant", k.id));
  const dishes = data.items.filter((d) => kept("item", d.id));
  // A dish's kitchen page: from the dish's own city/country, else its saved kitchen's.
  const where = new Map(data.restaurants.map((k) => [k.id, k]));
  const dishHref = (d: FavDish) => {
    const city = d.restaurant.city ?? where.get(d.restaurant.id)?.city;
    const country = d.restaurant.country ?? where.get(d.restaurant.id)?.country;
    return city && country ? kitchenPath(country, city, d.restaurant.slug) : null;
  };
  const chip = (s: Exclude<Show, null>, label: string) => (
    <button
      type="button"
      aria-pressed={show === s}
      onClick={() => setShow((v) => (v === s ? null : s))}
      className={`flex h-10 shrink-0 items-center rounded-full px-4 text-label ${show === s ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
    >
      {label}
    </button>
  );

  return (
    <div>
      <h1 className="text-h1 tracking-[-0.8px]">{t("favourites.title")}</h1>
      {!kitchens.length && !dishes.length ? (
        <p className="mt-4 text-[#4C5A5E]">
          {t("favourites.empty")} <Link href="/" className="font-bold">{t("favourites.find_food")}</Link>
        </p>
      ) : (
        <>
          <div role="group" aria-label={t("favourites.show")} className="mt-4 flex gap-2">
            {chip("kitchens", t("favourites.kitchens", { count: kitchens.length }))}
            {chip("dishes", t("favourites.dishes", { count: dishes.length }))}
          </div>
          {show !== "dishes" && (
            <section aria-label={t("favourites.kitchens", { count: kitchens.length })} className="mt-5">
              {kitchens.length ? (
                <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                  {kitchens.map((k) => <KitchenFav key={k.id} k={k} />)}
                </div>
              ) : (
                <p className="text-[#4C5A5E]">{t("favourites.empty_kitchens")}</p>
              )}
            </section>
          )}
          {show !== "kitchens" && (
            <section aria-labelledby="saved-dishes" className="mt-9">
              <h2 id="saved-dishes" className="text-h2 tracking-[-0.5px]">{t("favourites.saved_dishes")}</h2>
              {dishes.length ? (
                <div className="mt-[14px] grid gap-3 xl:grid-cols-2">
                  {dishes.map((d) => <DishFav key={d.id} d={d} href={dishHref(d)} />)}
                </div>
              ) : (
                <p className="mt-3 text-[#4C5A5E]">{t("favourites.empty_dishes")}</p>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
