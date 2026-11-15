// Cards from the design (WebHome): a kitchen, an offer, a cuisine. Everything on
// them is data from /discover; words come from the messages.
import Link from "next/link";

import { money, photo } from "@/lib/format";
import type { KitchenCard as Kitchen, Offer } from "@/lib/server";
import { FavouriteHeart } from "./FavouriteHeart";

type T = (key: string, vars?: Record<string, string | number>) => string;

/** "10% off, up to ₹50", "Free delivery", built from the offer's own numbers (translatable). */
export function offerTitle(o: Offer, t: T, currency: string, formatLocale: string): string {
  const m = (v?: string | null) => money(v ?? 0, currency, formatLocale, { whole: true });
  switch (o.template) {
    case "percent_off":
      return o.max_discount ? t("offers.percent_off_upto", { percent: o.percent ?? "", max: m(o.max_discount) }) : t("offers.percent_off", { percent: o.percent ?? "" });
    case "first_order":
      return o.max_discount ? t("offers.first_order_upto", { percent: o.percent ?? "", max: m(o.max_discount) }) : t("offers.first_order", { percent: o.percent ?? "" });
    case "flat_off":
      return t("offers.flat_off", { amount: m(o.amount) });
    case "free_delivery":
      return t("offers.free_delivery");
    default:
      return o.title;
  }
}

/** Short form for a card's badge: "10% off · we pay". */
export function offerBadge(o: Offer, t: T, currency: string, formatLocale: string): string {
  const short = o.template === "percent_off" || o.template === "first_order" ? t("offers.percent_off", { percent: o.percent ?? "" }) : offerTitle(o, t, currency, formatLocale);
  return t(o.funded_by === "restaurant" ? "offers.badge_kitchen_pays" : "offers.badge_we_pay", { offer: short });
}

export function offerSubtitle(o: Offer, t: T, currency: string, formatLocale: string): string {
  const min = o.min_subtotal ? money(o.min_subtotal, currency, formatLocale, { whole: true }) : null;
  const kitchen = o.restaurant?.name as string | undefined;
  if (kitchen && min) return t("offers.kitchen_orders_over", { kitchen, amount: min });
  if (kitchen) return t("offers.kitchen_any", { kitchen });
  if (min) return t("offers.orders_over", { amount: min });
  return t("offers.every_order");
}

function Img({ src, alt = "", className }: { src: string | null; alt?: string; className?: string }) {
  if (!src) return <span aria-hidden="true" className={`block h-full w-full bg-[#EFF6F6] ${className ?? ""}`} />;
  // eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library, already optimised
  return <img src={src} alt={alt} loading="lazy" className={`block h-full w-full object-cover ${className ?? ""}`} />;
}

export function KitchenCard({ k, t, currency, formatLocale, distanceUnit }: { k: Kitchen; t: T; currency: string; formatLocale: string; distanceUnit: string }) {
  const fee = k.delivery_fee != null ? Number(k.delivery_fee) : null;
  const meta = [...k.cuisine_types.slice(0, 2), k.distance != null ? t(distanceUnit === "mi" ? "common.mi" : "common.km", { n: k.distance }) : k.area].filter(Boolean).join(" · ");
  return (
    <div className="relative">
      <Link href={k.path} className="block text-[#111418] hover:text-[#111418]">
        <div className="relative aspect-[4/3] overflow-hidden rounded-[20px]">
          <Img src={photo(k.cover_url, 800)} className="rounded-[20px]" />
          {k.offer && (
            <span className="absolute left-3 top-3 flex h-7 items-center rounded-full bg-[#111418] px-[10px] text-xs font-extrabold text-white">
              {offerBadge(k.offer, t, currency, formatLocale)}
            </span>
          )}
          {!k.open_now && <span className="absolute inset-0 bg-white/40" aria-hidden="true" />}
        </div>
        <div className="mt-3 flex items-baseline justify-between gap-2">
          <b className="truncate text-[17px]">{k.name}</b>
          {k.is_new && <span className="shrink-0 rounded-md bg-[#DDEBEC] px-2 py-[3px] text-xs font-extrabold text-[#083F46]">{t("common.new")}</span>}
        </div>
        <div className="mt-1 truncate text-sm text-[#4C5A5E]">{meta}</div>
        <div className="mt-1 text-sm">
          <b>{t("common.minutes", { min: k.eta_min, max: k.eta_max })}</b>
          {fee !== null && (
            <>
              {" · "}
              {k.free_delivery || fee === 0 ? (
                <b className="text-[#0B5D66]">{t("common.free_delivery")}</b>
              ) : (
                t("common.delivery_fee", { fee: money(fee, currency, formatLocale, { whole: true }) })
              )}
            </>
          )}
          {!k.open_now && k.opens_at && <span className="text-[#4C5A5E]"> · {t("common.closed_opens", { time: new Date(k.opens_at).toLocaleTimeString(formatLocale, { hour: "numeric", minute: "2-digit" }) })}</span>}
        </div>
      </Link>
      <div className="absolute right-3 top-3">
        <FavouriteHeart kind="restaurant" id={k.id} name={k.name} />
      </div>
    </div>
  );
}

const OFFER_TINTS = ["#F6E7CC", "#DDEBEC", "#F1E3E1"];

export function OfferCard({ o, i, t, currency, formatLocale, fallbackPhoto, href }: { o: Offer; i: number; t: T; currency: string; formatLocale: string; fallbackPhoto?: string | null; href?: string }) {
  const img = photo((o.restaurant?.cover_url as string | null | undefined) ?? fallbackPhoto ?? null, 800);
  return (
    <Link href={href ?? (o.restaurant?.path as string | undefined) ?? "#kitchens"} style={{ background: OFFER_TINTS[i % 3] }} className="flex h-[150px] overflow-hidden rounded-[20px] text-[#111418] hover:text-[#111418]">
      <span className="flex flex-grow flex-col justify-center py-5 pl-6 pr-5">
        <b className="font-display text-[22px] font-semibold tracking-[-0.4px]">{offerTitle(o, t, currency, formatLocale)}</b>
        <span className="mt-1 text-sm text-[#24383B]">{offerSubtitle(o, t, currency, formatLocale)}</span>
        <span className="mt-[10px] text-xs font-extrabold uppercase text-[#4C5A5E]">{o.funded_by === "restaurant" ? t("common.kitchen_pays_caps") : t("common.bhojango_pays")}</span>
      </span>
      <span className="hidden w-[170px] shrink-0 sm:block"><Img src={img} /></span>
    </Link>
  );
}

export function CuisineTile({ name, image, href }: { name: string; image: string | null; href: string }) {
  return (
    <Link href={href} className="w-[72px] shrink-0 text-center text-[#111418] hover:text-[#111418] md:w-[150px]">
      <span className="block h-[72px] w-[72px] overflow-hidden rounded-full border-[3px] border-white shadow-[0_0_0_1px_#E2E7E8] md:h-[150px] md:w-[150px]">
        <Img src={photo(image, 400)} className="rounded-full" />
      </span>
      <span className="mt-[6px] block text-[13px] font-bold md:mt-3 md:text-[15px]">{name}</span>
    </Link>
  );
}

/** A cuisine's picture is its first kitchen's cover (data, not a mapping in code). */
export function cuisinePhotos(kitchens: Kitchen[]): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  for (const k of kitchens) for (const c of k.cuisine_types) if (!(c in out) && k.cover_url) out[c] = k.cover_url;
  return out;
}
