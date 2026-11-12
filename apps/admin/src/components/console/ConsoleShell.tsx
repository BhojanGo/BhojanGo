"use client";

/**
 * The admin console frame from the design board (P6, every section since P21):
 * header, country tabs, state chips with a searchable city picker, and the
 * section nav. Each section keeps its scope in the URL (?scope=IN-TG-HYD);
 * Markets keeps its own country/city routes. Admins only see the countries,
 * states and cities their roles cover, and only the sections they may use.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { CityPicker } from "@/components/console/CityPicker";
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

function Logo() {
  return (
    <div className="flex items-center gap-2.5 font-display text-xl font-bold tracking-[-0.4px]">
      <svg width="30" height="30" viewBox="0 0 40 40" aria-hidden="true">
        <path d="M11 5.5v24" stroke="#0B5D66" strokeWidth="5" strokeLinecap="round" fill="none" />
        <circle cx="20.5" cy="25" r="8.5" fill="none" stroke="#0B5D66" strokeWidth="5" />
        <path d="M18.5 13.5c-1.6-1.8 1.6-3.4 0-5.6M24.5 13.5c-1.6-1.8 1.6-3.4 0-5.6" stroke="#D4932A" strokeWidth="2.2" strokeLinecap="round" fill="none" />
      </svg>
      bhojango <span className="font-body text-sm font-semibold tracking-normal text-muted">admin</span>
    </div>
  );
}

/** "IN-TG-HYD" → { country: "IN", region: "IN-TG", city: "IN-TG-HYD" }; "*" → ALL. */
export function parseScope(scope: string | null | undefined): { country: string; region: string | null; city: string | null } {
  if (!scope || scope === "*") return { country: "ALL", region: null, city: null };
  const p = scope.split("-");
  return { country: p[0]!, region: p.length >= 2 ? `${p[0]}-${p[1]}` : null, city: p.length >= 3 ? scope : null };
}

export function ConsoleShell({
  section,
  country,
  region,
  city,
  cityHref,
  countryHref,
  scopeHref,
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
  children: React.ReactNode;
}) {
  const { isAuthenticated, user, logout } = useAdminAuth();
  const router = useRouter();
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();

  const hydrated = useAuthHydrated();
  useEffect(() => {
    if (hydrated && !isAuthenticated) router.replace("/login");
  }, [hydrated, isAuthenticated, router]);
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

  return (
    <div className="flex min-h-screen flex-col bg-porcelain font-body text-kohl">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 bg-white px-4 py-3 sm:px-8">
        <Logo />
        <div className="ml-auto flex items-center gap-2.5 text-sm">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-peacock-tint text-xs font-extrabold text-peacock-dark">{initials}</span>
          <span data-testid="who">
            {user?.full_name}
            {role ? ` · ${ROLE_LABELS[role.role] ?? role.role}${role.scope !== "*" ? ` (${role.scope})` : ""}` : ""}
          </span>
          <button type="button" onClick={() => { logout(); router.replace("/login"); }}
            className="ml-2 h-9 rounded-full px-3 font-semibold text-peacock hover:bg-peacock-wash">Sign out</button>
        </div>
      </header>

      <nav aria-label="Country" className="flex flex-wrap items-center gap-1 overflow-x-auto border-b border-line bg-white px-4 sm:px-8">
        {isGlobal && (
          <Link href={scopeHref ? scopeHref("*") : "/markets"} aria-current={country === "ALL" ? "page" : undefined}
            className={`box-border flex h-[52px] items-center border-b-[3px] px-4 text-[15px] ${country === "ALL" ? "border-peacock font-extrabold text-peacock-dark" : "border-transparent font-semibold text-muted"}`}>
            All countries
          </Link>
        )}
        {markets?.map((c) => (
          <Link key={c.code} href={toCountry(c.code)} aria-current={c.code === country ? "page" : undefined}
            className={`box-border flex h-[52px] items-center gap-2 border-b-[3px] px-4 text-[15px] ${c.code === country ? "border-peacock font-extrabold text-peacock-dark" : "border-transparent font-semibold text-muted"}`}>
            <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-extrabold ${c.code === country ? "bg-peacock-tint text-peacock-dark" : "bg-line-soft text-kohl"}`}>{c.code}</span>
            {c.name}
          </Link>
        ))}
        {!isGlobal && markets?.length === 1 ? <span className="ml-auto text-[13px] font-semibold text-muted">You can see {markets[0]!.name} only</span> : null}
      </nav>

      {current && (
        <nav aria-label={`State and city in ${current.name}`} className="flex flex-wrap items-center gap-2 border-b border-line bg-[#FAFBFB] px-4 py-2.5 sm:px-8">
          {showStates && <span className="mr-1 text-[13px] font-bold text-muted">State</span>}
          {showStates && (
            <Link href={toCountry(current.code)} aria-current={!region && !city ? "true" : undefined}
              className={`flex h-9 items-center rounded-full px-3.5 text-sm ${!region && !city ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold text-kohl"}`}>
              All states
            </Link>
          )}
          {showStates && current.regions.map((r) => {
            const on = region === r.code;
            return (
              <Link key={r.code} href={toRegion(r.code)} aria-current={on ? "true" : undefined}
                className={`flex h-9 items-center gap-2 rounded-full px-3.5 text-sm ${on ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold text-kohl"}`}>
                {r.name} <span className={`text-xs ${on ? "text-[#A9B8BA]" : "text-muted"}`}>{r.cities.length}</span>
              </Link>
            );
          })}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[13px] font-bold text-muted">City</span>
            <CityPicker country={current} value={city ?? null} onChange={(code) => router.push(toCity(current.code, code))} />
          </div>
        </nav>
      )}

      <div className="flex flex-grow flex-wrap">
        <nav aria-label="Admin sections" className="box-border flex flex-[1_1_248px] flex-col gap-1 border-r border-line bg-white px-4 py-6">
          {sections.map((s) => {
            const scope = city ?? region ?? (country !== "ALL" ? country : null);
            const href = s.href === "/markets" ? s.href : scope ? `${s.href}?scope=${scope}` : s.href;
            return (
              <Link key={s.href} href={href} aria-current={s.label === section ? "page" : undefined}
                className={`flex h-11 items-center rounded-xl px-4 text-[15px] ${s.label === section ? "bg-peacock-tint font-extrabold text-peacock-dark" : "font-semibold text-kohl hover:bg-porcelain"}`}>
                {s.label}
              </Link>
            );
          })}
        </nav>
        <main className="box-border min-w-0 flex-[999_1_560px] p-4 sm:p-8">
          <div className="flex max-w-[1280px] flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
