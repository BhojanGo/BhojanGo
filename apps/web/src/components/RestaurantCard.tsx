// A kitchen on the city page and the home page (as on CustomerHome.html):
// the plate, name, cuisines and time, a gold star rating.
import Link from "next/link";

import type { Restaurant } from "@/lib/server";
import { PlateImage } from "@bhojango/ui";

export function citySlug(name: string) {
  return name.toLowerCase().replace(/\s+/g, "-");
}

export function RestaurantCard({ r }: { r: Restaurant }) {
  const rating = Number(r.rating ?? 0);
  return (
    <Link href={`/${citySlug(r.city)}/${r.slug}`} className="group block overflow-hidden rounded-card bg-white shadow-float transition hover:-translate-y-0.5">
      <PlateImage src={r.cover_url ?? r.logo_url ?? undefined} alt="" className="h-36" size={104} />
      <div className="space-y-1 p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="truncate text-[17px] font-extrabold group-hover:text-peacock">{r.name}</h3>
          {rating > 0 ? (
            <span className="shrink-0 text-sm font-bold" aria-label={`Rated ${rating.toFixed(1)}`}>
              <span className="text-kesar">★</span> {rating.toFixed(1)}
            </span>
          ) : null}
        </div>
        <p className="truncate text-sm text-muted">{r.cuisine_types.join(" · ")} · {r.delivery_time_min}–{r.delivery_time_max} min</p>
      </div>
    </Link>
  );
}
