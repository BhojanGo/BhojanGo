// /hyderabad/spice-route-kitchen-madhapur: the kitchen and its menu,
// server-rendered with Restaurant + Menu structured data; adding to the bag
// happens in the browser.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BagPanel, MenuBoard } from "@/components/MenuBoard";
import { citySlug } from "@/components/RestaurantCard";
import { menu, restaurant, SITE } from "@/lib/server";
import { PlateImage } from "@bhojango/ui";

export const revalidate = 120;

type Params = Promise<{ city: string; slug: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params;
  const r = await restaurant(slug);
  if (!r) return {};
  const title = `${r.name}, ${r.city} — order online`;
  const description = `${r.cuisine_types.join(", ")} from ${r.name} in ${r.city}, delivered in ${r.delivery_time_min}–${r.delivery_time_max} min. See the whole bill before you pay.`;
  const url = `/${citySlug(r.city)}/${r.slug}`;
  return { title, description, alternates: { canonical: url }, openGraph: { title, description, url } };
}

export default async function RestaurantPage({ params }: { params: Params }) {
  const { city, slug } = await params;
  const r = await restaurant(slug);
  if (!r || citySlug(r.city) !== city) notFound();
  const m = await menu(r.id);
  const categories = m ? [...m.categories, ...(m.uncategorized_items.length ? [{ name: "More", items: m.uncategorized_items }] : [])] : [];
  const address = r.address as { street?: string; city?: string; state?: string; zip?: string; country?: string; landmark?: string };
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Restaurant",
    name: r.name,
    url: `${SITE}/${city}/${r.slug}`,
    servesCuisine: r.cuisine_types,
    priceRange: r.currency === "INR" ? "₹₹" : "$$",
    address: { "@type": "PostalAddress", streetAddress: address.street, addressLocality: address.city ?? r.city, addressRegion: address.state,
      postalCode: address.zip, addressCountry: address.country },
    ...(r.lat != null && r.lng != null ? { geo: { "@type": "GeoCoordinates", latitude: r.lat, longitude: r.lng } } : {}),
    ...(Number(r.review_count) > 0 ? { aggregateRating: { "@type": "AggregateRating", ratingValue: r.rating, reviewCount: r.review_count } } : {}),
    hasMenu: {
      "@type": "Menu",
      hasMenuSection: categories.map((c) => ({
        "@type": "MenuSection", name: c.name,
        hasMenuItem: c.items.map((i) => ({ "@type": "MenuItem", name: i.name, description: i.description ?? undefined,
          offers: { "@type": "Offer", price: String(i.price), priceCurrency: r.currency } })),
      })),
    },
  };
  return (
    <div className="mx-auto max-w-content px-5 pb-16 md:px-8">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <nav aria-label="Breadcrumb" className="py-4 text-sm text-muted">
        <Link href="/" className="hover:text-peacock">Home</Link> / <Link href={`/${city}`} className="hover:text-peacock">{r.city}</Link> / <span className="text-kohl">{r.name}</span>
      </nav>
      <div className="grid gap-8 md:grid-cols-[1fr_360px]">
        <div>
          <div className="overflow-hidden rounded-card bg-white">
            <PlateImage src={r.cover_url ?? r.logo_url ?? undefined} alt="" className="h-56" size={180} />
            <div className="space-y-2 p-6">
              <h1 className="font-display text-4xl font-semibold tracking-[-1px]">{r.name}</h1>
              <p className="text-muted">
                {r.cuisine_types.join(" · ")} · {r.delivery_time_min}–{r.delivery_time_max} min
                {Number(r.rating) > 0 ? <> · <span className="text-kesar">★</span> {Number(r.rating).toFixed(1)}</> : null}
                {address.landmark ? ` · ${address.landmark}` : ""}
              </p>
              {r.description ? <p className="max-w-2xl">{r.description}</p> : null}
            </div>
          </div>
          <MenuBoard restaurant={{ id: r.id, name: r.name, slug: r.slug, city: r.city, currency: r.currency }} categories={categories as never} />
        </div>
        <aside className="hidden md:block"><div className="sticky top-24"><BagPanel /></div></aside>
      </div>
    </div>
  );
}
