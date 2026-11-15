import type { MetadataRoute } from "next";

import { INDEXABLE, SITE } from "@/lib/server";

export default function robots(): MetadataRoute.Robots {
  if (!INDEXABLE) return { rules: [{ userAgent: "*", disallow: "/" }] };
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/checkout", "/orders", "/account", "/signin"] }],
    sitemap: `${SITE}/sitemap.xml`,
  };
}
