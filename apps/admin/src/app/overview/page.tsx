"use client";
// AdminHome.html (All countries) and AdminCountry.html (a country, state or
// city): live orders, today's orders and money, delivery times, the states and
// cities, and what needs someone's attention. Each country in its own money.
import Link from "next/link";
import { Suspense } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { StatusPill } from "@/components/console/StatusPill";
import type { MarketStatus } from "@/lib/markets";
import { money, useOverview, useScope, type Action, type OCountry, type Totals } from "@/lib/ops";

function pct(v: number | null) {
  return v == null ? "—" : `${v}%`;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl bg-white p-4">
      <div className="text-[13px] font-semibold text-muted">{label}</div>
      <div className="mt-1 font-display text-[28px] font-semibold tracking-[-0.6px] tabular-nums">{value}</div>
    </div>
  );
}

const ACTION_LINK: Record<string, (scope: string) => string> = {
  rule_approval: (s) => `/pricing?scope=${s}&tab=approvals`,
  kitchen_application: (s) => `/partners?scope=${s}&tab=applications`,
  rider_documents: (s) => `/partners?scope=${s}&tab=riders`,
  waiting_for_rider: (s) => `/operations?scope=${s}&tab=dispatch`,
  late_orders: (s) => `/operations?scope=${s}&tab=attention`,
};

function Actions({ actions, showCountry }: { actions: (Action & { country?: string })[]; showCountry?: boolean }) {
  if (!actions.length) return <p className="text-sm text-muted">Nothing needs action right now.</p>;
  return (
    <ul className="divide-y divide-line">
      {actions.map((a, i) => (
        <li key={i} className="flex items-center gap-3 py-3">
          {showCountry ? <span className="rounded-md bg-line-soft px-1.5 py-0.5 text-[11px] font-extrabold">{a.country}</span> : null}
          <span className={`h-2 w-2 shrink-0 rounded-full ${a.urgent ? "bg-chili" : "bg-kesar"}`} aria-hidden />
          <span className="min-w-0 flex-1"><b>{a.label}</b> <span className="text-sm text-muted">· {a.detail}</span></span>
          <Link href={ACTION_LINK[a.kind]?.(a.scope) ?? "#"} className="h-9 shrink-0 rounded-full border border-line-strong px-4 text-sm font-bold leading-9 hover:border-peacock">
            {a.kind === "rule_approval" ? "Review" : a.kind.includes("rider") || a.kind === "late_orders" ? "Dispatch" : "Open"}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function AllCountries({ countries }: { countries: OCountry[] }) {
  const cities = countries.reduce((n, c) => n + c.states.reduce((m, s) => m + s.cities.length, 0), 0);
  const live = countries.reduce((n, c) => n + c.states.reduce((m, s) => m + s.cities.filter((x) => x.status === "live" || x.status === "beta").length, 0), 0);
  const states = countries.reduce((n, c) => n + c.states.length, 0);
  return (
    <>
      <div>
        <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">All countries</h1>
        <p className="mt-1 text-sm text-muted">
          {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })} · {countries.length} countries · {states} states · {cities} cities ({live} live or in beta) · money stays in each country&apos;s currency
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {countries.map((c) => (
          <section key={c.code} className="flex flex-col gap-4 rounded-2xl bg-white p-6" aria-label={c.name}>
            <div className="flex items-center gap-3">
              <span className="rounded-md bg-peacock-tint px-2 py-1 text-xs font-extrabold text-peacock-dark">{c.code}</span>
              <div className="flex-1"><div className="text-lg font-extrabold">{c.name}</div><div className="text-[13px] text-muted">{c.currency} · {c.tax} · {c.payments} · main zone {c.timezone}</div></div>
              <Link href={`/overview?scope=${c.code}`} className="h-10 rounded-full bg-peacock px-4 text-sm font-extrabold leading-10 text-white">Open {c.code === "US" ? "US" : c.name}</Link>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <MiniStat label="Live orders" value={c.totals.live} />
              <MiniStat label="Orders today" value={c.totals.today.toLocaleString()} />
              <MiniStat label="Median delivery" value={c.totals.median_delivery_min != null ? `${Math.round(c.totals.median_delivery_min)} min` : "—"} />
              <MiniStat label="GMV today" value={money(c.totals.gmv_today, c.currency)} />
            </div>
            <ul className="divide-y divide-line text-sm">
              {c.states.map((s) => (
                <li key={s.code} className="flex items-center gap-2 py-2.5">
                  <b>{s.name}</b>
                  <span className="text-muted">· {s.cities.map((x) => `${x.name} ${x.status}`).join(", ")}</span>
                  <span className="ml-auto font-semibold tabular-nums">{s.totals.today ? `${s.totals.today} orders` : "not live"}</span>
                </li>
              ))}
            </ul>
            {c.needs_action.length ? (
              <Link href={`/overview?scope=${c.code}`} className={`rounded-xl px-4 py-3 text-sm ${c.needs_action.some((a) => a.urgent) ? "bg-danger-tint text-danger-ink" : "bg-kesar-tint text-kesar-ink"}`}>
                <b>{c.needs_action.reduce((n, a) => n + a.count, 0)} need action</b> · {c.needs_action.map((a) => a.label).join(" · ")}
              </Link>
            ) : null}
          </section>
        ))}
      </div>
      <section className="rounded-2xl bg-white p-6" aria-label="Side by side">
        <div className="mb-3 flex items-baseline justify-between"><h2 className="m-0 text-lg font-extrabold">Side by side</h2><span className="text-sm text-muted">Today · local time in each city</span></div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm tabular-nums">
            <thead className="text-[12px] uppercase tracking-wide text-muted">
              <tr><th className="py-2">Country</th><th>Completed</th><th>On time</th><th>Median delivery</th><th>Live</th><th>Kitchens</th><th>Refunds</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {countries.map((c) => (
                <tr key={c.code}>
                  <td className="py-3 font-bold">{c.name}</td><td>{pct(c.totals.completed_pct)}</td><td>{pct(c.totals.on_time_pct)}</td>
                  <td>{c.totals.median_delivery_min != null ? `${Math.round(c.totals.median_delivery_min)} min` : "—"}</td><td>{c.totals.live}</td>
                  <td>{c.states.reduce((n, s) => n + s.cities.reduce((m, x) => m + x.totals.kitchens, 0), 0)}</td><td>{pct(c.totals.refund_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="rounded-2xl bg-white p-6" aria-label="Needs action">
        <h2 className="m-0 mb-2 text-lg font-extrabold">Needs action · all countries</h2>
        <Actions showCountry actions={countries.flatMap((c) => c.needs_action.map((a) => ({ ...a, country: c.code })))} />
      </section>
    </>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-porcelain px-3 py-2.5">
      <div className="text-[12px] font-semibold text-muted">{label}</div>
      <div className="text-xl font-extrabold tabular-nums">{value}</div>
    </div>
  );
}

function Market({ country, scope }: { country: OCountry; scope: string }) {
  const { region, city } = parseScope(scope);
  const states = country.states.filter((s) => !region || s.code === region);
  const one = city ? states.flatMap((s) => s.cities).find((x) => x.code === city) : null;
  const t: Totals = one?.totals ?? (region ? states[0]?.totals : null) ?? country.totals;
  const title = one?.name ?? (region ? states[0]?.name : null) ?? country.name;
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">{title}</h1>
        {one ? <StatusPill status={one.status as MarketStatus} /> : null}
        <p className="w-full text-sm text-muted">
          {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })} · {one ? `times in ${one.timezone}` : "times in each city's own zone"} · amounts in {country.currency}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Live orders" value={t.live} />
        <Stat label="Orders today" value={t.today.toLocaleString()} />
        <Stat label="GMV today" value={money(t.gmv_today, country.currency)} />
        <Stat label="On time" value={pct(t.on_time_pct)} />
      </div>
      <section className="rounded-2xl bg-white p-6" aria-label="States and cities">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="m-0 text-lg font-extrabold">States and cities</h2>
          <Link href={`/markets/${country.code}`} className="text-sm font-bold text-peacock">Markets →</Link>
        </div>
        <table className="w-full text-left text-sm tabular-nums">
          <thead className="text-[12px] uppercase tracking-wide text-muted"><tr><th className="py-2">Name</th><th>Status</th><th>Kitchens</th><th>Orders today</th><th>On time</th><th>Live now</th></tr></thead>
          <tbody className="divide-y divide-line">
            {states.map((s) => [
              <tr key={s.code} className="bg-porcelain/60"><td className="py-3 font-extrabold"><Link href={`/overview?scope=${s.code}`}>{s.name}</Link> <span className="font-normal text-muted">· {s.cities.length} cities</span></td>
                <td className="text-muted">{s.cities.filter((x) => x.status === "live").length} live · {s.cities.filter((x) => x.status === "draft").length} draft</td>
                <td>{s.cities.reduce((n, x) => n + x.totals.kitchens, 0)}</td><td>{s.totals.today}</td><td>{pct(s.totals.on_time_pct)}</td><td>{s.totals.live}</td></tr>,
              ...s.cities.filter((x) => !city || x.code === city).map((x) => (
                <tr key={x.code}><td className="py-3 pl-6"><Link href={`/overview?scope=${x.code}`} className="font-bold hover:text-peacock">{x.name}</Link></td>
                  <td><StatusPill status={x.status as MarketStatus} /></td><td>{x.totals.kitchens}</td><td>{x.totals.today}</td><td>{pct(x.totals.on_time_pct)}</td><td>{x.totals.live}</td></tr>
              )),
            ])}
          </tbody>
        </table>
      </section>
      <section className="rounded-2xl bg-white p-6" aria-label="Needs action">
        <h2 className="m-0 mb-2 text-lg font-extrabold">Needs action · {title}</h2>
        <Actions actions={country.needs_action} />
      </section>
      <section className="rounded-2xl bg-white p-6" aria-label={`${country.name} settings`}>
        <h2 className="m-0 text-lg font-extrabold">{country.name} settings</h2>
        <p className="mb-3 text-sm text-muted">States inherit these, cities inherit from their state — either can override (Markets).</p>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="font-bold">Money and tax</dt><dd className="text-muted">{country.currency} · {country.tax}</dd></div>
          <div><dt className="font-bold">Payments</dt><dd className="text-muted">{country.payments}</dd></div>
          <div><dt className="font-bold">Main time zone</dt><dd className="text-muted">{country.timezone} · each city keeps its own ({[...new Set(country.states.flatMap((s) => s.cities.map((x) => x.timezone)))].join(", ")})</dd></div>
          <div><dt className="font-bold">Compliance</dt><dd className="text-muted">{country.code === "IN" ? "FSSAI licence required for every kitchen" : "Local food permits; sales tax by Stripe Tax"}</dd></div>
        </dl>
      </section>
    </>
  );
}

function OverviewPage() {
  const scope = useScope();
  const { country, region, city } = parseScope(scope);
  const { data, error, isLoading } = useOverview(scope);
  const chosen = data?.countries.find((c) => c.code === country);
  return (
    <ConsoleShell section="Overview" country={country} region={region} city={city} scopeHref={(s) => `/overview?scope=${s}`}>
      {isLoading ? <p className="text-muted">Loading…</p> : null}
      {error ? <p className="text-chili">You can&apos;t see this part of BhojanGo.</p> : null}
      {data && country === "ALL" ? (data.countries.length === 1 ? <Market country={data.countries[0]!} scope={data.countries[0]!.code} /> : <AllCountries countries={data.countries} />) : null}
      {data && chosen ? <Market country={chosen} scope={scope} /> : null}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><OverviewPage /></Suspense>;
}
