// The header (server part), minimal (R6): no country selector; the language is a
// small globe + code pill. Where the visitor is shows on the home page itself
// (the location line), not here. Two shapes:
// - no address yet (WebLanding): links, language pill, sign in;
// - an address (WebHome and inside the app): search, language pill, account, bag. The
//   address itself is on the page (the home's "N kitchens deliver to <address>" opens it).
// On a phone (MWeb*): the same pill + account, search on its own row.
import Link from "next/link";

import { getContext } from "@/lib/prefs";
import { discover } from "@/lib/server";
import { AccountButton, BagButton, LanguageMenu, SearchBox } from "./HeaderParts";
import { LogoMark } from "./Icons";

export async function SiteHeader() {
  const { t, place } = await getContext();
  const brand = (
    <Link href="/" aria-label={t("common.home")} className="flex shrink-0 items-center gap-[10px] text-[#111418] hover:text-[#111418]">
      <LogoMark />
      <span className="text-h2 tracking-[-0.4px]">{t("common.brand")}</span>
    </Link>
  );

  if (!place) {
    return (
      <header className="relative z-30 border-b border-[#E2E7E8] bg-white print:hidden">
        <div className="mx-auto flex h-[64px] max-w-[1440px] items-center gap-3 px-4 md:h-[76px] md:gap-5 md:px-16">
          {brand}
          <span className="flex-grow" />
          <nav aria-label={t("header.where_we_deliver")} className="hidden items-center gap-5 lg:flex">
            <Link href="/cities" className="text-label text-[#111418]">{t("header.where_we_deliver")}</Link>
            <Link href="/partner" className="text-label text-[#111418]">{t("header.add_your_kitchen")}</Link>
            <Link href="/deliver" className="text-label text-[#111418]">{t("header.ride_with_us")}</Link>
          </nav>
          <LanguageMenu />
          <AccountButton />
        </div>
      </header>
    );
  }

  // "Search biryani, dosa, kitchens…" from what's actually near the address (data, not copy).
  const near = place.served === false ? null : await discover({ lat: place.lat, lng: place.lng });
  const top = ((near?.cuisines ?? []) as { name: string }[]).slice(0, 2).map((c) => c.name.toLowerCase());
  const placeholder = top.length === 2 ? t("common.search_placeholder_near", { a: top[0]!, b: top[1]! }) : t("common.search_placeholder");
  return (
    <header className="sticky top-0 z-30 border-b border-[#E2E7E8] bg-white print:hidden">
      {/* desktop */}
      <div className="mx-auto hidden h-[76px] max-w-[1440px] items-center gap-4 px-16 md:flex">
        {brand}
        <SearchBox cityPath={place.city_path ?? null} placeholder={placeholder} />
        <LanguageMenu />
        <AccountButton />
        <BagButton />
      </div>
      {/* phone */}
      <div className="md:hidden">
        <div className="flex items-center gap-[10px] px-5 pb-3 pt-[10px]">
          <Link href="/" aria-label={t("common.home")} className="shrink-0">
            <LogoMark />
          </Link>
          <span className="flex-grow" />
          <LanguageMenu />
          <AccountButton />
        </div>
        <div className="px-5 pb-3">
          <SearchBox cityPath={place.city_path ?? null} placeholder={placeholder} compact />
        </div>
      </div>
    </header>
  );
}
