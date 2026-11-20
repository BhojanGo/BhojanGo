// Search engines index production only (R-domain, 2026-11-19): QA (qa.bhojango.com), staging and local
// send "X-Robots-Tag: noindex, nofollow" on every response (next.config.mjs) and a robots.txt that blocks
// everything. Tested in test/indexing.test.ts.

export const NOINDEX_HEADER = { key: "X-Robots-Tag", value: "noindex, nofollow" } as const;

/** True only in production: the one environment search engines may index. */
export function indexable(appEnv: string | undefined): boolean {
  return appEnv === "production";
}

export interface RobotsRules {
  rules: { userAgent: string; allow?: string; disallow: string | string[] }[];
  sitemap?: string;
}

/** robots.txt: everything blocked outside production; in production the private pages only. */
export function robotsRules(appEnv: string | undefined, site: string): RobotsRules {
  if (!indexable(appEnv)) return { rules: [{ userAgent: "*", disallow: "/" }] };
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/checkout", "/orders", "/account", "/signin"] }],
    sitemap: `${site}/sitemap.xml`,
  };
}
