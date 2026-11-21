"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Suspense, useState } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { DeliveryPartners } from "@/components/markets/DeliveryPartners";
import { HeroDish } from "@/components/markets/HeroDish";
import { LegalEntity } from "@/components/markets/LegalEntity";
import { OfferCeiling } from "@/components/markets/OfferCeiling";
import { PaymentMethods } from "@/components/markets/PaymentMethods";
import { KitchenDocuments } from "@/components/markets/KitchenDocuments";
import { PayoutProvider } from "@/components/markets/PayoutProvider";
import { StatusPill } from "@/components/console/StatusPill";
import {
  CHECKLIST_LABELS,
  type CitySummary,
  type CountrySummary,
  LOCALE_NAMES,
  apiError,
  can,
  marketsApi,
  moneySymbol,
  payoutLabel,
  useAdminMe,
  useDemand,
  useMarkets,
  WEBSITE_LABELS,
} from "@/lib/markets";
import { count } from "@/lib/count";
import { zoneLabel } from "@/lib/zone";
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
    { title: "Payouts", value: payoutLabel(country.payout_provider) },
    { title: "Languages", value: country.locales.map((l) => LOCALE_NAMES[l] ?? l).join(" · ") },
    { title: "Compliance", value: compliance || "No extra rules" },
    { title: "Time and units", value: `New cities: ${country.timezone} · payouts: ${country.payout_timezone || country.timezone} · ${country.distance_unit}` },
  ];
  return (
    <section aria-label={`${country.name} settings`} className="rounded-2xl border border-line bg-white p-6">
      <h2 className="m-0 text-h3">{country.name} settings</h2>
      <p className="mt-1 text-small text-muted">States inherit these, cities inherit from their state; either can override.</p>
      <div className="mt-4 grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
        {cards.map((c) => (
          <div key={c.title} className="rounded-xl border border-line-soft p-4">
            <div className="text-label text-muted">{c.title}</div>
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
  // R27: each city keeps its own zone; one zone for the country only when all its cities share it.
  const zones = [...new Set(country?.regions.flatMap((r) => r.cities.map((c) => c.timezone || r.timezone || country.timezone)) ?? [])];
  const tzShort = zones.length === 1 ? zoneLabel(zones[0]).replace(/^\((.*)\)$/, "$1") : null;

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
            <h1 className="m-0 text-h1">{country.name}</h1>
            <StatusPill status={country.status} />
            <span className="basis-full text-small text-muted">
              {tzShort ? `Times in ${tzShort}` : "Times in each city's own zone"} · amounts in {moneySymbol(country.currency).trim()} · {count(cities.length, "city", "cities")},{" "}
              {cities.filter((c) => c.status === "live" || c.status === "beta").length} open
            </span>
          </div>

          <section aria-label="States and cities" className="rounded-2xl border border-line bg-white p-6">
            <h2 className="m-0 mb-2 text-h3">States and cities</h2>
            <div className="table-scroll">
              <table className="w-full min-w-[640px] border-collapse text-small tabular-nums">
                <thead>
                  <tr className="text-left text-caption text-muted">
                    <th className="py-3 font-bold">Name</th>
                    <th className="font-bold">Status</th>
                    <th className="text-right font-bold">Zones open</th>
                    <th className="pl-6 font-bold">Setup</th>
                    <th className="text-right font-bold">Notify me</th>
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

          <AddCity country={country} />
          <DemandCard countryCode={country.code} />
          <SettingsCards country={country} />
          <PayoutProvider country={country} />
          <LegalEntity country={country} />
          <PaymentMethods country={country} />
          <OfferCeiling level="country" code={country.code}
            name={country.name} currency={country.currency} settings={country.settings} parents={[]} />
          <HeroDish country={country} />
          <KitchenDocuments key={JSON.stringify(country.settings.kitchen_documents ?? null)} country={country} />
          <DeliveryPartners key={country.code} country={country} />
        </>
      )}
    </ConsoleShell>
  );
}

/** R20: a state with no short code (made before the field existed) can't show "City, ST": set it here. */
function ShortCodeNeeded({ region }: { region: CountrySummary["regions"][number] }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(region.code.split("-")[1] ?? "");
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <form className="mt-1 flex flex-wrap items-center gap-2 font-normal" data-testid={`short-code-needed-${region.code}`}
      onSubmit={(e) => {
        e.preventDefault();
        void marketsApi.updateRegion(region.code, { short_code: value.trim().toUpperCase() })
          .then(() => qc.invalidateQueries({ queryKey: ["markets"] }), (err) => setProblem(apiError(err)));
      }}>
      <span className="text-caption text-chili">Short code needed</span>
      <input aria-label={`${region.name} short code`} required pattern="[A-Z0-9]{1,4}" value={value}
        onChange={(e) => setValue(e.target.value.toUpperCase())} className="h-8 w-16 rounded border border-line px-2 text-small" />
      <button type="submit" className="h-8 rounded-full bg-peacock px-3 text-caption text-white">Save</button>
      {problem ? <span role="alert" className="text-caption text-chili">{problem}</span> : null}
    </form>
  );
}

function RegionRows({ countryCode, region }: { countryCode: string; region: CountrySummary["regions"][number] }) {
  const open = region.cities.filter((c) => c.status === "live" || c.status === "beta").length;
  return (
    <>
      <tr className="border-t border-line-soft bg-[#FAFBFB]">
        <td className="py-3 font-bold">
          {region.name} <span className="font-normal text-muted">· {region.cities.length} {region.cities.length === 1 ? "city" : "cities"}</span>
          {region.short_code
            ? <span data-testid={`short-code-${region.code}`} className="ml-2 rounded bg-line-soft px-1.5 py-0.5 text-caption font-normal">{region.short_code}</span>
            : <ShortCodeNeeded region={region} />}
        </td>
        <td><StatusPill status={region.status} /></td>
        <td className="text-right text-muted">{open} open</td>
        <td />
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
            <td><StatusPill status={c.status} />{c.website ? <span data-testid={`website-${c.code}`} className="ml-2 whitespace-nowrap text-caption text-muted">{WEBSITE_LABELS[c.website]}</span> : null}</td>
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
            <td className="text-right">{c.waitlist || "–"}</td>
          </tr>
        );
      })}
    </>
  );
}

/** Code part from a name: "Nampa" -> "NMP", "Twin Falls" -> "TFA" (editable). */
function shortCode(name: string, len: number): string {
  const words = name.toUpperCase().replace(/[^A-Z ]/g, "").split(" ").filter(Boolean);
  if (!words.length) return "";
  const first = words[0];
  const pick = words.length > 1 ? words.map((w) => w[0]).join("") + words[words.length - 1].slice(1) : first[0] + first.slice(1).replace(/[AEIOU]/g, "");
  return pick.slice(0, len).padEnd(Math.min(len, 2), "X");
}

function AddCity({ country }: { country: CountrySummary }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ region: country.regions[0]?.code ?? "new", regionName: "", regionCode: "", regionShort: "", name: "", code: "", lat: "", lng: "", timezone: "" });
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!can(me, "markets.edit", country.code)) return null;
  const newState = f.region === "new";
  const regionCode = newState ? f.regionCode || (f.regionName ? `${country.code}-${shortCode(f.regionName, 2)}` : "") : f.region;
  const cityCode = f.code || (f.name && regionCode ? `${regionCode}-${shortCode(f.name, 3)}` : "");
  // R20: the state's short code ("ID") is required: for a new state, or an existing one that has none yet
  const picked = country.regions.find((r) => r.code === f.region);
  const needsShort = newState || !picked?.short_code;
  const regionShort = f.regionShort || regionCode.split("-")[1] || "";

  async function submit() {
    setBusy(true);
    setProblem(null);
    try {
      if (newState) await marketsApi.createRegion(country.code, { code: regionCode, name: f.regionName.trim(), short_code: regionShort, timezone: f.timezone || null });
      else if (needsShort) await marketsApi.updateRegion(regionCode, { short_code: regionShort });
      await marketsApi.createCity(regionCode, {
        code: cityCode,
        name: f.name.trim(),
        center_lat: Number(f.lat),
        center_lng: Number(f.lng),
        timezone: f.timezone || null,
      });
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setOpen(false);
      setF({ ...f, name: "", code: "", lat: "", lng: "" });
    } catch (e) {
      setProblem(apiError(e));
    } finally {
      setBusy(false);
    }
  }
  const field = "mt-1 block w-full rounded-lg border border-line px-3 py-2 text-small text-kohl";
  return (
    <section aria-label="Add a city" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Add a city</h2>
        {!open && (
          <button type="button" onClick={() => setOpen(true)} className="h-10 rounded-full bg-peacock px-4 text-label text-white">
            New city
          </button>
        )}
      </div>
      <p className="mt-1 text-small text-muted">
        A new city starts as a draft. &ldquo;Coming soon&rdquo; lists it on the website and collects sign-ups; draw a zone, set its hours and
        open it to take orders. The website picks it up by itself.
      </p>
      {open && (
        <form
          className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label className="text-small text-muted">
            State
            <select value={f.region} onChange={(e) => setF({ ...f, region: e.target.value })} className={field}>
              {country.regions.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.name}
                </option>
              ))}
              <option value="new">A new state…</option>
            </select>
          </label>
          {newState && (
            <>
              <label className="text-small text-muted">
                State name
                <input required minLength={2} value={f.regionName} onChange={(e) => setF({ ...f, regionName: e.target.value })} className={field} />
              </label>
              <label className="text-small text-muted">
                State code
                <input
                  required
                  pattern="[A-Z]{2}-[A-Z0-9]{1,3}"
                  value={regionCode}
                  onChange={(e) => setF({ ...f, regionCode: e.target.value.toUpperCase() })}
                  className={field}
                />
              </label>
            </>
          )}
          {needsShort && (
            <label className="text-small text-muted">
              State short code (shown as &ldquo;City, {regionShort || "ST"}&rdquo;)
              <input
                required
                aria-label="State short code"
                pattern="[A-Z0-9]{1,4}"
                value={regionShort}
                onChange={(e) => setF({ ...f, regionShort: e.target.value.toUpperCase() })}
                className={field}
              />
            </label>
          )}
          <label className="text-small text-muted">
            City name
            <input required minLength={2} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            City code
            <input
              required
              pattern="[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,4}"
              value={cityCode}
              onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })}
              className={field}
            />
          </label>
          <label className="text-small text-muted">
            Centre latitude
            <input required inputMode="decimal" value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Centre longitude
            <input required inputMode="decimal" value={f.lng} onChange={(e) => setF({ ...f, lng: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Time zone (empty: inherited)
            <input value={f.timezone} placeholder={country.timezone} onChange={(e) => setF({ ...f, timezone: e.target.value })} className={field} />
          </label>
          <div className="flex items-end gap-2">
            <button type="submit" disabled={busy} className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50">
              Create city
            </button>
            <button type="button" onClick={() => setOpen(false)} className="h-10 rounded-full px-3 text-label text-muted">
              Cancel
            </button>
          </div>
          {problem && (
            <p role="alert" className="col-span-full rounded-xl bg-danger-tint p-3 text-small text-danger-ink">
              {problem}
            </p>
          )}
        </form>
      )}
    </section>
  );
}

function DemandCard({ countryCode }: { countryCode: string }) {
  const { data } = useDemand();
  const cities = (data?.cities ?? []).filter((c) => c.country === countryCode);
  const suggested = data?.suggested ?? [];
  return (
    <section aria-label="Notify me demand" className="rounded-2xl border border-line bg-white p-6">
      <h2 className="m-0 text-h3">Notify me demand</h2>
      <p className="mt-1 text-small text-muted">
        Sign-ups from the website: coming-soon cities, addresses outside every zone, and cities visitors suggested.
      </p>
      {cities.length === 0 && suggested.length === 0 ? (
        <p className="mt-3 text-small text-muted">No sign-ups yet.</p>
      ) : (
        <div className="mt-3 grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]">
          <div className="table-scroll"><table className="w-full border-collapse text-small tabular-nums">
            <thead>
              <tr className="text-left text-caption text-muted">
                <th className="py-2 font-bold">City</th>
                <th className="text-right font-bold">Sign-ups</th>
                <th className="text-right font-bold">Can email</th>
              </tr>
            </thead>
            <tbody>
              {cities.map((c) => (
                <tr key={c.city_code} className="border-t border-line-soft">
                  <td className="py-2 font-semibold">{c.city_name}</td>
                  <td className="text-right">{c.signups}</td>
                  <td className="text-right text-muted">{c.with_consent}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
          {suggested.length > 0 && (
            <div>
              <div className="text-caption text-muted">Suggested (not in Markets)</div>
              <ul className="mt-2 space-y-1 text-small">
                {suggested.map((s) => (
                  <li key={s.text} className="flex justify-between gap-3 border-t border-line-soft py-1">
                    <span className="capitalize">{s.text}</span>
                    <span className="tabular-nums text-muted">{s.signups}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default function CountryPage() {
  return (
    <Suspense fallback={null}>
      <CountryView />
    </Suspense>
  );
}
