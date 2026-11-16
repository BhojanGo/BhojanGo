// The sign-in pages' frame (WebSignIn, WebOTP, MWebSignIn): food photos from
// the visitor's area (data) on the left, the form on the right; on a phone,
// two photos above the form. The photos are kitchens' covers from discover.
// The photo panel is never taller than the window under the header (107 px with
// the test-site banner), so no photo is cut off below the fold at any size
// (1366 at 125 % lays out 1093 x 614; 1920 at 150 %, 1280 x 720).
import Link from "next/link";
import type { ReactNode } from "react";

import { Check } from "@/components/Icons";
import { libraryPhoto, photo } from "@/lib/format";
import { getContext } from "@/lib/prefs";
import { discover } from "@/lib/server";

async function photos(): Promise<string[]> {
  // The address's kitchens, else the visitor's served city's; else food from across the
  // country's live cities (photos only: no city is named, R8), else the country's hero dish.
  const { place, city, country, directory } = await getContext();
  const live = city ? [city.code] : (country?.regions.flatMap((r) => r.cities).filter((c) => c.status === "live").map((c) => c.code) ?? []).slice(0, 3);
  const found = place ? [await discover({ lat: place.lat, lng: place.lng })] : await Promise.all(live.map((code) => discover({ city: code })));
  const urls = found.flatMap((d) => (d?.restaurants ?? []).map((k) => k.cover_url)).filter(Boolean) as string[];
  const out = [...new Set(urls)].slice(0, 4);
  const hero = libraryPhoto(country?.hero_photo ?? directory.hero_photo);
  return out.length ? out : hero ? [hero] : [];
}

function Tile({ src, className }: { src?: string; className?: string }) {
  const url = photo(src, 800);
  return (
    <span className={`block overflow-hidden rounded-[24px] bg-[#DDEBEC] ${className ?? ""}`}>
      {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
      {url && <img src={url} alt="" className="block h-full w-full object-cover" />}
    </span>
  );
}

export async function Shell({ children }: { children: ReactNode }) {
  const { t } = await getContext();
  const p = await photos();
  return (
    <div className="mx-auto grid max-w-[1440px] grid-cols-1 md:grid-cols-2">
      {/* phone: two photos, at most a third of the screen */}
      <div className="grid h-[clamp(140px,30svh,260px)] grid-cols-2 gap-[6px] p-[6px] md:hidden" aria-hidden="true">
        <Tile src={p[0]} />
        <Tile src={p[1]} />
      </div>
      {/* desktop: four photos and the promise */}
      <div className="relative hidden overflow-hidden md:sticky md:top-0 md:block md:h-[calc(100svh-107px)] md:min-h-[420px]">
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-2 p-2" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => <Tile key={i} src={p[i]} />)}
        </div>
        <div className="absolute bottom-6 left-6 right-6 rounded-[24px] bg-[rgba(17,20,24,0.84)] p-6 text-[#F2F5F5] lg:bottom-10 lg:left-10 lg:right-10 lg:p-7">
          <div className="text-h1 leading-[1.1]">{t("common.tagline")}</div>
          {/* a short window (a laptop at 125-150 %): the tagline alone, so the photos stay in view */}
          <ul className="m-0 mt-[14px] flex list-none flex-col gap-2 p-0 text-body text-[#C9D3D4] [@media(max-height:760px)]:hidden">
            {(["promise_fees", "promise_tip", "promise_refunds"] as const).map((k) => (
              <li key={k} className="flex items-center gap-2"><Check color="#8FD3D9" /> {t(`signin.${k}`)}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex min-w-0 flex-col px-4 pb-10 pt-6 md:min-h-[calc(100svh-107px)] md:px-8 md:py-10 lg:px-12 xl:px-[96px]">
        <div className="flex max-w-[440px] flex-grow flex-col md:justify-center">{children}</div>
        <p className="m-0 mt-8 text-small text-muted">
          {t("signin.agree_before")} <Link href="/terms">{t("signin.terms")}</Link> {t("signin.agree_and")} <Link href="/privacy">{t("signin.privacy")}</Link>.
        </p>
      </div>
    </div>
  );
}
