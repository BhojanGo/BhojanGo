import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://bhojango.com";

  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/restaurants"],
        disallow: ["/cart", "/checkout", "/orders", "/profile", "/wallet", "/api/"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
