// Every public city page and every live city's kitchens, from Markets (a city
// launched in admin appears here with no code change).
import type { MetadataRoute } from "next";

import { directory, discover, SITE } from "@/lib/server";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const dir = await directory();
  const pages: MetadataRoute.Sitemap = [
    { url: SITE, changeFrequency: "daily", priority: 1 },
    { url: `${SITE}/cities`, changeFrequency: "daily", priority: 0.9 },
    ...["help", "terms", "privacy", "credits", "partner", "ride"].map((p) => ({ url: `${SITE}/${p}`, changeFrequency: "monthly" as const, priority: 0.3 })),
  ];
  for (const k of dir.countries) {
    for (const r of k.regions) {
      for (const c of r.cities) {
        pages.push({ url: `${SITE}${c.path}`, changeFrequency: "daily", priority: c.status === "live" ? 0.9 : 0.5 });
        if (c.status !== "live") continue;
        const d = await discover({ city: c.code });
        for (const kitchen of d?.restaurants ?? []) pages.push({ url: `${SITE}${kitchen.path}`, changeFrequency: "daily", priority: 0.8 });
      }
    }
  }
  return pages;
}
