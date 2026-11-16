// Where we deliver (WebCities): the whole directory from Markets. A new city
// or country appears here by itself once it is added in admin Markets.
// ?choose=1 is "Change city" (the home page's location line, R8): the visitor's
// country's cities with a search, other countries behind "Other countries"; picking a
// city remembers it (bg_city) and goes home in that city's country.
import type { Metadata } from "next";

import { ChooseCity, CitiesDirectory } from "@/components/discover/DirectoryBrowser";
import { flatCities, totalsLine } from "@/components/discover/places";
import { NotifyMe } from "@/components/NotifyMe";
import { getContext } from "@/lib/prefs";
import { discover, SITE } from "@/lib/server";

type Search = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ searchParams }: { searchParams: Search }): Promise<Metadata> {
  const { t } = await getContext();
  const choosing = (await searchParams).choose === "1";
  return { title: choosing ? t("cities.choose_title") : t("cities.title"), description: t("meta.cities_description"), alternates: { canonical: `${SITE}/cities` } };
}

export default async function Cities({ searchParams }: { searchParams: Search }) {
  const { t, directory: dir, place, country } = await getContext();
  const choosing = (await searchParams).choose === "1" ? { addressCity: place?.city_code ?? null } : null;
  // A photo per live city: its first kitchen's cover (data, not a mapping in code).
  const live = flatCities(dir).filter((c) => c.status === "live");
  const found = await Promise.all(live.map((c) => discover({ city: c.code })));
  const covers = Object.fromEntries(live.map((c, i) => [c.code, found[i]?.restaurants?.find((k) => k.cover_url)?.cover_url ?? null]));

  return (
    <div className="mx-auto max-w-[1440px] px-5 pb-16 pt-8 md:px-16 md:pb-[72px] md:pt-12">
      <h1 className="m-0 text-h1 tracking-[-1px] md:tracking-[-1.4px]">{choosing ? t("cities.choose_title") : t("cities.title")}</h1>
      <p className="mt-2 text-body-lg text-[#4C5A5E]">{choosing ? t("cities.choose_note") : totalsLine(t, dir.totals)}</p>
      {choosing ? (
        <ChooseCity dir={dir} covers={covers} country={country?.code ?? null} choosing={choosing} />
      ) : (
        <CitiesDirectory dir={dir} covers={covers} />
      )}
      <div className="mt-12">
        <NotifyMe source="suggest_city" title={t("cities.not_listed")} />
      </div>
    </div>
  );
}
