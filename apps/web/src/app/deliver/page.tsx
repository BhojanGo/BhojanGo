// Deliver with BhojanGo (R8 F8): the page for people who want to deliver. Every
// number comes from GET /delivery/terms (the city's live rider pay rules, priced
// by the engine) and the requirements from the country's Markets settings, so the
// page is right in every country and stays right when an admin changes a rule.
// Sign-up happens here (phone + code, then /riders/apply, like the app's Join);
// documents and payouts follow in BhojanGo Delivery.
import { formatLocale as localeOf } from "@bhojango/i18n";
import type { Metadata } from "next";
import Link from "next/link";

import { flatCities } from "@/components/discover/places";
import { capitalize, defaultCity, distance, orList, percent, unitName, weekday } from "@/lib/deliver";
import { libraryPhoto, money } from "@/lib/format";
import { getContext } from "@/lib/prefs";
import { deliverySignUp, deliveryTerms, SITE, type DeliveryTerms } from "@/lib/server";
import { CityPicker } from "./CityPicker";
import { GetStarted } from "./GetStarted";

const HERO = "delivery-partner-scooter"; // the photo library (docs/design/photos/LICENSES.md)
const WRAP = "container-page";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("deliver_page.meta_title"), description: t("deliver_page.meta_description"), alternates: { canonical: `${SITE}/deliver` } };
}

type T = Awaited<ReturnType<typeof getContext>>["t"];

export default async function Deliver({ searchParams }: { searchParams: Promise<{ city?: string }> }) {
  const ctx = await getContext();
  const { t, language, directory: dir } = ctx;
  const asked = (await searchParams).city;
  const live = flatCities(dir).filter((c) => c.status === "live");
  const ours = live.filter((c) => !ctx.country || c.country === ctx.country.code);
  const askedCity = live.find((c) => c.code === asked)?.code;
  const code = askedCity ?? defaultCity(ours.map((c) => c.code), [ctx.place?.city_code, ctx.city?.code]);
  const terms = code ? await deliveryTerms(code) : null;
  const ok = terms && terms !== "error" ? terms : null;
  // Who can sign up in the form's country (its cities are that country's): minimum age and vehicles.
  const signUpCountry = ok?.country ?? ctx.country?.code ?? null;
  const signUp = signUpCountry ? await deliverySignUp(signUpCountry) : null;
  const termsCountry = dir.countries.find((k) => k.code === (ok?.country ?? ctx.country?.code)) ?? ctx.country;
  const loc = termsCountry ? localeOf(termsCountry.locales) : ctx.formatLocale;
  const cityName = ok?.city.name ?? live.find((c) => c.code === code)?.name ?? "";
  const m = (v: string | number | null | undefined) => (ok ? money(v, ok.currency, loc) : "");
  const hero = libraryPhoto(HERO, 800);
  const ex = ok?.example ?? null;

  return (
    <div className="pb-16 md:pb-24">
      {/* Hero */}
      <section className="bg-[linear-gradient(180deg,#EFF6F6_0%,#FFFFFF_100%)]">
        {/* R27: grid-cols-1 (minmax(0,1fr)) on phones: a long Tamil word no longer widens the page */}
        <div className={`${WRAP} grid grid-cols-1 items-center gap-8 pb-12 pt-8 md:pb-16 md:pt-14 lg:grid-cols-[1fr_520px] lg:gap-12`}>
          <div>
            <p className="m-0 text-caption text-peacock">{t("deliver_page.eyebrow")}</p>
            <h1 className="m-0 mt-3 text-h1 [overflow-wrap:anywhere] sm:text-display">{t("deliver_page.title")}</h1>
            <p className="m-0 mt-4 max-w-[560px] text-body-lg text-muted">{t("deliver_page.lead")}</p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <a href="#get-started" className="inline-flex h-[52px] items-center rounded-full bg-peacock px-7 text-label text-white hover:bg-peacock-deep hover:text-white">
                {t("deliver_page.get_started")}
              </a>
              <a href="#pay" className="inline-flex h-[52px] items-center rounded-full border-[1.5px] border-line-strong bg-white px-6 text-label text-kohl hover:border-peacock hover:text-kohl">
                {t("deliver_page.how_pay_works")}
              </a>
            </div>
            <p className="m-0 mt-5 inline-flex items-center gap-2 rounded-full bg-peacock-tint px-4 py-2 text-label text-peacock-deep" data-testid="no-fee">
              <Check /> {t("deliver_page.no_fee")}
            </p>
          </div>
          <div className="relative pb-16 lg:pb-12">
            <div className="aspect-[4/3] w-full overflow-hidden rounded-[28px] bg-plate md:rounded-[40px]">
              {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
              <img
                src={hero ?? undefined}
                srcSet={`/food/${HERO}-400.webp 400w, /food/${HERO}-800.webp 800w, /food/${HERO}-1600.webp 1024w`}
                sizes="(min-width: 1024px) 520px, 100vw"
                alt={t("deliver_page.hero_alt")}
                className="block h-full w-full object-cover"
              />
            </div>
            {ok && ex && (
              <div data-testid="hero-trip" className="absolute bottom-0 left-4 w-[300px] max-w-[calc(100%-32px)] rounded-[24px] bg-white p-5 shadow-[0_2px_4px_rgba(17,20,24,0.06),0_24px_48px_rgba(17,20,24,0.14)] lg:-left-6">
                <p className="m-0 text-caption text-peacock">{t("deliver_page.hero_card_title", { city: ok.city.name })}</p>
                <p className="m-0 mt-2 text-h3 tabular-nums">{t("deliver_page.hero_card_body", { amount: m(ex.total), distance: distance(ex.distance, ok.distance_unit, loc) })}</p>
                {ok.hourly_floor && (
                  <p className="m-0 mt-2 border-t border-line pt-2 text-small tabular-nums">{t("deliver_page.hero_card_floor", { amount: m(ok.hourly_floor) })}</p>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Pay */}
      <section id="pay" aria-labelledby="pay-title" className={`${WRAP} scroll-mt-24 pt-12 md:pt-16`}>
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <h2 id="pay-title" className="m-0 text-h1">{cityName ? t("deliver_page.pay_title", { city: cityName }) : t("deliver_page.how_pay_works")}</h2>
          {ok && ok.cities.length > 1 && <CityPicker cities={ok.cities} value={ok.city.code} label={t("deliver_page.city_label")} />}
        </div>
        {terms === "error" ? (
          <div role="alert" className="mt-6 rounded-[20px] border border-line bg-white p-6">
            <p className="m-0 text-body">{t("deliver_page.pay_error", { city: cityName })}</p>
            <a href={`/deliver${code ? `?city=${code}` : ""}#pay`} className="mt-3 inline-flex h-11 items-center rounded-full border-[1.5px] border-peacock px-5 text-label text-peacock">
              {t("deliver_page.try_again")}
            </a>
          </div>
        ) : !ok ? (
          <div className="mt-6 rounded-[20px] bg-porcelain p-6" data-testid="no-city">
            <h3 className="m-0 text-h3">{t("deliver_page.no_city_title", { country: ctx.country?.name ?? "" })}</h3>
            <p className="m-0 mt-1 text-body text-muted">{t("deliver_page.no_city_body")}</p>
            <Link href="/cities" className="mt-3 inline-block text-label">{t("deliver_page.no_city_link")}</Link>
          </div>
        ) : (
          <PayCards ok={ok} t={t} m={m} loc={loc} language={language} />
        )}
      </section>

      {/* Requirements */}
      {ok && <Requirements ok={ok} t={t} language={language} countryName={termsCountry?.name ?? ""} />}

      {/* How it works */}
      <section aria-labelledby="how-title" className={`${WRAP} pt-12 md:pt-16`}>
        <h2 id="how-title" className="m-0 text-h1">{t("deliver_page.how_title")}</h2>
        <ol className="m-0 mt-6 grid grid-cols-1 list-none gap-4 p-0 md:grid-cols-3 md:gap-6">
          {([1, 2, 3] as const).map((n) => (
            <li key={n} className="rounded-[24px] bg-porcelain p-5 md:p-7">
              <div aria-hidden="true" className="text-h1 text-peacock">{n}</div>
              <h3 className="m-0 mt-2 text-h3">{t(`deliver_page.step${n}_title`)}</h3>
              <p className="m-0 mt-[6px] text-body text-muted">{t(`deliver_page.step${n}_body`)}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Get started */}
      <section id="get-started" aria-labelledby="gs-title" className={`${WRAP} scroll-mt-24 pt-12 md:pt-16`}>
        <div className="grid grid-cols-1 gap-8 rounded-[28px] bg-[#0C1416] p-5 text-[#F2F5F5] sm:p-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)] lg:p-12">
          <div>
            <h2 id="gs-title" className="m-0 text-h1">{t("deliver_page.gs_title")}</h2>
            <p className="m-0 mt-3 text-body-lg text-[#C4D0D2]">{t("deliver_page.gs_sub")}</p>
            <ol className="m-0 mt-6 hidden list-none space-y-3 p-0 lg:block">
              {([1, 2, 3] as const).map((n) => (
                <li key={n} className="flex items-start gap-3 text-body text-[#C4D0D2]">
                  <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-kesar-bright text-label text-kohl">{n}</span>
                  <span><b className="text-[#F2F5F5]">{t(`deliver_page.step${n}_title`)}</b></span>
                </li>
              ))}
            </ol>
          </div>
          <GetStarted
            countries={dir.countries.filter((k) => k.live > 0).map((k) => ({ code: k.code, name: k.name, phone_code: k.phone_code }))}
            country={ok?.country ?? ctx.country?.code ?? null}
            cities={ok?.cities ?? ours.map((c) => ({ code: c.code, name: c.name, region: c.region }))}
            city={ok?.city.code ?? code}
            apps={ok?.apps ?? { android: null, ios: null }}
            rules={signUp ? { min_age: signUp.min_age, vehicles: signUp.vehicles, today: signUp.today } : null}
          />
        </div>
      </section>

      {/* FAQ */}
      {ok && <Faq ok={ok} t={t} m={m} loc={loc} language={language} countryName={termsCountry?.name ?? ""} />}
    </div>
  );
}

function PayCards({ ok, t, m, loc, language }: { ok: DeliveryTerms; t: T; m: (v: string | number | null | undefined) => string; loc: string; language: string }) {
  const ex = ok.example;
  if (!ex) return <p className="mt-6 rounded-[20px] bg-porcelain p-6 text-body">{t("deliver_page.pay_none", { city: ok.city.name })}</p>;
  const unit = unitName(ok.distance_unit, loc);
  const biweekly = ok.pay_schedule?.frequency === "biweekly";
  return (
    <>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="pay-cards" data-city={ok.city.code}>
        <Card title={t("deliver_page.pay_trip_title")} big={m(ex.total)} testid="pay-trip" sub={t("deliver_page.pay_trip_example", { distance: distance(ex.distance, ok.distance_unit, loc) })}>
          <p className="m-0">{t("deliver_page.pay_trip_body", { base: m(ex.base), per_unit: m(ex.per_unit), unit })}</p>
          {Number(ex.per_wait_minute) > 0 && (
            <p className="m-0 mt-2">{t("deliver_page.pay_wait", { per_minute: m(ex.per_wait_minute), minutes: ex.free_wait_minutes })}</p>
          )}
        </Card>
        {ok.hourly_floor && (
          <Card title={t("deliver_page.pay_floor_title")} big={t("deliver_page.pay_floor_amount", { amount: m(ok.hourly_floor) })} testid="pay-floor">
            <p className="m-0">{t("deliver_page.pay_floor_body")}</p>
          </Card>
        )}
        <Card title={t("deliver_page.pay_tips_title")} big={t("deliver_page.pay_tips_amount", { percent: percent(ok.tips_percent ?? 100, loc) })} testid="pay-tips">
          <p className="m-0">{t("deliver_page.pay_tips_body")}</p>
        </Card>
        {ok.pay_schedule && (
          <Card title={t(biweekly ? "deliver_page.pay_biweekly_title" : "deliver_page.pay_weekly_title")} big={capitalize(weekday(ok.pay_schedule.day, language))} testid="pay-weekly">
            <p className="m-0">{t("deliver_page.pay_cadence_body", { day: weekday(ok.pay_schedule.day, language) })}</p>
          </Card>
        )}
      </div>
      {ok.batch_bonus && Number(ok.batch_bonus) > 0 && (
        <p className="m-0 mt-4 rounded-[16px] bg-peacock-mist px-5 py-4 text-body">{t("deliver_page.pay_batch", { amount: m(ok.batch_bonus) })}</p>
      )}
      <p className="m-0 mt-4 text-small text-muted">{t("deliver_page.pay_note", { distance: distance(ex.distance, ok.distance_unit, loc), city: ok.city.name })}</p>
    </>
  );
}

function Card({ title, big, sub, testid, children }: { title: string; big?: string; sub?: string; testid: string; children: React.ReactNode }) {
  return (
    <div data-testid={testid} className="flex flex-col rounded-[24px] border border-line bg-white p-5 md:p-6">
      <h3 className="m-0 text-caption text-peacock">{title}</h3>
      {big && <p className="m-0 mt-3 text-h2 tabular-nums">{big}</p>}
      {sub && <p className="m-0 text-small text-muted">{sub}</p>}
      <div className="mt-3 text-small text-muted">{children}</div>
    </div>
  );
}

function Requirements({ ok, t, language, countryName }: { ok: DeliveryTerms; t: T; language: string; countryName: string }) {
  const r = ok.requirements;
  const vehicles = r.vehicles.map((v) => t(`deliver_page.vehicle_${v}`));
  const items: { key: string; title: string; body: string }[] = [
    ...(r.min_age ? [{ key: "age", title: t("deliver_page.req_age_title", { age: r.min_age }), body: t("deliver_page.req_age_body", { country: countryName }) }] : []),
    ...(vehicles.length ? [{ key: "vehicle", title: t("deliver_page.req_vehicle_title"), body: capitalize(orList(vehicles, language)) }] : []),
    { key: "phone", title: t("deliver_page.req_phone_title"), body: t("deliver_page.req_phone_body") },
    ...r.papers.map((d) => ({ key: d.key, title: t(`deliver_page.doc_${d.key}`), body: t(`deliver_page.doc_${d.key}_body`) })),
  ];
  return (
    <section id="requirements" aria-labelledby="req-title" className={`${WRAP} pt-12 md:pt-16`}>
      <h2 id="req-title" className="m-0 text-h1">{t("deliver_page.req_title")}</h2>
      <p className="m-0 mt-1 text-body text-muted">{t("deliver_page.req_sub", { country: countryName })}</p>
      <ul className="m-0 mt-6 grid grid-cols-1 list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3" data-testid="requirements" data-country={ok.country}>
        {items.map((i) => (
          <li key={i.key} data-key={i.key} className="flex gap-3 rounded-[20px] border border-line bg-white p-4 md:p-5">
            <span aria-hidden="true" className="mt-[2px] flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-peacock-tint text-peacock"><Check /></span>
            <span>
              <b className="block text-label">{i.title}</b>
              <span className="block text-small text-muted">{i.body}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="m-0 mt-4 text-small text-muted">{t("deliver_page.req_note")}</p>
    </section>
  );
}

function Faq({ ok, t, m, loc, language, countryName }: { ok: DeliveryTerms; t: T; m: (v: string | number | null | undefined) => string; loc: string; language: string; countryName: string }) {
  const ex = ok.example;
  const insurance = ok.requirements.papers.find((d) => d.step === "insurance");
  const vehicles = ok.requirements.vehicles.map((v) => t(`deliver_page.vehicle_${v}`));
  const qa: { id: string; q: string; a: string }[] = [
    ...(ex ? [{
      id: "pay", q: t("deliver_page.faq_pay_q"),
      a: [t("deliver_page.faq_pay_a", { city: ok.city.name, base: m(ex.base), per_unit: m(ex.per_unit), unit: unitName(ok.distance_unit, loc),
        per_minute: m(ex.per_wait_minute), minutes: ex.free_wait_minutes }),
      ok.hourly_floor ? t("deliver_page.faq_pay_floor", { amount: m(ok.hourly_floor) }) : ""].filter(Boolean).join(" "),
    }] : []),
    { id: "hours", q: t("deliver_page.faq_hours_q"), a: t("deliver_page.faq_hours_a") },
    { id: "tips", q: t("deliver_page.faq_tips_q"), a: t("deliver_page.faq_tips_a") },
    ...(vehicles.length ? [{ id: "vehicle", q: t("deliver_page.faq_vehicle_q"), a: t("deliver_page.faq_vehicle_a", { country: countryName, vehicles: orList(vehicles, language) }) }] : []),
    ...(insurance ? [{ id: "insurance", q: t("deliver_page.faq_insurance_q"), a: t("deliver_page.faq_insurance_a", { document: t(`deliver_page.doc_${insurance.key}`) }) }] : []),
    ...(ok.pay_schedule ? [{ id: "paid", q: t("deliver_page.faq_paid_q"), a: t(ok.pay_schedule.frequency === "biweekly" ? "deliver_page.faq_paid_biweekly" : "deliver_page.faq_paid_weekly") }] : []),
    { id: "approval", q: t("deliver_page.faq_approval_q"), a: t("deliver_page.faq_approval_a") },
    { id: "fee", q: t("deliver_page.faq_fee_q"), a: t("deliver_page.faq_fee_a") },
  ];
  return (
    <section aria-labelledby="faq-title" className={`${WRAP} pt-12 md:pt-16`}>
      <h2 id="faq-title" className="m-0 text-h1">{t("deliver_page.faq_title")}</h2>
      <div className="mt-6 divide-y divide-line rounded-[24px] border border-line bg-white" data-testid="faq">
        {qa.map((x) => (
          <details key={x.id} className="group px-5 md:px-6">
            <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-4 py-4 text-label [&::-webkit-details-marker]:hidden">
              {x.q}
              <span aria-hidden="true" className="text-h3 text-peacock transition-transform group-open:rotate-45">+</span>
            </summary>
            <p className="m-0 max-w-[760px] pb-5 text-body text-muted">{x.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function Check() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
