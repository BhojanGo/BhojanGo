// The sign-in pages' frame (WebSignIn, WebOTP, MWebSignIn): food photos from
// the visitor's area (data) on the left, the form on the right; on a phone,
// two photos above the form. The photos are kitchens' covers from discover.
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
    <div className="mx-auto grid max-w-[1440px] md:min-h-[820px] md:grid-cols-2">
      {/* phone: two photos */}
      <div className="grid h-[260px] grid-cols-2 gap-[6px] p-[6px] md:hidden" aria-hidden="true">
        <Tile src={p[0]} />
        <Tile src={p[1]} />
      </div>
      {/* desktop: four photos and the promise */}
      <div className="relative hidden overflow-hidden md:block">
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-2 p-2" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => <Tile key={i} src={p[i]} />)}
        </div>
        <div className="absolute bottom-10 left-10 right-10 rounded-[24px] bg-[rgba(17,20,24,0.84)] p-7 text-[#F2F5F5]">
          <div className="text-h1 leading-[1.1] tracking-[-0.8px]">{t("common.tagline")}</div>
          <ul className="m-0 mt-[14px] flex list-none flex-col gap-2 p-0 text-body text-[#C9D3D4]">
            {(["promise_fees", "promise_tip", "promise_refunds"] as const).map((k) => (
              <li key={k} className="flex items-center gap-2"><Check color="#8FD3D9" /> {t(`signin.${k}`)}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex flex-col px-5 pb-10 pt-6 md:px-[96px] md:py-10">
        <div className="flex max-w-[440px] flex-grow flex-col md:justify-center">{children}</div>
        <p className="m-0 mt-8 text-small text-muted">
          {t("signin.agree_before")} <Link href="/terms">{t("signin.terms")}</Link> {t("signin.agree_and")} <Link href="/privacy">{t("signin.privacy")}</Link>.
        </p>
      </div>
    </div>
  );
}
