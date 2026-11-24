"use client";
// R36: the city page's search, "Dishes": each dish found by name with its restaurant, its price and add.
// A dish with options (size, spice) opens its restaurant's menu; a cart from another restaurant asks first.
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Plus } from "@/components/Icons";
import { okToReplaceBag, useBag, useHydrated } from "@/lib/client";
import { photo } from "@/lib/format";
import { useFormat, useT } from "@/lib/i18n";
import type { DishHit } from "@/lib/server";

export function DishResults({ dishes, currency, cityName }: { dishes: DishHit[]; currency: string; cityName: string }) {
  const t = useT();
  const f = useFormat();
  const router = useRouter();
  const hydrated = useHydrated();
  const bag = useBag();
  const qty = (d: DishHit) => (hydrated && bag.restaurant?.id === d.restaurant_id
    ? bag.lines.filter((l) => l.menuItemId === d.id).reduce((n, l) => n + l.quantity, 0) : 0);
  const add = (d: DishHit) => {
    if (d.has_options) return router.push(d.restaurant_path);
    if (!okToReplaceBag(d.restaurant_id, t)) return;
    if (d.pickup_only) bag.setFulfillment("pickup");
    bag.add({ id: d.restaurant_id, name: d.restaurant_name, slug: d.restaurant_slug, city: cityName, currency },
      { menuItemId: d.id, name: d.name, unitPrice: Number(d.price), quantity: 1, picks: [], summary: "" });
  };
  return (
    <ul className="m-0 mt-3 grid list-none gap-3 p-0 md:grid-cols-2" data-testid="dish-results">
      {dishes.map((d) => {
        const orderable = d.open_now && (d.deliverable || d.pickup_only);
        const pic = photo(d.photo_url, 400);
        const n = qty(d);
        return (
          <li key={d.id} data-testid="dish-hit" className="flex min-w-0 items-center gap-3 rounded-[18px] border border-[#E2E7E8] bg-white p-3">
            {pic && (
              // eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library
              <img src={pic} alt="" loading="lazy" className="h-16 w-16 shrink-0 rounded-[14px] object-cover" />
            )}
            <span className="min-w-0 flex-grow">
              <b className="block break-words text-label">{d.name}</b>
              <Link href={d.restaurant_path} className="block truncate text-small text-muted" data-testid="dish-hit-restaurant">{d.restaurant_name}</Link>
              <b className="block text-label tabular-nums">{f.money(d.price, currency)}</b>
              {!orderable && <span className="block text-small text-[#8C1D18]">{d.open_now ? t("common.too_far") : t("common.closed")}</span>}
            </span>
            <button type="button" disabled={!orderable} onClick={() => add(d)} aria-label={t("kitchen.add_dish", { name: d.name })}
              data-testid="dish-hit-add"
              className="flex h-10 min-w-10 shrink-0 items-center justify-center gap-1 rounded-full border-[1.5px] border-[#0B5D66] bg-white px-2 font-bold text-[#0B5D66] disabled:cursor-not-allowed disabled:border-dashed disabled:border-[#C9D3D4] disabled:text-[#8A9599]">
              {n > 0 && <span className="tabular-nums">{n}</span>}
              <Plus color={orderable ? "#0B5D66" : "#8A9599"} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
