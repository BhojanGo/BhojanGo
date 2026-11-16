"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { StatusPill } from "@/components/console/StatusPill";
import {
  apiError,
  can,
  type CountryCreate,
  type CountrySummary,
  marketsApi,
  PAYMENT_PROVIDERS,
  PAYOUT_PROVIDERS,
  type PayoutProviderName,
  TAX_REGIMES,
  useAdminMe,
  useMarkets,
} from "@/lib/markets";

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

const EMPTY = { code: "", name: "", currency: "", locales: "", timezone: "", distance_unit: "km", phone_code: "+", payment_providers: [] as string[], tax_regime: "gst", payout_provider: "none" as PayoutProviderName };

/** Super admins add a country (a draft); then its states, cities and zones, and it
 * opens from its own page. Sign-up, phone codes and kitchens' currency follow it
 * (backend markets/service/countries.py), so a new country needs no code change. */
function NewCountry() {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState(EMPTY);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!can(me, "markets.edit", "*")) return null;

  async function submit() {
    setBusy(true);
    setProblem(null);
    const body: CountryCreate = {
      code: f.code.trim().toUpperCase(),
      name: f.name.trim(),
      currency: f.currency.trim().toUpperCase(),
      locales: f.locales.split(",").map((l) => l.trim()).filter(Boolean),
      timezone: f.timezone.trim(),
      distance_unit: f.distance_unit === "mi" ? "mi" : "km",
      phone_code: f.phone_code.trim(),
      payment_providers: f.payment_providers,
      tax_regime: f.tax_regime,
      payout_provider: f.payout_provider,
    };
    try {
      await marketsApi.createCountry(body);
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setOpen(false);
      setF(EMPTY);
      router.push(`/markets/${body.code}`);
    } catch (e) {
      setProblem(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  const field = "mt-1 block w-full rounded-lg border border-line px-3 py-2 text-small text-kohl";
  const toggle = (p: string) =>
    setF({ ...f, payment_providers: f.payment_providers.includes(p) ? f.payment_providers.filter((x) => x !== p) : [...f.payment_providers, p] });
  return (
    <section aria-label="Add a country" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Add a country</h2>
        {!open && (
          <button type="button" onClick={() => setOpen(true)} className="h-10 rounded-full bg-peacock px-4 text-label text-white">
            New country
          </button>
        )}
      </div>
      <p className="mt-1 text-small text-muted">
        A new country starts as a draft: nobody can sign up or open a kitchen there yet. Add its states, cities and zones, then
        open it. Its currency, phone code and tax regime apply to every state and city in it; it opens only once it has a payout
        provider (who pays its kitchens and riders).
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
            Country code (ISO, 2 letters)
            <input required pattern="[A-Za-z]{2}" maxLength={2} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} className={field} />
          </label>
          <label className="text-small text-muted">
            Name
            <input required minLength={2} maxLength={100} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Currency (ISO, 3 letters)
            <input required pattern="[A-Za-z]{3}" maxLength={3} value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value.toUpperCase() })} className={field} />
          </label>
          <label className="text-small text-muted">
            Languages (comma separated, e.g. en-GB, cy-GB)
            <input required value={f.locales} onChange={(e) => setF({ ...f, locales: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Time zone (IANA, e.g. Europe/London)
            <input required value={f.timezone} onChange={(e) => setF({ ...f, timezone: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Distance
            <select value={f.distance_unit} onChange={(e) => setF({ ...f, distance_unit: e.target.value })} className={field}>
              <option value="km">Kilometres</option>
              <option value="mi">Miles</option>
            </select>
          </label>
          <label className="text-small text-muted">
            Phone code
            <input required pattern="\+[0-9]{1,4}" maxLength={5} value={f.phone_code} onChange={(e) => setF({ ...f, phone_code: e.target.value })} className={field} />
          </label>
          <label className="text-small text-muted">
            Tax regime
            <select value={f.tax_regime} onChange={(e) => setF({ ...f, tax_regime: e.target.value })} className={field}>
              {TAX_REGIMES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-small text-muted">
            Payout provider
            <select
              value={f.payout_provider}
              onChange={(e) => setF({ ...f, payout_provider: e.target.value as PayoutProviderName })}
              className={field}
            >
              {PAYOUT_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="text-small text-muted">
            <legend>Payment providers</legend>
            <div className="mt-2 flex gap-4">
              {PAYMENT_PROVIDERS.map((p) => (
                <label key={p} className="flex items-center gap-2 text-small text-kohl">
                  <input type="checkbox" checked={f.payment_providers.includes(p)} onChange={() => toggle(p)} />
                  {p[0].toUpperCase() + p.slice(1)}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex items-end gap-2">
            <button
              type="submit"
              disabled={busy || f.payment_providers.length === 0}
              className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50"
            >
              Create country
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
        <h1 className="m-0 text-h1">All countries</h1>
        <p className="mt-1 text-small text-muted">
          {markets
            ? `${markets.length} countries · ${regions.length} states · ${cities.length} cities (${open.length} live or in beta) · money stays in each country's currency`
            : "Loading…"}
        </p>
      </div>

      {error ? <p role="alert" className="rounded-xl bg-danger-tint p-4 text-danger-ink">Couldn&apos;t load markets.</p> : null}
      {isLoading ? <p className="text-muted">Loading markets…</p> : null}

      <NewCountry />

      <div className="grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))]">
        {markets?.map((c) => {
          const cs = c.regions.flatMap((r) => r.cities);
          const zones = cs.reduce((n, x) => n + x.zone_count, 0);
          const openZones = cs.reduce((n, x) => n + x.live_zone_count, 0);
          const setup = cs.filter((x) => x.status === "draft").length;
          return (
            <article key={c.code} className="flex flex-col gap-5 rounded-2xl border border-line bg-white p-6 tabular-nums">
              <div className="flex items-center gap-3">
                <span className="rounded-lg bg-line-soft px-2 py-1 text-label">{c.code}</span>
                <div className="flex-grow">
                  <div className="text-h2">{c.name}</div>
                  <div className="text-small text-muted">{countrySubtitle(c)}</div>
                </div>
                <Link href={`/markets/${c.code}`} className="flex h-11 items-center rounded-full bg-peacock px-5 text-label text-white hover:bg-peacock-dark">
                  Open {c.code === "US" ? "US" : c.name}
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div><div className="text-small text-muted">Status</div><div className="mt-1"><StatusPill status={c.status} /></div></div>
                <div><div className="text-small text-muted">Cities open</div><div className="text-h2">{cs.filter((x) => x.status === "live" || x.status === "beta").length}</div></div>
                <div><div className="text-small text-muted">Zones open</div><div className="text-h2">{openZones}<span className="text-label text-muted"> / {zones}</span></div></div>
                <div><div className="text-small text-muted">In setup</div><div className="text-h2">{setup}</div></div>
              </div>
              <div className="border-t border-line-soft">
                {c.regions.map((r) => (
                  <Link key={r.code} href={`/markets/${c.code}?state=${r.code}`} className="flex items-center gap-3 border-b border-line-soft py-3 text-small text-kohl last:border-b-0">
                    <span className="flex-grow">
                      <b>{r.name}</b> <span className="text-muted">· {stateLine(r.cities)}</span>
                    </span>
                    <StatusPill status={r.status} />
                  </Link>
                ))}
              </div>
              {setup > 0 && (
                <div className="flex justify-between rounded-xl bg-kesar-tint px-4 py-3 text-small text-kesar-ink">
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
