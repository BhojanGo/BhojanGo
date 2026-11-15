// Home. Three states, decided on the server from the visitor's address cookie:
// none -> first visit (WebLanding); served -> personal home (WebHome);
// outside every zone -> "not in your area yet" (WebNotInArea).
import type { Metadata } from "next";

import { Landing } from "@/components/home/Landing";
import { NotInArea } from "@/components/home/NotInArea";
import { PersonalHome } from "@/components/home/PersonalHome";
import { getContext } from "@/lib/prefs";
import { discover, SITE } from "@/lib/server";

export async function generateMetadata(): Promise<Metadata> {
  const { t, place } = await getContext();
  return {
    // The landing page uses the site's default title ("BhojanGo — Real food. Fair prices.").
    ...(place ? { title: place.served === false ? t("meta.not_in_area") : t("meta.home") } : {}),
    alternates: { canonical: `${SITE}/` },
  };
}

export default async function Home() {
  const { place } = await getContext();
  if (!place) return <Landing />;
  if (place.served === false) return <NotInArea place={place} />;
  const d = await discover({ lat: place.lat, lng: place.lng });
  if (d && !d.served) return <NotInArea place={place} />;
  return <PersonalHome place={place} d={d ?? { served: true, restaurants: [], offers: [], cuisines: [] }} />;
}
