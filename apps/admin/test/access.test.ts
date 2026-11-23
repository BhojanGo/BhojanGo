// node --test: every admin role × every country × every console page (R27).
// R26: the viewer labelled "Viewer (IN)" opened US Finance, and Settings showed a load
// error instead of "no access". The console now refuses a section the role doesn't have
// and a scope outside the admin's countries, and offers only their countries. A new page
// that isn't in PAGES (so isn't checked here) fails the first test.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import test from "node:test";

import { pickableCountries, roleScopes, sectionAccess, sectionPerm, type Permissions } from "../src/lib/access.ts";

// What each role may do: a copy of backend/shared/authz.py PERMISSIONS (the API is the real check).
const VIEW = ["markets.view", "rules.view", "partners.view", "riders.view", "orders.view", "customers.view", "finance.view",
  "reports.view", "admins.view", "legal.view", "content.view"];
const ROLE_PERMS: Record<string, string[]> = {
  country_manager: [...VIEW, "markets.edit", "rules.edit", "admins.grant", "content.edit", "legal.edit"],
  city_ops: ["markets.view", "rules.view", "partners.view", "riders.view", "orders.view", "customers.view", "reports.view", "legal.view"],
  support_agent: ["orders.view", "customers.view", "partners.view", "riders.view", "legal.view", "content.view"],
  finance: ["finance.view", "rules.view", "orders.view", "reports.view", "partners.view", "riders.view", "legal.view"],
  viewer: VIEW.filter((p) => p !== "admins.view"),
};
// Each role's seeded scope per country (tools/seed/data.py ADMINS): city ops and support are city admins.
const HOME: Record<string, Record<string, string>> = {
  country_manager: { IN: "IN", US: "US" },
  city_ops: { IN: "IN-TG-HYD", US: "US-ID-BOI" },
  support_agent: { IN: "IN-TG-HYD", US: "US-ID-BOI" },
  finance: { IN: "IN", US: "US" },
  viewer: { IN: "IN", US: "US" },
};
const OTHER: Record<string, string> = { IN: "US", US: "IN" };
const CITY: Record<string, string> = { IN: "IN-TG-HYD", US: "US-ID-BOI" };

function me(role: string, scope: string): Permissions {
  return Object.fromEntries(ROLE_PERMS[role]!.map((p) => [p, [scope]]));
}

// Every page in src/app and the section it opens in ConsoleShell (null: not a console page).
const PAGES: Record<string, string | null> = {
  "page.tsx": null,  // redirects to /overview
  "login/page.tsx": null,
  "overview/page.tsx": "Overview",
  "operations/page.tsx": "Operations",
  "incidents/page.tsx": "Incidents",
  "partners/page.tsx": "Partners",
  "pricing/page.tsx": "Pricing & Rules",
  "pricing/simulator/page.tsx": "Pricing & Rules",
  "pricing/fees/page.tsx": "Pricing & Rules",
  "markets/page.tsx": "Markets",
  "markets/[country]/page.tsx": "Markets",
  "markets/[country]/[city]/page.tsx": "Markets",
  "finance/page.tsx": "Finance",
  "finance/statements/[id]/page.tsx": "Finance",
  "settings/page.tsx": "Settings",
  "content/help/page.tsx": "Help",
  "content/help/new/page.tsx": "Help",
  "content/help/[id]/page.tsx": "Help",
  "content/legal/page.tsx": "Legal",
};
const APP = join(import.meta.dirname, "..", "src", "app");

function pages(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? pages(p) : f === "page.tsx" ? [relative(APP, p).split(sep).join("/")] : [];
  });
}

test("every console page is in the table and opens its section in ConsoleShell", () => {
  const found = pages(APP).sort();
  assert.deepEqual(found, Object.keys(PAGES).sort(), "add the new page to PAGES with its section");
  for (const [page, section] of Object.entries(PAGES)) {
    if (!section) continue;
    const src = readFileSync(join(APP, page), "utf8");
    assert.ok(src.includes("<ConsoleShell"), `${page} must render inside ConsoleShell (it checks access)`);
    assert.ok(src.includes(`section="${section}"`), `${page} must open section "${section}"`);
    assert.ok(sectionPerm(section), `section "${section}" needs a permission in lib/access.ts`);
  }
});

const SECTIONS = [...new Set(Object.values(PAGES).filter((s): s is string => Boolean(s)))];
const CASES = Object.keys(ROLE_PERMS).flatMap((role) => ["IN", "US"].flatMap((country) => SECTIONS.map((section) => ({ role, country, section }))));

for (const { role, country, section } of CASES) {
  test(`${role} (${country}) on ${section}`, () => {
    const perms = me(role, HOME[role]![country]!);
    const has = ROLE_PERMS[role]!.includes(sectionPerm(section)!);
    // Their own country, state-wide and their city: open when the role has the section.
    for (const scope of [country, CITY[country]!, null]) {
      assert.equal(sectionAccess(perms, section, scope), has ? "ok" : "no-section", `${scope}`);
    }
    // The other country and its city: never (R26: a viewer for India on US Finance).
    for (const scope of [OTHER[country]!, CITY[OTHER[country]!]!]) {
      assert.equal(sectionAccess(perms, section, scope), has ? "no-scope" : "no-section", `${scope}`);
    }
    // The scope picker offers only their own country.
    const offered = pickableCountries([{ code: "IN" }, { code: "US" }], perms, section).map((c) => c.code);
    assert.deepEqual(offered, has ? [country] : []);
  });
}

test("a super admin opens everything everywhere", () => {
  const perms = Object.fromEntries([...VIEW, "admins.grant"].map((p) => [p, ["*"]]));
  for (const section of SECTIONS) for (const scope of ["IN", "US-ID-BOI", null]) assert.equal(sectionAccess(perms, section, scope), "ok");
});

test("a viewer holding two countries sees both, and the header says so", () => {
  const perms: Permissions = { "finance.view": ["IN", "US"] };
  assert.equal(sectionAccess(perms, "Finance", "US"), "ok");
  assert.equal(sectionAccess(perms, "Settings", "IN"), "no-section");
  const labels = { viewer: "Viewer", super_admin: "Super admin" };
  assert.equal(roleScopes([{ role: "viewer", scope: "IN" }, { role: "viewer", scope: "US" }], labels), "Viewer (IN, US)");
  assert.equal(roleScopes([{ role: "viewer", scope: "IN" }], labels), "Viewer (IN)");
  assert.equal(roleScopes([{ role: "super_admin", scope: "*" }], labels), "Super admin");
});
