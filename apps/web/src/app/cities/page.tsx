// Where we deliver (WebCities): the whole directory from Markets. A new city
// or country appears here by itself once it is added in admin Markets.
import type { Metadata } from "next";

import { CitiesDirectory } from "@/components/discover/DirectoryBrowser";
import { flatCities, totalsLine } from "@/components/discover/places";
import { NotifyMe } from "@/components/NotifyMe";
import { getContext } from "@/lib/prefs";
import { discover, SITE } from "@/lib/server";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("cities.title"), description: t("meta.cities_description"), alternates: { canonical: `${SITE}/cities` } };
}

export default async function Cities() {
  const { t, directory: dir } = await getContext();
  // A photo per live city: its first kitchen's cover (data, not a mapping in code).
  const live = flatCities(dir).filter((c) => c.status === "live");
  const found = await Promise.all(live.map((c) => discover({ city: c.code })));
  const covers = Object.fromEntries(live.map((c, i) => [c.code, found[i]?.restaurants?.find((k) => k.cover_url)?.cover_url ?? null]));

  return (
    <div className="mx-auto max-w-[1440px] px-5 pb-16 pt-8 md:px-16 md:pb-[72px] md:pt-12">
      <h1 className="m-0 text-h1 tracking-[-1px] md:tracking-[-1.4px]">{t("cities.title")}</h1>
      <p className="mt-2 text-body-lg text-[#4C5A5E]">{totalsLine(t, dir.totals)}</p>
      <CitiesDirectory dir={dir} covers={covers} />
      <div className="mt-12">
        <NotifyMe source="suggest_city" title={t("cities.not_listed")} />
      </div>
    </div>
  );
}
