"use client";

/**
 * The new admin console frame from the design board: header, country tabs,
 * state chips with a searchable city picker, and the section nav. Markets (P6)
 * is the first section on it; P21 moves the rest of the console over.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { CityPicker } from "@/components/console/CityPicker";
import { ROLE_LABELS, useAdminMe, useMarkets } from "@/lib/markets";
import { useAdminAuth, useAuthHydrated } from "@/store/auth";

const SECTIONS = [
  { href: "/dashboard", label: "Home" },
  { href: "/orders", label: "Operations" },
  { href: "/restaurants", label: "Partners" },
  { href: "/users", label: "Customers" },
  { href: "/pricing", label: "Pricing & Rules" },
  { href: "/markets", label: "Markets" },
  { href: "/payments", label: "Finance" },
  { href: "/analytics", label: "Reports" },
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

export function ConsoleShell({
  section,
  country,
  region,
  city,
  cityHref,
  countryHref,
  children,
}: {
  section: string;
  /** Where picking a city goes; defaults to that city's Markets page. */
  cityHref?: (country: string, city: string) => string;
  /** Where a country tab goes; defaults to that country's Markets page. Pages
      that set this show only the city picker (no state chips). */
  countryHref?: (country: string) => string;
  /** "ALL" for the all-countries view, else a country code */
  country: string;
  region?: string | null;
  city?: string | null;
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
  const isGlobal = (me?.permissions["markets.view"] ?? []).includes("*");
  const role = me?.assignments[0];
  const initials = (user?.full_name ?? "?").split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="flex min-h-screen flex-col bg-porcelain font-body text-kohl">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 bg-white px-4 py-3 sm:px-8">
        <Logo />
        <div className="ml-auto flex items-center gap-2.5 text-sm">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-peacock-tint text-xs font-extrabold text-peacock-dark">
            {initials}
          </span>
          <span>
            {user?.full_name}
            {role ? ` · ${ROLE_LABELS[role.role] ?? role.role}${role.scope !== "*" ? ` (${role.scope})` : ""}` : ""}
          </span>
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="ml-2 h-9 rounded-full px-3 font-semibold text-peacock hover:bg-peacock-wash"
          >
            Sign out
          </button>
        </div>
      </header>

      <nav aria-label="Country" className="flex flex-wrap gap-1 overflow-x-auto border-b border-line bg-white px-4 sm:px-8">
        {isGlobal && (
          <Link
            href="/markets"
            aria-current={country === "ALL" ? "page" : undefined}
            className={`box-border flex h-[52px] items-center border-b-[3px] px-4 text-[15px] ${
              country === "ALL" ? "border-peacock font-extrabold text-peacock-dark" : "border-transparent font-semibold text-muted"
            }`}
          >
            All countries
          </Link>
        )}
        {markets?.map((c) => (
          <Link
            key={c.code}
            href={countryHref ? countryHref(c.code) : `/markets/${c.code}`}
            aria-current={c.code === country ? "page" : undefined}
            className={`box-border flex h-[52px] items-center gap-2 border-b-[3px] px-4 text-[15px] ${
              c.code === country ? "border-peacock font-extrabold text-peacock-dark" : "border-transparent font-semibold text-muted"
            }`}
          >
            <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-extrabold ${c.code === country ? "bg-peacock-tint text-peacock-dark" : "bg-line-soft text-kohl"}`}>
              {c.code}
            </span>
            {c.name}
          </Link>
        ))}
      </nav>

      {current && (
        <nav aria-label={`State and city in ${current.name}`} className="flex flex-wrap items-center gap-2 border-b border-line bg-[#FAFBFB] px-4 py-2.5 sm:px-8">
          {!countryHref && <span className="mr-1 text-[13px] font-bold text-muted">State</span>}
          {!countryHref && <Link
            href={`/markets/${current.code}`}
            aria-current={!region && !city ? "true" : undefined}
            className={`flex h-9 items-center rounded-full px-3.5 text-sm ${
              !region && !city ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold text-kohl"
            }`}
          >
            All states
          </Link>}
          {!countryHref && current.regions.map((r) => {
            const on = region === r.code;
            return (
              <Link
                key={r.code}
                href={`/markets/${current.code}?state=${r.code}`}
                aria-current={on ? "true" : undefined}
                className={`flex h-9 items-center gap-2 rounded-full px-3.5 text-sm ${
                  on ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold text-kohl"
                }`}
              >
                {r.name} <span className={`text-xs ${on ? "text-[#A9B8BA]" : "text-muted"}`}>{r.cities.length}</span>
              </Link>
            );
          })}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[13px] font-bold text-muted">City</span>
            <CityPicker
              country={current}
              value={city ?? null}
              onChange={(code) => router.push(cityHref ? cityHref(current.code, code) : `/markets/${current.code}/${code}`)}
            />
          </div>
        </nav>
      )}

      <div className="flex flex-grow flex-wrap">
        <nav aria-label="Admin sections" className="box-border flex flex-[1_1_248px] flex-col gap-1 border-r border-line bg-white px-4 py-6">
          {SECTIONS.map((s) => (
            <Link
              key={s.href}
              href={s.href}
              aria-current={s.label === section ? "page" : undefined}
              className={`flex h-11 items-center rounded-xl px-4 text-[15px] ${
                s.label === section ? "bg-peacock-tint font-extrabold text-peacock-dark" : "font-semibold text-kohl hover:bg-porcelain"
              }`}
            >
              {s.label}
            </Link>
          ))}
        </nav>
        <main className="box-border min-w-0 flex-[999_1_560px] p-4 sm:p-8">
          <div className="flex max-w-[1280px] flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
