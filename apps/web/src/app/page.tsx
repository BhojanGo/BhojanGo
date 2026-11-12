// Home: the promise (real food, fair prices), how the fair bill works, and the
// kitchens in each city we deliver to.
import Link from "next/link";

import { RestaurantCard } from "@/components/RestaurantCard";
import { cities, exampleBill, restaurantsIn } from "@/lib/server";
import { FairBill } from "@bhojango/ui";
import { money } from "@bhojango/ui/bill";

export const revalidate = 300;

export default async function Home() {
  const list = await cities();
  const byCity = await Promise.all(list.map(async (c) => ({ city: c, restaurants: (await restaurantsIn(c)).slice(0, 6) })));
  return (
    <>
      <section className="bg-peacock-mist">
        <div className="mx-auto grid max-w-content items-center gap-10 px-5 py-14 md:grid-cols-[1.2fr_1fr] md:px-8 md:py-20">
          <div className="space-y-5">
            <h1 className="font-display text-5xl font-semibold leading-[1.02] tracking-[-1.5px] md:text-6xl">Real food.<br />Fair prices.</h1>
            <p className="max-w-md text-lg text-muted">Every fee shown before you pay — and who gets it: the kitchen, your rider, tax, and us.</p>
            <div className="flex flex-wrap gap-3">
              {list.map((c) => (
                <Link key={c.slug} href={`/${c.slug}`} className="inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white hover:bg-peacock-deep">
                  Order in {c.name}
                </Link>
              ))}
            </div>
          </div>
          <FairBillPromise city={list.find((c) => c.country === "IN") ?? list[0]} />
        </div>
      </section>
      {byCity.map(({ city, restaurants }) => (
        <section key={city.slug} className="mx-auto max-w-content px-5 pt-12 md:px-8" aria-labelledby={`c-${city.slug}`}>
          <div className="mb-5 flex items-baseline justify-between">
            <h2 id={`c-${city.slug}`} className="font-display text-3xl font-semibold tracking-[-0.6px]">Kitchens in {city.name}</h2>
            <Link href={`/${city.slug}`} className="text-sm font-bold text-peacock">All {city.restaurants} →</Link>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{restaurants.map((r) => <RestaurantCard key={r.id} r={r} />)}</div>
        </section>
      ))}
      <section className="mx-auto mt-16 grid max-w-content gap-6 px-5 md:grid-cols-3 md:px-8">
        {[
          ["See the whole bill first", "Food, delivery, service, tax and tip — each with who gets it. Nothing added at the end."],
          ["Kitchens set their prices", "The menu price is the kitchen's price. Offers say who pays for them: us or the kitchen."],
          ["Riders paid fairly", "Riders see the full pay before they accept, keep 100% of tips, and have an hourly floor."],
        ].map(([t, d]) => (
          <div key={t} className="rounded-card bg-white p-6">
            <h3 className="mb-2 text-lg font-extrabold">{t}</h3>
            <p className="text-muted">{d}</p>
          </div>
        ))}
      </section>
    </>
  );
}

async function FairBillPromise({ city }: { city: { code: string; name: string } | undefined }) {
  const ex = city ? await exampleBill(city.code) : null;
  if (!ex) return null;
  const a = ex.assumptions;
  return (
    <figure aria-label="An example of the fair bill" className="space-y-2">
      <FairBill lines={ex.lines as never} currency={ex.currency} className="shadow-float" />
      <figcaption className="text-xs text-muted">
        A real {ex.city_name} bill for {money(Number(a.food), ex.currency, { decimals: 0 })} of food, {Number(a.distance)} {a.distance_unit} away, at 8 pm with a {money(Number(a.tip), ex.currency, { decimals: 0 })} tip — priced with today&apos;s rules. Yours is worked out live for your order and address.
      </figcaption>
    </figure>
  );
}
