/**
 * What an admin may open, and where (R27). Pure functions over /admin/me's
 * permissions ({ permission: widest scopes }), so the console and its tests use
 * the same rules. The API checks every request again (shared/authz.py); this only
 * keeps the console from offering what the API would refuse.
 *
 * R26: the viewer labelled "Viewer (IN)" opened US Finance, and Settings showed
 * "didn't load" instead of saying the viewer has no access.
 */

/** Sections and the permission that shows each (anywhere in your scopes). */
export const SECTIONS = [
  { href: "/overview", label: "Overview", perm: "orders.view" },
  { href: "/operations", label: "Operations", perm: "orders.view" },
  { href: "/incidents", label: "Incidents", perm: "orders.view" },  // R17: pause, bulk refunds, bulk messages
  { href: "/partners", label: "Partners", perm: "partners.view" },
  { href: "/pricing", label: "Pricing & Rules", perm: "rules.view" },
  { href: "/markets", label: "Markets", perm: "markets.view" },
  { href: "/finance", label: "Finance", perm: "finance.view" },
  { href: "/settings", label: "Settings", perm: "admins.view" },
] as const;

/**
 * Grouped sections under a heading. Content: what the website shows that admins
 * write (Help in F9; Legal joins it in F10: add an item here). These are
 * per country inside the page, so they don't take the console's scope.
 */
export const SECTION_GROUPS: { label: string; items: { href: string; label: string; perm: string }[] }[] = [
  { label: "Content", items: [
    { href: "/content/help", label: "Help", perm: "content.view" },
    { href: "/content/legal", label: "Legal", perm: "legal.view" },  // F10: Terms and Privacy per country
  ] },
];

export type Permissions = Record<string, string[]>;

/** The permission a section needs, by its label (the `section` a page gives ConsoleShell). */
export function sectionPerm(section: string): string | null {
  return SECTIONS.find((s) => s.label === section)?.perm
    ?? SECTION_GROUPS.flatMap((g) => g.items).find((s) => s.label === section)?.perm
    ?? null;
}

/** True when `scope` is `target` or contains it ("IN" covers "IN-TG-HYD"; "*" covers all). */
export function covers(scope: string, target: string): boolean {
  if (scope === "*") return true;
  if (target === "*") return false;
  return target === scope || target.startsWith(`${scope}-`);
}

/** Held at, above or inside `target`: a city's ops admin may open their country, cut to their city. */
export function holdsAround(perms: Permissions | undefined, perm: string, target: string): boolean {
  return (perms?.[perm] ?? []).some((s) => covers(s, target) || covers(target, s));
}

export type Access = "ok" | "no-section" | "no-scope";

/**
 * May this admin open this section at this scope? `scope` is the console's
 * (null or "*": the page shows what is inside your scopes).
 * - "no-section": the role never has the section's permission (a viewer on Settings);
 * - "no-scope": it has it, but not here (a viewer for India on ?scope=US).
 */
export function sectionAccess(perms: Permissions | undefined, section: string, scope: string | null | undefined): Access {
  const perm = sectionPerm(section);
  if (!perm) return "ok";  // not a gated section
  if (!(perms?.[perm] ?? []).length) return "no-section";
  if (!scope || scope === "*") return "ok";
  return holdsAround(perms, perm, scope) ? "ok" : "no-scope";
}

/** The countries a section's scope picker offers: only those where the admin holds its permission. */
export function pickableCountries<T extends { code: string }>(countries: T[] | undefined, perms: Permissions | undefined,
  section: string): T[] {
  const perm = sectionPerm(section);
  if (!countries) return [];
  if (!perm || !perms) return countries;
  return countries.filter((c) => holdsAround(perms, perm, c.code));
}

/** "the United States" / "IN-TG-HYD": the words for the no-access message. */
export function noAccessText(access: Access, section: string, where: string | null): { title: string; body: string } {
  if (access === "no-section") {
    return { title: "You don't have access to " + section,
      body: "Your role doesn't include this section. Ask a country manager or super admin if you need it." };
  }
  return { title: `You don't have access to ${section} in ${where ?? "this place"}`,
    body: "Your role covers other places. Pick one of yours above, or ask a country manager or super admin for access here." };
}

/** Each role once with all its scopes: "Viewer (IN)", "Viewer (IN, US)", "Super admin". */
export function roleScopes(assignments: { role: string; scope: string }[] | undefined, labels: Record<string, string>): string {
  const byRole = new Map<string, string[]>();
  for (const a of assignments ?? []) byRole.set(a.role, [...(byRole.get(a.role) ?? []), a.scope]);
  return [...byRole].map(([role, scopes]) => {
    const where = scopes.filter((s) => s !== "*");
    return `${labels[role] ?? role}${where.length ? ` (${where.join(", ")})` : ""}`;
  }).join(" · ");
}
