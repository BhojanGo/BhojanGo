// "Add your kitchen" (R8 F7): the landing page for kitchen partners, not a sign-in
// wall. Everything it promises is data: commission from the live rules, payouts from
// the payout_schedule rule, cities and documents from Markets (GET /kitchens/terms),
// and a real bill from the pricing engine (GET /pricing/example). The country comes
// from the visitor's location (address, chosen city, IP hint), never from the code.
// The application itself (account, then the steps) is the client part, ApplyPanel.
import type { Metadata } from "next";

import { FairBill } from "@/components/FairBill";
import { flatCities } from "@/components/discover/places";
import { money } from "@/lib/format";
import { commissionSummary } from "@/lib/kitchenJoin";
import { getContext } from "@/lib/prefs";
import { exampleBill, kitchenTerms, SITE } from "@/lib/server";
import { ApplyPanel, HeroAction } from "./ApplyPanel";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("kitchen_join.meta_title"), description: t("kitchen_join.meta_description"), alternates: { canonical: `${SITE}/partner` } };
}

const PAGE = "container-page";
const HERO = "kitchen-cook";

export default async function Partner() {
  const { t, country, city: here, language, formatLocale, directory: dir } = await getContext();
  const billCity = here?.status === "live" ? here : flatCities(dir).find((c) => c.country === country?.code && c.status === "live") ?? null;
  const [terms, bill] = await Promise.all([
    country ? kitchenTerms(country.code, language) : Promise.resolve(null),
    billCity ? exampleBill(billCity.code) : Promise.resolve(null),
  ]);
  const commission = commissionSummary(terms, here?.code);
  const fmtMoney = (v: string | number) => money(v, terms?.currency ?? country?.currency ?? "USD", formatLocale, { whole: true });
  const pct = (n: number) => new Intl.NumberFormat(formatLocale, { maximumFractionDigits: 1 }).format(n);
  const weekly = (terms?.payout.frequency ?? "weekly") === "weekly";
  const openCities = terms?.cities.length ?? 0;

  const commissionLines: string[] =
    commission.kind === "unknown"
      ? [t("kitchen_join.why_commission_unknown")]
      : [
          commission.kind === "one"
            ? t("kitchen_join.why_commission_one", { percent: pct(commission.percent) })
            : t("kitchen_join.why_commission_range", { min: pct(commission.min), max: pct(commission.max) }),
          ...(commission.kind === "range" && commission.start !== null
            ? [commission.city
                ? t("kitchen_join.why_commission_start_city", { city: commission.city, start: pct(commission.start) })
                : t("kitchen_join.why_commission_start", { start: pct(commission.start) })]
            : []),
          ...(commission.flat ? [t("kitchen_join.why_commission_flat", { amount: fmtMoney(commission.flat) })] : []),
          t("kitchen_join.why_commission_never"),
        ];
  const why = [
    { key: "commission", title: t("kitchen_join.why_commission_title"), body: commissionLines.join(" ") },
    {
      key: "payout",
      title: t(weekly ? "kitchen_join.why_payout_title_weekly" : "kitchen_join.why_payout_title_biweekly"),
      body: weekly
        ? t("kitchen_join.why_payout_body", { count: terms?.payout.hold_days ?? 2 })
        : t("kitchen_join.why_payout_body_biweekly"),
    },
    { key: "prices", title: t("kitchen_join.why_prices_title"), body: t("kitchen_join.why_prices_body") },
    { key: "bill", title: t("kitchen_join.why_bill_title"), body: t("kitchen_join.why_bill_body") },
  ];
  const steps = [1, 2, 3, 4] as const;
  const faq = ["fees", "payouts", "delivery", "tablet", "approval", "prices", "account", "later"] as const;
  const countries = dir.countries.map((c) => c.name);

  return (
    <>
      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <section className="bg-[linear-gradient(180deg,#EFF6F6_0%,#FFFFFF_100%)]">
        <div className={`${PAGE} grid items-center gap-8 pb-12 pt-8 md:pb-16 md:pt-12 lg:grid-cols-[1fr_minmax(0,500px)] lg:gap-12 lg:pt-16`}>
          <div>
            <p className="m-0 text-caption text-peacock">{t("kitchen_join.eyebrow")}</p>
            <h1 className="m-0 mt-3 text-display">{t("kitchen_join.title")}</h1>
            <p className="m-0 mt-4 max-w-[560px] text-body-lg text-muted">{t("kitchen_join.lead")}</p>
            <div className="mt-7">
              <HeroAction />
            </div>
            <dl aria-label={t("kitchen_join.facts_label")} className="m-0 mt-9 grid max-w-[560px] grid-cols-3 gap-3 sm:gap-6">
              {commission.kind !== "unknown" && (
                <Fact
                  value={commission.kind === "one"
                    ? t("kitchen_join.fact_commission_one", { percent: pct(commission.percent) })
                    : t("kitchen_join.fact_commission_range", { min: pct(commission.min), max: pct(commission.max) })}
                  label={t("kitchen_join.fact_commission_note")}
                  testId="fact-commission"
                />
              )}
              <Fact value={t(weekly ? "kitchen_join.fact_weekly" : "kitchen_join.fact_biweekly")} label={t("kitchen_join.fact_payout_note")} />
              {openCities > 0 && (
                <Fact
                  value={t("kitchen_join.fact_cities", { count: new Intl.NumberFormat(formatLocale).format(openCities) })}
                  label={t("kitchen_join.fact_cities_note", { count: openCities })}
                />
              )}
            </dl>
          </div>
          <div className="relative overflow-hidden rounded-[28px] bg-peacock-mist md:rounded-[36px]">
            {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
            <img
              src={`/food/${HERO}-800.webp`}
              srcSet={`/food/${HERO}-800.webp 800w, /food/${HERO}-1600.webp 1600w`}
              sizes="(min-width: 1024px) 500px, 100vw"
              alt={t("kitchen_join.hero_alt")}
              data-testid="partner-hero"
              className="block aspect-[4/3] w-full object-cover object-[62%_40%] lg:aspect-[5/6]"
            />
          </div>
        </div>
      </section>

      {/* ── why ──────────────────────────────────────────────────────────── */}
      <section aria-labelledby="why" className={`${PAGE} pt-12 md:pt-16`}>
        <h2 id="why" className="m-0 text-h1">{t("kitchen_join.why_title")}</h2>
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_400px] lg:gap-10">
          <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2">
            {why.map((w) => (
              <li key={w.key} data-testid={`why-${w.key}`} className="rounded-card bg-porcelain p-5 md:p-6">
                <h3 className="m-0 text-h3">{w.title}</h3>
                <p className="m-0 mt-2 text-body text-muted">{w.body}</p>
              </li>
            ))}
          </ul>
          {bill && (
            <figure data-testid="partner-bill" className="m-0 rounded-[24px] bg-kohl p-5 md:p-6">
              <figcaption className="text-caption text-kesar-bright">
                {bill.source === "order" ? t("city.bill_real", { city: bill.city_name }) : t("city.bill_typical", { city: bill.city_name })}
              </figcaption>
              <div className="mt-4 rounded-[18px] bg-white p-5">
                <FairBill
                  lines={bill.lines}
                  total={bill.total}
                  currency={bill.currency}
                  formatLocale={formatLocale}
                  t={t}
                  distance={bill.assumptions.distance ? t(bill.assumptions.distance_unit === "mi" ? "common.mi" : "common.km", { n: bill.assumptions.distance }) : null}
                  totalLabel={t("city.you_pay")}
                  compact
                />
                {bill.shares && (
                  <p className="m-0 mt-3 rounded-chip bg-peacock-mist px-3 py-2 text-small font-semibold tabular-nums text-peacock-deep">
                    {t("kitchen_join.bill_kitchen_gets", { amount: money(bill.shares.kitchen, bill.currency, formatLocale) })}
                  </p>
                )}
              </div>
              <p className="m-0 mt-3 text-small text-[#A9B8BA]">{t("city.bill_note", { city: bill.city_name })}</p>
            </figure>
          )}
        </div>
      </section>

      {/* ── how it works ─────────────────────────────────────────────────── */}
      <section aria-labelledby="how" className={`${PAGE} pt-12 md:pt-16`}>
        <h2 id="how" className="m-0 text-h1">{t("kitchen_join.how_title")}</h2>
        <ol className="m-0 mt-6 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((n) => (
            <li key={n} className="rounded-card border border-line p-5 md:p-6">
              <span aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-pill bg-peacock text-label text-white">{n}</span>
              <h3 className="m-0 mt-3 text-h3">{t(`kitchen_join.how_${n}_title`)}</h3>
              <p className="m-0 mt-2 text-body text-muted">{t(`kitchen_join.how_${n}_body`)}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ── documents ───────────────────────────────────────────────────── */}
      <section aria-labelledby="docs" className={`${PAGE} pt-12 md:pt-16`}>
        <div className="rounded-[24px] bg-peacock-mist p-5 md:p-8">
          <h2 id="docs" className="m-0 text-h2">{t("kitchen_join.docs_title")}</h2>
          {terms && terms.documents.length > 0 ? (
            <>
              <p className="m-0 mt-2 text-body text-muted">{t("kitchen_join.docs_lead")}</p>
              <ul data-testid="partner-docs" className="m-0 mt-5 grid list-none gap-3 p-0 md:grid-cols-2">
                {terms.documents.map((d) => (
                  <li key={d.key} data-doc={d.key} className="flex gap-3 rounded-card bg-white p-4">
                    <span aria-hidden="true" className="mt-[2px] flex h-6 w-6 shrink-0 items-center justify-center rounded-pill bg-peacock text-white">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
                    </span>
                    <span>
                      <b className="block text-label">{d.title}</b>
                      <span className="mt-1 block text-small text-muted">{d.why}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p data-testid="partner-docs-none" className="m-0 mt-2 text-body text-muted">{t("kitchen_join.docs_none")}</p>
          )}
        </div>
      </section>

      {/* ── apply ───────────────────────────────────────────────────────── */}
      <section id="apply" aria-labelledby="apply-title" className={`${PAGE} scroll-mt-20 pt-12 md:pt-16`}>
        <ApplyPanel
          terms={terms}
          visitorCity={here?.code ?? null}
          countryKnown={!!country}
          countries={countries}
          taxRegimes={Object.fromEntries(dir.countries.map((c) => [c.code, c.tax_regime]))}
          phoneCodes={Object.fromEntries(dir.countries.map((c) => [c.code, c.phone_code]))}
        />
      </section>

      {/* ── FAQ ─────────────────────────────────────────────────────────── */}
      <section aria-labelledby="faq" className={`${PAGE} pb-16 pt-12 md:pb-24 md:pt-16`}>
        <h2 id="faq" className="m-0 text-h1">{t("kitchen_join.faq_title")}</h2>
        <div className="mt-4 divide-y divide-line border-y border-line">
          {faq.map((q) => (
            <details key={q} className="group py-1">
              <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-4 py-3 text-h3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peacock [&::-webkit-details-marker]:hidden">
                {t(`kitchen_join.faq_${q}_q`)}
                <span aria-hidden="true" className="text-h2 leading-none text-peacock transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="m-0 max-w-[760px] pb-5 text-body text-muted">{t(`kitchen_join.faq_${q}_a`)}</p>
            </details>
          ))}
        </div>
      </section>
    </>
  );
}

function Fact({ value, label, testId }: { value: string; label: string; testId?: string }) {
  return (
    <div data-testid={testId} className="flex min-w-0 flex-col-reverse justify-end">
      <dt className="mt-1 text-small text-muted">{label}</dt>
      <dd className="m-0 text-h2 tabular-nums text-peacock-deep">{value}</dd>
    </div>
  );
}
