import type { MetadataRoute } from "next";

import { SITE } from "@/lib/server";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/checkout", "/orders", "/sign-in", "/design"] }],
    sitemap: `${SITE}/sitemap.xml`,
  };
}
