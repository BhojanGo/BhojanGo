"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { StatusPill } from "@/components/console/StatusPill";
import { CHECKLIST_LABELS, type CitySummary, type CountrySummary, moneySymbol, useMarkets } from "@/lib/markets";

const LOCALE_NAMES: Record<string, string> = {
  "en-IN": "English",
  "en-US": "English",
  "hi-IN": "हिन्दी",
  "te-IN": "తెలుగు",
};
const METHOD_NAMES: Record<string, string> = { upi: "UPI", card: "cards", wallet: "wallets", apple_pay: "Apple Pay", google_pay: "Google Pay" };

function setupProgress(c: CitySummary) {
  const done = Object.values(c.launch_checklist).filter(Boolean).length;
  return { done, total: Object.keys(c.launch_checklist).length };
}

function SettingsCards({ country }: { country: CountrySummary }) {
  const s = country.settings as Record<string, unknown>;
  const methods = (s.payment_methods as string[] | undefined)?.map((m) => METHOD_NAMES[m] ?? m).join(", ");
  const compliance = [s.fssai_required ? "FSSAI required" : null, s.sms_dlt_required ? "DLT SMS" : null].filter(Boolean).join(" · ");
  const cards = [
    { title: "Money and tax", value: `${country.currency} · ${country.tax_regime === "gst" ? "GST" : "Stripe Tax"}` },
    { title: "Payments", value: [country.payment_providers.map((p) => p[0].toUpperCase() + p.slice(1)).join(", "), methods].filter(Boolean).join(" · ") },
    { title: "Languages", value: country.locales.map((l) => LOCALE_NAMES[l] ?? l).join(" · ") },
    { title: "Compliance", value: compliance || "No extra rules" },
    { title: "Time and units", value: `${country.timezone} · ${country.distance_unit}` },
  ];
  return (
    <section aria-label={`${country.name} settings`} className="rounded-2xl border border-line bg-white p-6">
      <h2 className="m-0 text-[17px] font-extrabold">{country.name} settings</h2>
      <p className="mt-1 text-[13px] text-muted">States inherit these, cities inherit from their state; either can override.</p>
      <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
        {cards.map((c) => (
          <div key={c.title} className="rounded-xl border border-line-soft p-4">
            <div className="text-[13px] font-semibold text-muted">{c.title}</div>
            <div className="mt-1 font-bold">{c.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function CountryView() {
  const { country: code } = useParams<{ country: string }>();
  const state = useSearchParams().get("state");
  const { data: markets, isLoading } = useMarkets();
  const country = markets?.find((c) => c.code === code);
  const regions = country?.regions.filter((r) => !state || r.code === state) ?? [];
  const cities = country?.regions.flatMap((r) => r.cities) ?? [];
  const tzShort = country?.timezone === "Asia/Kolkata" ? "IST" : country?.timezone;

  return (
    <ConsoleShell section="Markets" country={code} region={state}>
      {isLoading && <p className="text-muted">Loading…</p>}
      {!isLoading && !country && (
        <p role="alert" className="rounded-xl bg-danger-tint p-4 text-danger-ink">
          You don&apos;t have access to this country, or it doesn&apos;t exist.
        </p>
      )}
      {country && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">{country.name}</h1>
            <StatusPill status={country.status} />
            <span className="basis-full text-sm text-muted">
              Times in {tzShort} · amounts in {moneySymbol(country.currency).trim()} · {cities.length} cities,{" "}
              {cities.filter((c) => c.status === "live" || c.status === "beta").length} open
            </span>
          </div>

          <section aria-label="States and cities" className="rounded-2xl border border-line bg-white p-6">
            <h2 className="m-0 mb-2 text-[17px] font-extrabold">States and cities</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm tabular-nums">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-[0.6px] text-muted">
                    <th className="py-3 font-bold">Name</th>
                    <th className="font-bold">Status</th>
                    <th className="text-right font-bold">Zones open</th>
                    <th className="pl-6 font-bold">Setup</th>
                  </tr>
                </thead>
                <tbody>
                  {regions.map((r) => (
                    <RegionRows key={r.code} countryCode={country.code} region={r} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <SettingsCards country={country} />
        </>
      )}
    </ConsoleShell>
  );
}

function RegionRows({ countryCode, region }: { countryCode: string; region: CountrySummary["regions"][number] }) {
  const open = region.cities.filter((c) => c.status === "live" || c.status === "beta").length;
  return (
    <>
      <tr className="border-t border-line-soft bg-[#FAFBFB]">
        <td className="py-3 font-bold">
          {region.name} <span className="font-normal text-muted">· {region.cities.length} {region.cities.length === 1 ? "city" : "cities"}</span>
        </td>
        <td><StatusPill status={region.status} /></td>
        <td className="text-right text-muted">{open} open</td>
        <td />
      </tr>
      {region.cities.map((c) => {
        const p = setupProgress(c);
        const missing = Object.entries(c.launch_checklist).filter(([, ok]) => !ok).map(([k]) => CHECKLIST_LABELS[k] ?? k);
        return (
          <tr key={c.code} className="border-t border-line-soft">
            <td className="py-3 pl-5">
              <Link href={`/markets/${countryCode}/${c.code}`} className="font-bold text-peacock hover:text-peacock-dark">
                {c.name}
              </Link>
              <span className="text-muted"> · {c.zone_count ? `${c.zone_count} zones` : "zones not drawn"}</span>
            </td>
            <td><StatusPill status={c.status} /></td>
            <td className="text-right">{c.live_zone_count}</td>
            <td className="pl-6">
              {p.done === p.total ? (
                <span className="font-semibold text-peacock-dark">Ready</span>
              ) : (
                <span title={`Still needed: ${missing.join(", ")}`} className="text-muted">
                  setup {p.done} of {p.total}
                </span>
              )}
            </td>
          </tr>
        );
      })}
    </>
  );
}

export default function CountryPage() {
  return (
    <Suspense fallback={null}>
      <CountryView />
    </Suspense>
  );
}
