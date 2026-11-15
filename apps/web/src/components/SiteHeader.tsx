// The header (server part). Two shapes from the design:
// - no address yet (WebLanding): links, country, language, sign in;
// - an address (WebHome and inside the app): address, search, language, account, bag.
// On a phone (MWeb*): "Deliver to" + language + account, search on its own row.
import Link from "next/link";

import { getContext } from "@/lib/prefs";
import { AccountButton, AddressPill, BagButton, CountryMenu, LanguageMenu, SearchBox } from "./HeaderParts";
import { LogoMark } from "./Icons";

export async function SiteHeader() {
  const { t, place, country, directory } = await getContext();
  const countries = directory.countries.map((c) => ({ code: c.code, name: c.name }));
  const current = country ? { code: country.code, name: country.name } : null;
  const brand = (
    <Link href="/" aria-label={t("common.home")} className="flex shrink-0 items-center gap-[10px] text-[#111418] hover:text-[#111418]">
      <LogoMark />
      <span className="font-display text-[22px] font-bold tracking-[-0.4px]">{t("common.brand")}</span>
    </Link>
  );

  if (!place) {
    return (
      <header className="relative z-30 border-b border-[#E2E7E8] bg-white">
        <div className="mx-auto flex h-[64px] max-w-[1440px] items-center gap-3 px-4 md:h-[76px] md:gap-5 md:px-16">
          {brand}
          <span className="flex-grow" />
          <nav aria-label={t("header.where_we_deliver")} className="hidden items-center gap-5 lg:flex">
            <Link href="/cities" className="text-[15px] font-bold text-[#111418]">{t("header.where_we_deliver")}</Link>
            <Link href="/partner" className="text-[15px] font-bold text-[#111418]">{t("header.add_your_kitchen")}</Link>
            <Link href="/ride" className="text-[15px] font-bold text-[#111418]">{t("header.ride_with_us")}</Link>
          </nav>
          <div className="hidden md:block">
            <CountryMenu countries={countries} current={current} />
          </div>
          <LanguageMenu />
          <AccountButton />
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-30 border-b border-[#E2E7E8] bg-white">
      {/* desktop */}
      <div className="mx-auto hidden h-[76px] max-w-[1440px] items-center gap-4 px-16 md:flex">
        {brand}
        <AddressPill label={place.label} country={place.country} />
        <SearchBox cityPath={place.city_path ?? null} />
        <LanguageMenu />
        <AccountButton />
        <BagButton />
      </div>
      {/* phone */}
      <div className="md:hidden">
        <div className="flex items-center gap-[10px] px-5 pb-3 pt-[10px]">
          <AddressPill label={place.label} country={place.country} mobile />
          <LanguageMenu compact />
          <AccountButton />
        </div>
        <div className="px-5 pb-3">
          <SearchBox cityPath={place.city_path ?? null} compact />
        </div>
      </div>
    </header>
  );
}
