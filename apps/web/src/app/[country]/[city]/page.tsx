// A city's page (WebCity), server-rendered for search engines: one per city in
// Markets, live or coming soon. Name, state, country, areas, kitchens, offers
// and the example bill are all data; a new city needs no code.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AddressBox } from "@/components/AddressBox";
import { KitchenCard, OfferCard } from "@/components/Cards";
import { FairBill } from "@/components/FairBill";
import { Search } from "@/components/Icons";
import { NotifyMe } from "@/components/NotifyMe";
import { lowestFee, pricingOf, waitingOf } from "@/lib/contract";
import { photo } from "@/lib/format";
import { cityFaq } from "./faq";
import { getContext } from "@/lib/prefs";
import { cityPage, discover, exampleBill, SITE, type CityPage, type KitchenCard as Kitchen } from "@/lib/server";

type Params = Promise<{ country: string; city: string }>;
type Query = Promise<{ cuisine?: string | string[]; q?: string | string[] }>;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() || "";
const pathOf = (c: CityPage) => `/${c.country.slug}/${c.slug}`;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { country, city } = await params;
  const [c, { t }] = await Promise.all([cityPage(country, city), getContext()]);
  if (!c) return {};
  const live = c.status === "live";
  return {
    title: live ? t("city.meta_title", { city: c.name }) : t("city.meta_title_soon", { city: c.name }),
    description: live
      ? t("city.meta_description", { city: c.name, count: c.restaurants })
      : t("city.meta_description_soon", { city: c.name }),
    alternates: { canonical: `${SITE}${pathOf(c)}` },
  };
}

export default async function City({ params, searchParams }: { params: Params; searchParams: Query }) {
  const { country, city } = await params;
  const c = await cityPage(country, city);
  if (!c) notFound();
  return c.status === "live" ? <LiveCity c={c} search={await searchParams} /> : <SoonCity c={c} />;
}

async function Crumbs({ c }: { c: CityPage }) {
  const { t } = await getContext();
  return (
    <nav aria-label={t("city.breadcrumb")} className="text-small text-[#C9D3D4]">
      <Link href="/cities" className="text-[#C9D3D4] hover:text-white">{t("cities.title")}</Link>
      {" › "}
      {c.country.name}
      {c.region?.name ? ` › ${c.region.name}` : ""}
      {" › "}
      <b aria-current="page" className="text-white">{c.name}</b>
    </nav>
  );
}

function matches(k: Kitchen, cuisine: string, q: string): boolean {
  const lc = (s: string) => s.toLocaleLowerCase();
  if (cuisine && !k.cuisine_types.some((x) => lc(x) === lc(cuisine))) return false;
  if (q && !lc([k.name, ...k.cuisine_types, k.area ?? ""].join(" ")).includes(lc(q))) return false;
  return true;
}

async function LiveCity({ c, search }: { c: CityPage; search: Awaited<Query> }) {
  const { t, formatLocale, place } = await getContext();
  // With an address in this city, each kitchen's fee is the exact one to that address.
  const here = place && place.served !== false && place.city_code === c.code ? place : null;
  const [d, bill, near] = await Promise.all([discover({ city: c.code }), exampleBill(c.code), here ? discover({ lat: here.lat, lng: here.lng }) : Promise.resolve(null)]);
  const exact = new Map((near?.restaurants ?? []).map((k) => [k.id, k]));
  const kitchens = (d?.restaurants ?? []).map((k) => {
    const e = exact.get(k.id);
    return e ? { ...k, delivery_fee: e.delivery_fee, free_delivery: e.free_delivery, distance: e.distance, eta_min: e.eta_min, eta_max: e.eta_max, offer: e.offer ?? k.offer } : k;
  });
  const pricing = pricingOf(c);
  const feeFrom = here ? null : lowestFee(pricing);
  const offers = d?.offers ?? [];
  const currency = d?.currency ?? bill?.currency ?? c.country.currency;
  const unit = d?.distance_unit ?? c.country.distance_unit;
  const cuisines = (d?.cuisines ?? []).map((x) => String(x.name));
  const cuisine = one(search.cuisine);
  const q = one(search.q);
  const shown = kitchens.filter((k) => matches(k, cuisine, q));
  const cover = photo(kitchens.find((k) => k.cover_url)?.cover_url ?? null, 1600);
  const top = cuisines.slice(0, 4).join(", ");
  const base = pathOf(c);
  const zones = c.zones;
  const chip = "inline-flex h-11 items-center rounded-full border px-[18px] font-bold";
  // Every kitchen in the city, for search engines (the name comes from the page's title).
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: t("city.title", { city: c.name }),
    itemListElement: kitchens.map((k, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE}${k.path ?? `${base}/${k.slug}`}`, name: k.name })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <section className="relative overflow-hidden bg-[#111418]">
        {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
        {cover && <img src={cover} alt="" className="absolute inset-0 block h-full w-full object-cover" />}
        <div aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(90deg,rgba(17,20,24,0.86)_0%,rgba(17,20,24,0.55)_50%,rgba(17,20,24,0.1)_100%)]" />
        <div className="relative container-page py-10 text-white md:py-16">
          <div className="max-w-[680px]">
            <Crumbs c={c} />
            <h1 className="mt-4 text-display leading-none">{t("city.title", { city: c.name })}</h1>
            <p className="mt-[14px] text-body-lg text-[#DDE5E6]">
              {[
                t("city.kitchens", { count: c.restaurants }),
                top ? t("city.cuisines_more", { cuisines: top }) : null,
                t("city.every_fee"),
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="mt-7 text-[#111418]">
              <AddressBox size="hero" country={c.country.code} />
            </div>
          </div>
        </div>
      </section>

      <div className="container-page">
        {zones.length > 0 && (
          <section aria-labelledby="areas" className="pt-10 md:pt-12">
            <h2 id="areas" className="m-0 text-h2">{t("city.areas_title")}</h2>
            <p className="mt-1 text-body text-muted">{t("city.areas_note", { count: zones.length })}</p>
            <ul className="m-0 mt-4 flex list-none flex-wrap gap-[10px] p-0">
              {zones.map((z) => (
                <li key={z.name} className={`${chip} border-[#E2E7E8] text-[#111418]`}>{z.name}</li>
              ))}
            </ul>
          </section>
        )}

        <section id="kitchens" aria-labelledby="kitchens-title" className="pt-12 md:pt-14">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <h2 id="kitchens-title" className="m-0 text-h2">
              {cuisine ? t("city.cuisine_kitchens", { cuisine, city: c.name }) : t("city.kitchens_title", { city: c.name })}
            </h2>
            <form id="search" role="search" action={`${base}#kitchens`} className="flex h-12 scroll-mt-[140px] w-full items-center gap-[10px] rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-[18px] focus-within:border-[#0B5D66] md:w-[360px]">
              <Search size={18} color="#3D4A4E" />
              {cuisine && <input type="hidden" name="cuisine" value={cuisine} />}
              <label htmlFor="city-q" className="sr-only">{t("city.search_label")}</label>
              <input id="city-q" type="search" name="q" defaultValue={q} placeholder={t("city.search_placeholder")} className="min-w-0 flex-grow bg-transparent text-body outline-none placeholder:text-muted" />
            </form>
          </div>
          {cuisines.length > 0 && (
            <nav aria-label={t("city.cuisines")} className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 md:mx-0 md:flex-wrap md:px-0">
              <Link href={`${base}${q ? `?q=${encodeURIComponent(q)}` : ""}#kitchens`} aria-current={!cuisine ? "page" : undefined} className={`flex h-10 shrink-0 items-center rounded-full px-4 text-label ${!cuisine ? "bg-[#111418] text-white hover:text-white" : "border border-[#C9D3D4] text-[#111418] hover:text-[#111418]"}`}>
                {t("city.all_cuisines")}
              </Link>
              {cuisines.map((name) => {
                const on = name.toLocaleLowerCase() === cuisine.toLocaleLowerCase();
                const qs = new URLSearchParams({ ...(on ? {} : { cuisine: name }), ...(q ? { q } : {}) }).toString();
                return (
                  <Link key={name} href={`${base}${qs ? `?${qs}` : ""}#kitchens`} aria-current={on ? "page" : undefined} className={`flex h-10 shrink-0 items-center rounded-full px-4 text-label ${on ? "bg-[#111418] text-white hover:text-white" : "border border-[#C9D3D4] text-[#111418] hover:text-[#111418]"}`}>
                    {name}
                  </Link>
                );
              })}
            </nav>
          )}
          {shown.length ? (
            <div className="mt-5 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {shown.map((k) => (
                <KitchenCard key={k.id} k={k} t={t} currency={currency} formatLocale={formatLocale} distanceUnit={unit} feeFrom={feeFrom} />
              ))}
            </div>
          ) : (
            <p role="status" className="mt-5 text-body text-muted">
              {kitchens.length ? t("city.no_match") : t("city.no_kitchens")}{" "}
              {(cuisine || q) && <Link href={`${base}#kitchens`} className="font-bold">{t("city.clear_filters")}</Link>}
            </p>
          )}
        </section>

        {offers.length > 0 && (
          <section aria-labelledby="city-offers" className="pt-12 md:pt-14">
            <h2 id="city-offers" className="m-0 text-h2">{t("city.offers_title", { city: c.name })}</h2>
            <p className="mt-1 text-body text-muted">{t("offers.who_pays")}</p>
            <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {offers.slice(0, 6).map((o, i) => (
                <OfferCard
                  key={o.id}
                  o={o}
                  i={i}
                  t={t}
                  currency={currency}
                  formatLocale={formatLocale}
                  fallbackPhoto={kitchens.find((k) => k.id === (o.restaurant?.id as string | undefined))?.cover_url ?? null}
                />
              ))}
            </div>
          </section>
        )}

        <section aria-labelledby="plainly" className="grid grid-cols-1 items-start gap-10 pb-16 pt-12 md:pb-24 md:pt-16 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-12 xl:grid-cols-[minmax(0,1fr)_440px]">
          <div>
            <h2 id="plainly" className="m-0 text-h2">{t("city.plainly_title", { city: c.name })}</h2>
            <dl className="m-0 mt-2">
              {cityFaq(c, pricing, t, formatLocale).map((f) => (
                <div key={f.q} className="border-b border-[#E2E7E8] py-5">
                  <dt className="text-h3">{f.q}</dt>
                  <dd className="m-0 mt-[6px] text-body leading-[1.5] text-muted">{f.a}</dd>
                </div>
              ))}
            </dl>
          </div>
          {bill && (
            <div className="rounded-[28px] bg-[#111418] p-5 md:p-6">
              <div className="text-caption text-[#E8A93C]">
                {bill.source === "order" ? t("city.bill_real", { city: c.name }) : t("city.bill_typical", { city: c.name })}
              </div>
              <div className="mt-4 rounded-[20px] bg-white p-5">
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
              </div>
              <p className="mt-4 text-small text-[#A9B8BA]">{t("city.bill_note", { city: c.name })}</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

async function SoonCity({ c }: { c: CityPage }) {
  const { t, formatLocale } = await getContext();
  const waiting = waitingOf(c);
  return (
    <>
      <section className="bg-[#111418]">
        <div className="container-page py-10 text-white md:py-16">
          <div className="max-w-[680px]">
            <Crumbs c={c} />
            <h1 className="mt-4 text-display leading-none">{t("city.soon_title", { city: c.name })}</h1>
            <p className="mt-[14px] text-body-lg text-[#DDE5E6]">{t("city.soon_body", { city: c.name })}</p>
            {waiting > 0 && (
              <p className="mt-4 inline-flex h-9 items-center gap-2 rounded-full bg-[#1C3A3E] px-4 text-label text-[#F2F5F5]">
                <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#E8A93C]" />
                {t("common.people_waiting", { count: waiting, n: new Intl.NumberFormat(formatLocale).format(waiting) })}
              </p>
            )}
          </div>
        </div>
      </section>
      <div className="container-page py-10 md:py-14">
        <div className="max-w-[640px]">
          <NotifyMe variant="card" source="soon_city" cityCode={c.code} cityName={c.name} />
          <p className="mt-4 text-body text-muted">
            <Link href="/cities" className="font-bold">{t("home.see_where")}</Link>
          </p>
        </div>
      </div>
    </>
  );
}
