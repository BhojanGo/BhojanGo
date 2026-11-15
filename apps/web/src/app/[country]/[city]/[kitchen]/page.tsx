// /{country}/{city}/{kitchen} (WebKitchen, MWebMenu): the kitchen and its menu,
// server-rendered with Restaurant + Menu structured data. The fee, the offer
// and the distance are for the visitor's address (discover) when one is set;
// adding to the bag happens in the browser.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { offerBadge, offerTitle, RatingBadge } from "@/components/Cards";
import { money, number, photo } from "@/lib/format";
import { getContext } from "@/lib/prefs";
import { discover, menu, restaurant, SITE, type KitchenCard, type Restaurant } from "@/lib/server";
import { availability, clock, km, slugify } from "./data";
import { KitchenActions } from "./KitchenActions";
import { KitchenMenu, type Category } from "./KitchenMenu";

type Params = Promise<{ country: string; city: string; kitchen: string }>;

async function load(params: Params): Promise<{ r: Restaurant; path: string } | null> {
  const { country, city, kitchen } = await params;
  const r = await restaurant(kitchen);
  if (!r || slugify(r.city) !== city.toLowerCase() || r.country.toLowerCase() !== country.toLowerCase()) return null;
  return { r, path: `/${r.country.toLowerCase()}/${slugify(r.city)}/${r.slug}` };
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const hit = await load(params);
  if (!hit) return {};
  const { t } = await getContext();
  const { r, path } = hit;
  const title = t("kitchen.meta_title", { name: r.name, city: r.city });
  const description = t("kitchen.meta_description", { name: r.name, cuisines: r.cuisine_types.join(", "), city: r.city, min: r.delivery_time_min, max: r.delivery_time_max });
  const image = photo(r.cover_url, 1600);
  return { title, description, alternates: { canonical: path }, openGraph: { title, description, url: path, ...(image ? { images: [image] } : {}) } };
}

function Img({ src, className }: { src: string | null; className?: string }) {
  if (!src) return <span aria-hidden="true" className={`block h-full w-full bg-[#DDEBEC] ${className ?? ""}`} />;
  // eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library, already optimised
  return <img src={src} alt="" className={`block h-full w-full object-cover ${className ?? ""}`} />;
}

export default async function KitchenPage({ params }: { params: Params }) {
  const hit = await load(params);
  if (!hit) notFound();
  const { r, path } = hit;
  const { t, place, formatLocale, country } = await getContext();
  const [m, avail, near] = await Promise.all([menu(r.id), availability(r.id), place ? discover({ lat: place.lat, lng: place.lng }) : Promise.resolve(null)]);
  const card: KitchenCard | null = near?.restaurants?.find((k) => k.id === r.id) ?? null;
  const currency = r.currency;
  const unit = near?.distance_unit ?? country?.distance_unit ?? "km";
  const fmt = (v: number | string | null | undefined) => money(v, currency, formatLocale, { whole: true });

  // Distance: discover's (already in the country's unit), else from the address to the kitchen.
  let distance: string | null = null;
  if (card?.distance != null) distance = t(unit === "mi" ? "common.mi" : "common.km", { n: number(card.distance, formatLocale) });
  else if (place && r.lat != null && r.lng != null) {
    const d = km(place, { lat: r.lat, lng: r.lng });
    distance = t(unit === "mi" ? "common.mi" : "common.km", { n: number(unit === "mi" ? d * 0.621371 : d, formatLocale) });
  }
  const address = (r.address ?? {}) as { street?: string; city?: string; state?: string; zip?: string; country?: string; landmark?: string };
  const area = card?.area ?? address.landmark ?? null;

  const etaMin = card?.eta_min ?? r.delivery_time_min;
  const etaMax = card?.eta_max ?? r.delivery_time_max;
  const eta = t("common.minutes", { min: etaMin, max: etaMax });
  const fee = card ? (card.delivery_fee != null ? Number(card.delivery_fee) : null) : Number(r.delivery_fee);
  const free = card?.free_delivery || fee === 0;
  const feeText = free ? t("common.free_delivery") : fee == null ? null : card ? t("kitchen.fee_to_address", { fee: fmt(fee) }) : t("common.delivery_fee", { fee: fmt(fee) });
  const feeChip = free ? t("common.free_delivery") : fee == null ? null : t("common.delivery_fee", { fee: fmt(fee) });

  const opens = clock(r.opens_at, formatLocale);
  const closes = clock(r.closes_at, formatLocale);
  const closedNow = avail ? !avail.open_now : !r.is_open;
  const nextOpen = avail?.next_open_at ? new Intl.DateTimeFormat(formatLocale, { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: avail.timezone ?? country?.timezone }).format(new Date(avail.next_open_at)) : opens;
  const hours = closedNow
    ? { label: t("kitchen.closed_now"), value: nextOpen ? t("kitchen.opens_at", { time: nextOpen }) : t("kitchen.closed_now") }
    : opens && closes
      ? { label: t("kitchen.open_today"), value: t("kitchen.hours", { from: opens, to: closes }) }
      : { label: t("kitchen.open_today"), value: t("common.open_now") };

  const offer = card?.offer ?? null;
  const fssai = (r as { fssai_number?: string | null }).fssai_number;
  const boxes = [
    { label: t("kitchen.delivery_time"), value: eta },
    ...(feeText ? [{ label: t("kitchen.delivery_fee"), value: feeText }] : []),
    hours,
    ...(offer ? [{ label: t("kitchen.offer_who_pays", { who: offer.funded_by === "restaurant" ? t("common.kitchen_pays_caps") : t("common.bhojango_pays") }), value: offerTitle(offer, t, currency, formatLocale) }] : []),
    ...(fssai ? [{ label: t("kitchen.fssai"), value: fssai.replace(/(\d{4})(?=\d)/g, "$1 ") }] : []),
  ];

  const categories: Category[] = [
    ...(m?.categories ?? []).filter((c) => c.items.length).map((c, i) => ({ key: c.id ?? `c${i}`, name: c.name, description: c.description ?? null, items: c.items })),
    ...(m?.uncategorized_items.length ? [{ key: "more", name: t("kitchen.more"), description: null, items: m.uncategorized_items }] : []),
  ] as Category[];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Restaurant",
    name: r.name,
    url: `${SITE}${path}`,
    servesCuisine: r.cuisine_types,
    ...(r.cover_url ? { image: `${SITE}${photo(r.cover_url, 1600)}` } : {}),
    address: { "@type": "PostalAddress", streetAddress: address.street, addressLocality: address.city ?? r.city, addressRegion: address.state, postalCode: address.zip, addressCountry: address.country ?? r.country },
    ...(r.lat != null && r.lng != null ? { geo: { "@type": "GeoCoordinates", latitude: r.lat, longitude: r.lng } } : {}),
    ...(Number(r.review_count) > 0 ? { aggregateRating: { "@type": "AggregateRating", ratingValue: r.rating, reviewCount: r.review_count } } : {}),
    hasMenu: {
      "@type": "Menu",
      hasMenuSection: categories.map((c) => ({
        "@type": "MenuSection",
        name: c.name,
        hasMenuItem: c.items.map((i) => ({ "@type": "MenuItem", name: i.name, description: i.description || undefined, offers: { "@type": "Offer", price: String(i.price), priceCurrency: currency } })),
      })),
    },
  };

  const cover = photo(r.cover_url, 1600);
  const logo = photo(r.logo_url ?? r.cover_url, 400);
  const metaDesktop = [...r.cuisine_types, area, distance].filter(Boolean).join(" · ");
  const metaPhone = [r.cuisine_types[0], distance, !closedNow && closes ? t("kitchen.open_till", { time: closes }) : null].filter(Boolean).join(" · ");
  const cityPath = `/${r.country.toLowerCase()}/${slugify(r.city)}`;

  return (
    <div>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <section className="relative h-[200px] overflow-hidden md:h-[300px]">
        <Img src={cover} />
        <span aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(180deg,rgba(17,20,24,0)_40%,rgba(17,20,24,0.55)_100%)]" />
        <Link href={cityPath} aria-label={t("kitchen.back_to_city", { city: r.city })} className="absolute left-4 top-3 flex h-10 w-10 items-center justify-center rounded-full bg-white text-[#111418] shadow-[0_2px_8px_rgba(17,20,24,0.18)] md:hidden">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
        </Link>
      </section>

      <section className="relative mx-auto max-w-[1440px] px-5 md:-mt-11 md:px-16">
        <div className="flex items-end gap-6 pt-5 md:pt-0">
          <span className="hidden h-[120px] w-[120px] shrink-0 rounded-[28px] bg-white p-[6px] shadow-[0_10px_30px_rgba(17,20,24,0.18)] md:block">
            <span className="block h-full w-full overflow-hidden rounded-[22px]"><Img src={logo} /></span>
          </span>
          <span className="min-w-0 flex-grow md:pb-[6px]">
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h1 className="m-0 font-display text-[28px] font-semibold leading-tight tracking-[-0.6px] md:text-[44px] md:tracking-[-1.2px]">{r.name}</h1>
              {/* "New" until 5 ratings, then the average and how many */}
              <RatingBadge x={r} t={t} formatLocale={formatLocale} />
            </span>
            <span className="hidden text-base text-[#4C5A5E] md:block">{metaDesktop}</span>
            <span className="block text-[15px] text-[#4C5A5E] md:hidden">{metaPhone}</span>
          </span>
          <span className="hidden md:block md:pb-[10px]">
            <KitchenActions id={r.id} name={r.name} />
          </span>
        </div>

        {/* desktop: the info boxes */}
        <div className="mt-[22px] hidden overflow-hidden rounded-[18px] border border-[#E2E7E8] md:grid" style={{ gridTemplateColumns: `repeat(${boxes.length}, minmax(0, 1fr))` }}>
          {boxes.map((b, i) => (
            <div key={b.label} className={`px-[18px] py-[14px] ${i ? "border-l border-[#E2E7E8]" : ""}`}>
              <span className="text-[13px] text-[#4C5A5E]">{b.label}</span>
              <b className="mt-[2px] block truncate text-base">{b.value}</b>
            </div>
          ))}
        </div>

        {/* phone: chips */}
        <div className="mt-3 flex flex-wrap gap-2 md:hidden">
          <span className="flex h-9 items-center rounded-[10px] bg-[#F4F6F6] px-3 text-sm font-bold">{eta}</span>
          {feeChip && <span className="flex h-9 items-center rounded-[10px] bg-[#F4F6F6] px-3 text-sm">{feeChip}</span>}
          {offer && <span className="flex h-9 items-center rounded-[10px] bg-[#F6E7CC] px-3 text-sm">{offerBadge(offer, t, currency, formatLocale)}</span>}
          {closedNow && <span className="flex h-9 items-center rounded-[10px] bg-[#F1E3E1] px-3 text-sm font-bold">{hours.value}</span>}
          <KitchenActions id={r.id} name={r.name} compact />
        </div>
      </section>

      <KitchenMenu
        restaurant={{ id: r.id, name: r.name, slug: r.slug, city: r.city, currency }}
        categories={categories}
        deliverTo={place ? (place.address_id ? { address_id: place.address_id } : { lat: place.lat, lng: place.lng }) : null}
        closed={closedNow}
      />
    </div>
  );
}
