"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { StatusPill } from "@/components/console/StatusPill";
import { type CountrySummary, useAdminMe, useMarkets } from "@/lib/markets";

const TAX: Record<string, string> = { gst: "GST", us_sales_tax: "Stripe Tax" };

function countrySubtitle(c: CountrySummary) {
  const providers = c.payment_providers.map((p) => p[0].toUpperCase() + p.slice(1)).join(", ");
  return `${c.currency} · ${TAX[c.tax_regime] ?? c.tax_regime} · ${providers} · ${c.timezone}`;
}

function stateLine(cities: CountrySummary["regions"][number]["cities"]) {
  if (!cities.length) return "no cities yet";
  const open = cities.filter((c) => c.status === "live" || c.status === "beta");
  if (!open.length) return `${cities.length} ${cities.length === 1 ? "city" : "cities"} in setup`;
  return cities.map((c) => `${c.name} ${c.status}`).join(", ");
}

/** All countries overview (design board: AdminHome). Super admins only; others land on their country. */
export default function AllCountriesPage() {
  const { data: markets, isLoading, error } = useMarkets();
  const { data: me } = useAdminMe();
  const router = useRouter();
  const isGlobal = (me?.permissions["markets.view"] ?? []).includes("*");

  useEffect(() => {
    if (me && !isGlobal && markets?.length) router.replace(`/markets/${markets[0].code}`);
  }, [me, isGlobal, markets, router]);

  const regions = markets?.flatMap((c) => c.regions) ?? [];
  const cities = regions.flatMap((r) => r.cities);
  const open = cities.filter((c) => c.status === "live" || c.status === "beta");

  return (
    <ConsoleShell section="Markets" country="ALL">
      <div>
        <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">All countries</h1>
        <p className="mt-1 text-sm text-muted">
          {markets
            ? `${markets.length} countries · ${regions.length} states · ${cities.length} cities (${open.length} live or in beta) · money stays in each country's currency`
            : "Loading…"}
        </p>
      </div>

      {error ? <p role="alert" className="rounded-xl bg-danger-tint p-4 text-danger-ink">Couldn&apos;t load markets.</p> : null}
      {isLoading ? <p className="text-muted">Loading markets…</p> : null}

      <div className="grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))]">
        {markets?.map((c) => {
          const cs = c.regions.flatMap((r) => r.cities);
          const zones = cs.reduce((n, x) => n + x.zone_count, 0);
          const openZones = cs.reduce((n, x) => n + x.live_zone_count, 0);
          const setup = cs.filter((x) => x.status === "draft").length;
          return (
            <article key={c.code} className="flex flex-col gap-5 rounded-2xl border border-line bg-white p-6 tabular-nums">
              <div className="flex items-center gap-3">
                <span className="rounded-lg bg-line-soft px-2 py-1 text-[13px] font-extrabold">{c.code}</span>
                <div className="flex-grow">
                  <div className="font-display text-2xl font-semibold tracking-[-0.4px]">{c.name}</div>
                  <div className="text-[13px] text-muted">{countrySubtitle(c)}</div>
                </div>
                <Link href={`/markets/${c.code}`} className="flex h-11 items-center rounded-full bg-peacock px-5 text-sm font-extrabold text-white hover:bg-peacock-dark">
                  Open {c.code === "US" ? "US" : c.name}
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div><div className="text-xs text-muted">Status</div><div className="mt-1"><StatusPill status={c.status} /></div></div>
                <div><div className="text-xs text-muted">Cities open</div><div className="text-2xl font-extrabold">{cs.filter((x) => x.status === "live" || x.status === "beta").length}</div></div>
                <div><div className="text-xs text-muted">Zones open</div><div className="text-2xl font-extrabold">{openZones}<span className="text-sm font-semibold text-muted"> / {zones}</span></div></div>
                <div><div className="text-xs text-muted">In setup</div><div className="text-2xl font-extrabold">{setup}</div></div>
              </div>
              <div className="border-t border-line-soft">
                {c.regions.map((r) => (
                  <Link key={r.code} href={`/markets/${c.code}?state=${r.code}`} className="flex items-center gap-3 border-b border-line-soft py-3 text-sm text-kohl last:border-b-0">
                    <span className="flex-grow">
                      <b>{r.name}</b> <span className="text-muted">· {stateLine(r.cities)}</span>
                    </span>
                    <StatusPill status={r.status} />
                  </Link>
                ))}
              </div>
              {setup > 0 && (
                <div className="flex justify-between rounded-xl bg-kesar-tint px-4 py-3 text-sm text-kesar-ink">
                  <span><b>{setup} {setup === 1 ? "city" : "cities"} in setup</b> · see what each still needs</span>
                  <Link href={`/markets/${c.code}`} className="font-bold text-kesar-ink">View</Link>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </ConsoleShell>
  );
}
