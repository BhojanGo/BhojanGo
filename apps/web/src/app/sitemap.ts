// Every city page and every live restaurant page, for search engines.
import type { MetadataRoute } from "next";

import { citySlug } from "@/components/RestaurantCard";
import { cities, restaurantsIn, SITE } from "@/lib/server";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const list = await cities();
  const pages: MetadataRoute.Sitemap = [
    { url: SITE, changeFrequency: "daily", priority: 1 },
    ...["help", "terms", "privacy"].map((p) => ({ url: `${SITE}/${p}`, changeFrequency: "monthly" as const, priority: 0.3 })),
  ];
  for (const c of list) {
    pages.push({ url: `${SITE}/${c.slug}`, changeFrequency: "daily", priority: 0.9 });
    for (const r of await restaurantsIn(c)) {
      pages.push({ url: `${SITE}/${citySlug(r.city)}/${r.slug}`, lastModified: r.updated_at ? new Date(r.updated_at) : undefined, changeFrequency: "daily", priority: 0.8 });
    }
  }
  return pages;
}
