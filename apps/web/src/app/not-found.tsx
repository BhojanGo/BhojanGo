// Not found (R8): any unknown URL, and every notFound() (a kitchen, city or order
// that isn't there). Inside the site's frame (header, footer, tab bar), in the
// visitor's language: what happened, a search box, and the ways on. The photo is
// the visitor's country's hero dish (Markets), as on the landing page.
import type { Metadata } from "next";

import { ErrorFrame, WayList } from "@/components/ErrorFrame";
import { SearchBox } from "@/components/HeaderParts";
import { libraryPhoto } from "@/lib/format";
import { getContext } from "@/lib/prefs";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("errors.title_404"), robots: { index: false, follow: true } };
}

export default async function NotFound() {
  const { t, place, country, directory } = await getContext();
  const hero = libraryPhoto(country?.hero_photo ?? directory.hero_photo, 800);
  const cityPath = place && place.served !== false ? (place.city_path ?? null) : null;
  const ways = [
    { href: "/", label: t("errors.go_home") },
    { href: "/cities", label: t("errors.where_we_deliver") },
    { href: "/help", label: t("errors.help") },
  ];
  return (
    <ErrorFrame photo={hero} title={t("errors.title_404")} body={t("errors.body_404")}>
      <SearchBox cityPath={cityPath} />
      <WayList label={t("errors.popular")} ways={ways} />
    </ErrorFrame>
  );
}
