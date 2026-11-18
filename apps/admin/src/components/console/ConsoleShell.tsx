"use client";

/**
 * The admin console frame from the design board (P6, every section since P21):
 * header, country tabs, state chips with a searchable city picker, and the
 * section nav. Each section keeps its scope in the URL (?scope=IN-TG-HYD);
 * Markets keeps its own country/city routes. Admins only see the countries,
 * states and cities their roles cover, and only the sections they may use.
 * Layout (R8): from 1024 px the section nav is a side column; under it, a Menu
 * button in the header opens it as a drawer. Content is at most 1200 px wide with
 * 16 / 32 / 48 px gutters; the country tabs scroll sideways instead of wrapping.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CityPicker } from "@/components/console/CityPicker";
import { Logo } from "@bhojango/ui";
import { ROLE_LABELS, useAdminMe, useMarkets } from "@/lib/markets";
import { useAdminAuth, useAuthHydrated } from "@/store/auth";

/** Sections and the permission that shows each (anywhere in your scopes). */
const SECTIONS = [
  { href: "/overview", label: "Overview", perm: "orders.view" },
  { href: "/operations", label: "Operations", perm: "orders.view" },
  { href: "/partners", label: "Partners", perm: "partners.view" },
  { href: "/pricing", label: "Pricing & Rules", perm: "rules.view" },
  { href: "/markets", label: "Markets", perm: "markets.view" },
  { href: "/finance", label: "Finance", perm: "finance.view" },
  { href: "/settings", label: "Settings", perm: "admins.view" },
];

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

/** "IN-TG-HYD" → { country: "IN", region: "IN-TG", city: "IN-TG-HYD" }; "*" → ALL. */
export function parseScope(scope: string | null | undefined): { country: string; region: string | null; city: string | null } {
  if (!scope || scope === "*") return { country: "ALL", region: null, city: null };
  const p = scope.split("-");
  return { country: p[0]!, region: p.length >= 2 ? `${p[0]}-${p[1]}` : null, city: p.length >= 3 ? scope : null };
}

/**
 * The signed-in admin, once (R13): "Name · Role (scope)", or just "Role (scope)" when the name
 * already says the role (the seed's "USA Finance" with Finance (US) reads "Finance (US)";
 * "BhojanGo Admin", a super admin, reads "Super admin").
 */
export function whoLine(name: string | null | undefined, role: { role: string; scope: string } | null | undefined): string {
  const label = role ? `${ROLE_LABELS[role.role] ?? role.role}${role.scope !== "*" ? ` (${role.scope})` : ""}` : "";
  if (!name) return label;
  if (!label) return name;
  // A word of the role already in the name ("USA Finance" / Finance, "BhojanGo Admin" / Super admin): the role alone.
  const nameWords = new Set(name.toLowerCase().split(/\s+/));
  const repeats = (ROLE_LABELS[role!.role] ?? role!.role).toLowerCase().split(/[\s_]+/).some((w) => w.length > 2 && nameWords.has(w));
  return repeats ? label : `${name} · ${label}`;
}

export function ConsoleShell({
  section,
  country,
  region,
  city,
  cityHref,
  countryHref,
  scopeHref,
  hideScope = false,
  children,
}: {
  section: string;
  /** "ALL" for the all-countries view, else a country code */
  country: string;
  region?: string | null;
  city?: string | null;
  /** Sections other than Markets: where picking a scope goes (keeps the section). */
  scopeHref?: (scope: string) => string;
  /** Markets: where picking a city goes; defaults to that city's Markets page. */
  cityHref?: (country: string, city: string) => string;
  /** Markets/simulator: where a country tab goes. Setting it hides the state chips. */
  countryHref?: (country: string) => string;
  /** Sections that pick their country inside the page (Content): no country tabs or state chips. */
  hideScope?: boolean;
  children: React.ReactNode;
}) {
  const { isAuthenticated, user, logout } = useAdminAuth();
  const router = useRouter();
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();

  const hydrated = useAuthHydrated();
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (hydrated && !isAuthenticated) router.replace("/login");
  }, [hydrated, isAuthenticated, router]);
  useEffect(() => {
    if (!menu) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [menu]);
  if (!hydrated || !isAuthenticated) return null;

  const current = markets?.find((c) => c.code === country);
  const isGlobal = (me?.permissions["markets.view"] ?? me?.permissions["orders.view"] ?? []).includes("*");
  const role = me?.assignments[0];
  const initials = (user?.full_name ?? "?").split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  const toCountry = (code: string) => (scopeHref ? scopeHref(code) : countryHref ? countryHref(code) : `/markets/${code}`);
  const toRegion = (code: string) => (scopeHref ? scopeHref(code) : `/markets/${current?.code}?state=${code}`);
  const toCity = (c: string, code: string) => (scopeHref ? scopeHref(code) : cityHref ? cityHref(c, code) : `/markets/${c}/${code}`);
  const showStates = Boolean(scopeHref) || !countryHref;
  const sections = SECTIONS.filter((s) => !me || (me.permissions[s.perm] ?? []).length > 0);
  const scope = city ?? region ?? (country !== "ALL" ? country : null);
  const sectionLinks = sections.map((s) => {
    const href = s.href === "/markets" ? s.href : scope ? `${s.href}?scope=${scope}` : s.href;
    return (
      <Link key={s.href} href={href} onClick={() => setMenu(false)} aria-current={s.label === section ? "page" : undefined}
        className={`flex h-11 shrink-0 items-center rounded-xl px-4 text-label ${s.label === section ? "bg-peacock-tint font-bold text-peacock-dark" : "font-semibold text-kohl hover:bg-porcelain"}`}>
        {s.label}
      </Link>
    );
  }).concat(SECTION_GROUPS.map((g) => {
    const items = g.items.filter((s) => !me || (me.permissions[s.perm] ?? []).length > 0);
    if (!items.length) return null;
    return (
      <div key={g.label} role="group" aria-label={g.label} className="mt-4 flex shrink-0 flex-col gap-1 border-t border-line pt-4">
        <span className="px-4 pb-1 text-caption text-muted">{g.label}</span>
        {items.map((s) => (
          <Link key={s.href} href={s.href} onClick={() => setMenu(false)} aria-current={s.label === section ? "page" : undefined}
            className={`flex h-11 shrink-0 items-center rounded-xl px-4 text-label ${s.label === section ? "bg-peacock-tint font-bold text-peacock-dark" : "font-semibold text-kohl hover:bg-porcelain"}`}>
            {s.label}
          </Link>
        ))}
      </div>
    );
  }));

  return (
    <div className="flex min-h-screen flex-col bg-porcelain font-sans text-kohl">
      <header className="flex items-center gap-x-2 bg-white sm:gap-x-4 px-4 py-3 md:px-8 lg:px-12">
        <button type="button" onClick={() => setMenu(true)} aria-expanded={menu} aria-controls="admin-sections" aria-label="Menu"
          className="-ml-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-kohl hover:bg-porcelain lg:hidden">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
        </button>
        <Logo size={30} suffix="admin" />
        <div className="ml-auto flex min-w-0 items-center gap-2.5 text-small">
          <span className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-peacock-tint sm:flex text-small text-peacock-dark">{initials}</span>
          <span data-testid="who" className="hidden truncate md:inline">{whoLine(user?.full_name, role)}</span>
          <button type="button" onClick={() => { logout(); router.replace("/login"); }}
            className="h-9 shrink-0 whitespace-nowrap rounded-full px-3 font-semibold text-peacock hover:bg-peacock-wash md:ml-2">Sign out</button>
        </div>
      </header>

      {hideScope ? null : <nav aria-label="Country" className="flex items-center gap-1 overflow-x-auto border-b border-line bg-white px-4 md:px-8 lg:px-12">
        {isGlobal && (
          <Link href={scopeHref ? scopeHref("*") : "/markets"} aria-current={country === "ALL" ? "page" : undefined}
            className={`box-border flex h-[52px] shrink-0 items-center whitespace-nowrap border-b-[3px] px-4 text-label ${country === "ALL" ? "border-peacock font-bold text-peacock-dark" : "border-transparent font-semibold text-muted"}`}>
            All countries
          </Link>
        )}
        {markets?.map((c) => (
          <Link key={c.code} href={toCountry(c.code)} aria-current={c.code === country ? "page" : undefined}
            className={`box-border flex h-[52px] shrink-0 items-center gap-2 whitespace-nowrap border-b-[3px] px-4 text-label ${c.code === country ? "border-peacock font-bold text-peacock-dark" : "border-transparent font-semibold text-muted"}`}>
            <span className={`rounded-md px-1.5 py-0.5 text-caption ${c.code === country ? "bg-peacock-tint text-peacock-dark" : "bg-line-soft text-kohl"}`}>{c.code}</span>
            {c.name}
          </Link>
        ))}
        {!isGlobal && markets?.length === 1 ? <span className="ml-auto shrink-0 whitespace-nowrap text-label text-muted">You can see {markets[0]!.name} only</span> : null}
      </nav>}

      {current && !hideScope && (
        <nav aria-label={`State and city in ${current.name}`} className="flex flex-wrap items-center gap-2 border-b border-line bg-[#FAFBFB] px-4 py-2.5 md:px-8 lg:px-12">
          {showStates && <span className="mr-1 text-label text-muted">State</span>}
          {showStates && (
            <Link href={toCountry(current.code)} aria-current={!region && !city ? "true" : undefined}
              className={`flex h-9 items-center rounded-full px-3.5 text-label ${!region && !city ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold text-kohl"}`}>
              All states
            </Link>
          )}
          {showStates && current.regions.map((r) => {
            const on = region === r.code;
            return (
              <Link key={r.code} href={toRegion(r.code)} aria-current={on ? "true" : undefined}
                className={`flex h-9 items-center gap-2 rounded-full px-3.5 text-label ${on ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold text-kohl"}`}>
                {r.name} <span className={`text-small ${on ? "text-[#A9B8BA]" : "text-muted"}`}>{r.cities.length}</span>
              </Link>
            );
          })}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-label text-muted">City</span>
            <CityPicker country={current} value={city ?? null} onChange={(code) => router.push(toCity(current.code, code))} />
          </div>
        </nav>
      )}

      <div className="flex flex-grow">
        <nav aria-label="Admin sections" className="box-border hidden w-[248px] shrink-0 flex-col gap-1 border-r border-line bg-white px-4 py-6 lg:flex">
          {sectionLinks}
        </nav>
        {menu && (
          <div className="fixed inset-0 z-50 bg-[rgba(17,20,24,0.5)] lg:hidden" onClick={() => setMenu(false)}>
            <nav id="admin-sections" aria-label="Admin sections" onClick={(e) => e.stopPropagation()}
              className="flex h-full w-[min(300px,85vw)] flex-col gap-1 overflow-y-auto bg-white px-4 py-4 shadow-sheet">
              <div className="mb-2 flex items-center justify-between">
                <Logo size={26} suffix="admin" />
                <button type="button" autoFocus onClick={() => setMenu(false)} aria-label="Close menu"
                  className="flex h-11 w-11 items-center justify-center rounded-xl text-kohl hover:bg-porcelain">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
                </button>
              </div>
              {sectionLinks}
            </nav>
          </div>
        )}
        <main className="box-border min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8 lg:px-12">
          <div className="flex max-w-[1200px] flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
