// /hyderabad, /boise: every kitchen we deliver from in the city, server-rendered
// with an ItemList for search engines.
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RestaurantCard } from "@/components/RestaurantCard";
import { cities, city, restaurantsIn, SITE } from "@/lib/server";

export const revalidate = 300;

export async function generateStaticParams() {
  return (await cities()).map((c) => ({ city: c.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ city: string }> }): Promise<Metadata> {
  const c = await city((await params).city);
  if (!c) return {};
  const title = `Food delivery in ${c.name}`;
  const description = `Order from ${c.restaurants} local kitchens in ${c.name}, ${c.region}. Every fee shown before you pay.`;
  return { title, description, alternates: { canonical: `/${c.slug}` }, openGraph: { title, description, url: `/${c.slug}` } };
}

export default async function CityPage({ params }: { params: Promise<{ city: string }> }) {
  const c = await city((await params).city);
  if (!c) notFound();
  const list = await restaurantsIn(c);
  const cuisines = [...new Set(list.flatMap((r) => r.cuisine_types))].slice(0, 8);
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `Restaurants delivering in ${c.name}`,
    itemListElement: list.map((r, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE}/${c.slug}/${r.slug}`, name: r.name })),
  };
  return (
    <div className="mx-auto max-w-content px-5 py-10 md:px-8">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <p className="text-sm font-bold uppercase tracking-[1.2px] text-peacock">{c.region}</p>
      <h1 className="mt-1 font-display text-5xl font-semibold tracking-[-1.2px]">Food delivery in {c.name}</h1>
      <p className="mt-3 max-w-2xl text-lg text-muted">
        {list.length} kitchens{cuisines.length ? ` — ${cuisines.join(", ")}` : ""}. Prices are the kitchens&apos; own; delivery, service and tax are shown, with who gets each, before you pay.
      </p>
      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{list.map((r) => <RestaurantCard key={r.id} r={r} />)}</div>
    </div>
  );
}
