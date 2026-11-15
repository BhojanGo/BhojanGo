// First visit, no address (WebLanding): address first, no city named in the
// template. The hero photo is the visitor's country's choice in Markets; the
// example bill, the other photos and the cuisines come from the first live city
// of that country; the directory from Markets.
import Link from "next/link";

import { AddressBox } from "@/components/AddressBox";
import { LandingDirectory } from "@/components/discover/DirectoryBrowser";
import { firstLiveCity } from "@/components/discover/places";
import { MoneyBar } from "@/components/FairBill";
import { HintRow } from "@/components/HintRow";
import { NotifyMe } from "@/components/NotifyMe";
import { cuisineTiles } from "@/lib/contract";
import { libraryPhoto, photo } from "@/lib/format";
import { getContext } from "@/lib/prefs";
import { discover, exampleBill } from "@/lib/server";
import { RecruitCards } from "./Recruit";

export async function Landing() {
  const { t, country, countrySource, directory: dir } = await getContext();
  const city = firstLiveCity(dir, country?.code);
  const [d, bill] = city ? await Promise.all([discover({ city: city.code }), exampleBill(city.code)]) : [null, null];
  // The hero is the country's chosen library photo (Markets -> country -> Hero dish; a default when unset).
  const hero = libraryPhoto(country?.hero_photo ?? dir.hero_photo);
  // One tile per cuisine with 2+ kitchens and a photo of its own; no photo twice on the page (the hero's included).
  const tiles = cuisineTiles(d, new Set(hero ? [hero] : []));
  const steps = [1, 2, 3] as const;

  return (
    <>
      <section className="bg-[linear-gradient(180deg,#EFF6F6_0%,#FFFFFF_100%)]">
        <div className="mx-auto grid max-w-[1440px] items-center gap-10 px-5 pb-14 pt-10 md:px-16 md:pb-20 md:pt-[72px] lg:grid-cols-[1fr_560px] lg:gap-14">
          <div>
            <h1 className="m-0 whitespace-pre-line font-display text-[52px] font-semibold leading-[0.98] tracking-[-1.8px] md:text-[80px] md:tracking-[-2.8px]">
              {t("home.hero_title")}
            </h1>
            <p className="mt-[22px] max-w-[560px] text-lg leading-[1.5] text-[#4C5A5E] md:text-xl">{t("home.hero_body")}</p>
            <div className="mt-9">
              <AddressBox size="hero" country={country?.code ?? null} />
            </div>
            <HintRow currentCountry={country?.code ?? null} countrySource={countrySource} />
          </div>
          {(hero || bill) && (
            <div className="relative h-[420px] md:h-[520px]">
              <div className="absolute right-0 top-0 h-[340px] w-full overflow-hidden rounded-[36px] bg-[#F6E7CC] md:h-[480px] md:w-[480px] md:rounded-[48px]">
                {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
                {hero && <img src={hero} alt="" data-testid="landing-hero" className="block h-full w-full object-cover" />}
              </div>
              {bill && (
                <div className="absolute bottom-0 left-4 w-[300px] max-w-[calc(100%-32px)] rounded-[24px] bg-white p-5 shadow-[0_2px_4px_rgba(17,20,24,0.06),0_24px_48px_rgba(17,20,24,0.14)] md:left-0">
                  <div className="mb-[14px] text-xs font-extrabold uppercase tracking-[1px] text-[#0B5D66]">{t("bill.who_gets")}</div>
                  <MoneyBar lines={bill.lines} t={t} />
                  <p className="mt-3 text-xs text-[#4C5A5E]">{t("bill.exact_note")}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section aria-label={t("home.how_it_works")} className="mx-auto max-w-[1440px] px-5 md:px-16">
        <ol className="m-0 grid list-none gap-4 p-0 md:grid-cols-3 md:gap-6">
          {steps.map((n) => (
            <li key={n} className="rounded-[24px] bg-[#F4F6F6] p-5 md:p-7">
              <div aria-hidden="true" className="font-display text-[32px] font-semibold tracking-[-1px] text-[#0B5D66] md:text-[40px]">{n}</div>
              <b className="mt-2 block text-lg">{t(`home.step${n}_title`)}</b>
              <p className="mt-[6px] text-[15px] leading-[1.5] text-[#4C5A5E]">{t(`home.step${n}_body`)}</p>
            </li>
          ))}
        </ol>
      </section>

      {city && tiles.length > 0 && (
        <section aria-labelledby="cooking" className="mx-auto max-w-[1440px] px-5 pt-14 md:px-16 md:pt-[72px]">
          <div className="flex flex-col gap-1 md:flex-row md:items-baseline md:justify-between">
            <h2 id="cooking" className="m-0 font-display text-[28px] font-semibold tracking-[-0.8px] md:text-[36px]">{t("home.cooking_title")}</h2>
            <span className="text-[15px] text-[#4C5A5E]">{t("home.cooking_note")}</span>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 md:gap-4 lg:grid-cols-8">
            {tiles.map(({ name, photo: src }) => (
              <Link key={name} href={`${city.path}?cuisine=${encodeURIComponent(name)}`} className="relative block aspect-square overflow-hidden rounded-[20px] bg-[#EFF6F6] text-white hover:text-white">
                {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
                <img src={photo(src, 400) ?? undefined} alt="" loading="lazy" className="block h-full w-full object-cover" />
                <span className="absolute inset-x-0 bottom-0 bg-[linear-gradient(180deg,rgba(17,20,24,0)_0%,rgba(17,20,24,0.72)_100%)] px-[14px] pb-3 pt-10 text-base font-extrabold">{name}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <LandingDirectory dir={dir} />
      <div className="mx-auto max-w-[1440px] px-5 pt-6 md:px-16">
        <NotifyMe source="suggest_city" />
      </div>

      <RecruitCards />
      <div className="h-14 md:h-20" />
    </>
  );
}
