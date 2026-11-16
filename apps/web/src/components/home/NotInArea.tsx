// An address outside every open zone (WebNotInArea): say so, collect a
// "notify me" for that point (or the coming-soon city it is in), and show the
// nearest live cities from the directory, by distance from the address.
import Link from "next/link";

import { flatCities, km } from "@/components/discover/places";
import { NotifyMe } from "@/components/NotifyMe";
import { number, photo } from "@/lib/format";
import { getContext, type Place } from "@/lib/prefs";
import { discover } from "@/lib/server";
import { ChangeAddress } from "./ChangeAddress";

const KM_PER_MI = 1.609344;

export async function NotInArea({ place }: { place: Place }) {
  const { t, directory: dir, formatLocale } = await getContext();
  const cities = flatCities(dir);
  const unit = dir.countries.find((k) => k.code === place.country)?.distance_unit ?? "km";
  const away = (c: { lat: number; lng: number }) => {
    const d = km(place, c);
    return t(unit === "mi" ? "common.mi" : "common.km", { n: number(Math.round(unit === "mi" ? d / KM_PER_MI : d), formatLocale, 0) });
  };
  // Live cities in the address's country first; other countries only when it has none.
  const live = cities.filter((c) => c.status === "live");
  const sameCountry = live.filter((c) => c.country === place.country);
  const nearest = (sameCountry.length ? sameCountry : live)
    .map((c) => ({ ...c, d: km(place, c) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, 3);
  const soonCity = cities.find((c) => c.code === place.city_code && c.status === "soon") ?? null;
  const first = nearest[0] ?? null;
  const near = first ? await discover({ city: first.code }) : null;
  const cover = near?.restaurants?.find((k) => k.cover_url)?.cover_url ?? null;

  return (
    <div className="container-page grid grid-cols-1 items-center gap-10 py-10 md:py-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:gap-16 xl:grid-cols-[minmax(0,1fr)_520px]">
      <div>
        <div className="text-caption text-muted">{place.label}</div>
        <h1 className="mt-3 text-display leading-[1.02]">{t("home.not_in_area_title")}</h1>
        <p className="mt-[14px] max-w-[560px] text-body-lg leading-[1.5] text-muted">
          {soonCity
            ? t("home.not_in_area_soon", { city: soonCity.name })
            : first
              ? t("home.not_in_area_body", { city: first.name, distance: away(first) })
              : t("home.not_in_area_none")}
        </p>
        <div className="mt-7 max-w-[600px]">
          <NotifyMe
            variant="card"
            source={soonCity ? "soon_city" : "outside_zone"}
            cityCode={soonCity?.code ?? null}
            point={soonCity ? null : { lat: place.lat, lng: place.lng }}
            title={t("home.notify_here")}
          />
        </div>
        <ChangeAddress country={place.country}>
          {" · "}
          <Link href="/cities" className="font-bold">
            {t("home.see_where")}
          </Link>
        </ChangeAddress>
        {nearest.length > 0 && (
          <div className="mt-9">
            <h2 className="m-0 text-label">{t("home.nearest_title")}</h2>
            <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
              {nearest.map((c) => (
                <li key={c.code}>
                  <Link href={c.path} className="flex h-11 items-center gap-2 rounded-full border border-[#DDEBEC] bg-[#EFF6F6] px-4 font-bold text-[#083F46] hover:text-[#083F46]">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#0B5D66]" />
                    {c.name}
                    <span className="font-semibold text-muted">· {away(c)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="relative hidden h-[520px] overflow-hidden rounded-[32px] bg-[#F6E7CC] lg:block">
        {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
        {cover && <img src={photo(cover, 800) ?? undefined} alt="" className="block h-full w-full object-cover" />}
      </div>
    </div>
  );
}
