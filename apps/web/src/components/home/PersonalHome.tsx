// The personal home for an address we serve (WebHome / MWebHome): kitchens,
// cuisines and offers for that address from /discover. No marketing here.
import { cuisineName } from "@bhojango/i18n";

import { CuisineTile, OfferCard } from "@/components/Cards";
import { flatCities } from "@/components/discover/places";
import { kitchenPhoto } from "@/components/KitchenPhoto";
import { cuisineTiles } from "@/lib/contract";
import { getContext, type Place } from "@/lib/prefs";
import type { Discover } from "@/lib/server";
import { HomeFeed } from "./HomeFeed";
import { LocationLine } from "./LocationLine";

export async function PersonalHome({ place, d }: { place: Place; d: Discover }) {
  const { t, directory: dir, formatLocale, country } = await getContext();
  const kitchens = d.restaurants ?? [];
  const offers = d.offers ?? [];
  const currency = d.currency ?? country?.currency ?? "USD";
  const city = flatCities(dir).find((c) => c.code === (place.city_code ?? (d.city?.code as string | undefined)));
  const cityPath = place.city_path ?? (d.city?.path as string | undefined) ?? city?.path ?? "/cities";
  // Cuisines with 2+ kitchens, each with a photo of its own (never the same photo twice).
  const cuisines = cuisineTiles(d);
  const cover = (o: (typeof offers)[number]) =>
    kitchenPhoto(kitchens.find((k) => k.id === (o.restaurant?.id as string | undefined))) ?? kitchenPhoto(kitchens[0]);

  const cravings = cuisines.length > 0 && (
    <section aria-labelledby="craving">
      <h2 id="craving" className="sr-only m-0 text-h2 md:not-sr-only">{t("home.craving")}</h2>
      <div className="-mx-4 flex gap-[14px] overflow-x-auto px-4 py-1 md:mx-0 md:mt-5 md:gap-5 md:px-0">
        {cuisines.map(({ name, photo }) => (
          <CuisineTile key={name} name={cuisineName(t, name)} image={photo} href={`${cityPath}?cuisine=${encodeURIComponent(name)}`} />
        ))}
      </div>
    </section>
  );

  const offerBlock = offers.length > 0 && (
    <section aria-labelledby="offers-near">
      <h2 id="offers-near" className="m-0 text-h2">{t("offers.near_you")}</h2>
      <p className="mt-1 text-body text-muted">{t("offers.who_pays")}</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {offers.slice(0, 3).map((o, i) => (
          <OfferCard key={o.id} o={o} i={i} t={t} currency={currency} formatLocale={formatLocale} fallbackPhoto={cover(o)} />
        ))}
      </div>
    </section>
  );

  return (
    <>
      {/* "<city>, <CC> · Change city": one line above the home content (R6) */}
      <div className="container-page pt-4 md:pt-6">
        <LocationLine />
      </div>
      <HomeFeed
        kitchens={kitchens}
        placeLabel={place.label}
        placeCountry={place.country}
        cityName={city?.name ?? ((d.city?.name as string | undefined) ?? "")}
        currency={currency}
        formatLocale={formatLocale}
        distanceUnit={d.distance_unit ?? country?.distance_unit ?? "km"}
        timeZone={d.timezone ?? country?.timezone ?? null}
        cravings={cravings}
        offers={offerBlock}
        freeDeliveryChip={!!d.free_delivery_chip}
      />
    </>
  );
}
