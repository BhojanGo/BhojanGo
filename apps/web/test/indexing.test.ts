// node --test: search engines index production only. QA (qa.bhojango.com) and every other environment
// send X-Robots-Tag: noindex, nofollow on every response and serve a robots.txt that blocks everything;
// production sends no such header and allows the public pages.
import assert from "node:assert/strict";
import test from "node:test";

import { indexable, robotsRules } from "../src/lib/indexing.ts";

async function headersFor(appEnv: string | undefined): Promise<{ key: string; value: string }[]> {
  const before = process.env.APP_ENV;
  if (appEnv === undefined) delete process.env.APP_ENV;
  else process.env.APP_ENV = appEnv;
  try {
    const config = (await import("../next.config.mjs")).default as { headers: () => Promise<{ source: string; headers: { key: string; value: string }[] }[]> };
    const rules = await config.headers();
    return rules.filter((r) => r.source === "/:path*").flatMap((r) => r.headers);
  } finally {
    if (before === undefined) delete process.env.APP_ENV;
    else process.env.APP_ENV = before;
  }
}

test("QA, staging and local send X-Robots-Tag: noindex, nofollow on every page", async () => {
  for (const env of ["qa", "staging", "development", undefined]) {
    const robots = (await headersFor(env)).filter((h) => h.key === "X-Robots-Tag");
    assert.deepEqual(robots, [{ key: "X-Robots-Tag", value: "noindex, nofollow" }], String(env));
  }
});

test("production sends no X-Robots-Tag", async () => {
  assert.equal((await headersFor("production")).some((h) => h.key === "X-Robots-Tag"), false);
});

test("robots.txt blocks everything outside production and allows the public pages in production", () => {
  for (const env of ["qa", "staging", undefined]) {
    assert.equal(indexable(env), false);
    assert.deepEqual(robotsRules(env, "https://qa.bhojango.com"), { rules: [{ userAgent: "*", disallow: "/" }] });
  }
  const prod = robotsRules("production", "https://bhojango.com");
  assert.equal(indexable("production"), true);
  assert.equal(prod.rules[0].allow, "/");
  assert.ok(!(prod.rules[0].disallow as string[]).includes("/"));
  assert.equal(prod.sitemap, "https://bhojango.com/sitemap.xml");
});
