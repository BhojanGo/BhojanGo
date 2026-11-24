// Cards from the design (WebHome): a kitchen, an offer, a cuisine. Everything on
// them is data from /discover; words come from the messages.
import { cuisineName, opensLabel, wallClock } from "@bhojango/i18n";
import Link from "next/link";

import { ratingOf } from "@/lib/contract";
import { money, photo } from "@/lib/format";
import type { KitchenCard as Kitchen, Offer } from "@/lib/server";
import { FavouriteHeart } from "./FavouriteHeart";
import { kitchenPhoto, KitchenPhoto } from "./KitchenPhoto";

type T = (key: string, vars?: Record<string, string | number>) => string;

/** "10% off, up to ₹50", "Free delivery", built from the offer's own numbers (translatable). */
export function offerTitle(o: Offer, t: T, currency: string, formatLocale: string): string {
  const m = (v?: string | null) => money(v ?? 0, currency, formatLocale);
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
  // "0" (or no minimum) means every order qualifies: no "Orders over 0".
  const min = o.min_subtotal && Number(o.min_subtotal) > 0 ? money(o.min_subtotal, currency, formatLocale) : null;
  const kitchen = o.restaurant?.name as string | undefined;
  if (kitchen && min) return t("offers.kitchen_orders_over", { kitchen, amount: min });
  if (kitchen) return t("offers.kitchen_any", { kitchen });
  if (min) return t("offers.orders_over", { amount: min });
  return t("offers.every_order");
}

/** R27: "Closed · opens 6:30 am" (another day: "Closed · opens Sat 6:30 am", the weekday in the visitor's language),
 *  on the kitchen's city clock: `timeZone` (discover's), else the time's own offset. */
function closedOpens(t: T, iso: string, formatLocale: string, timeZone?: string | null, language?: string | null): string {
  if (timeZone) return opensLabel(t, iso, { timeZone, formatLocale, language }) ?? t("common.closed_opens", { time: iso });
  const m = /T(\d{2}):(\d{2})/.exec(iso);
  const time = m ? wallClock(`${m[1]}:${m[2]}`, formatLocale) : null;
  return t("common.closed_opens", { time: time ?? iso });
}

function Img({ src, alt = "", className }: { src: string | null; alt?: string; className?: string }) {
  if (!src) return <span aria-hidden="true" className={`block h-full w-full bg-[#EFF6F6] ${className ?? ""}`} />;
  // eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library, already optimised
  return <img src={src} alt={alt} loading="lazy" className={`block h-full w-full object-cover ${className ?? ""}`} />;
}

/** "New" until a kitchen has 5 ratings, then "★4.6 (23)" (rating_display, or the same rule over rating/review_count). */
export function RatingBadge({ x, t, formatLocale }: { x: Parameters<typeof ratingOf>[0]; t: T; formatLocale: string }) {
  const r = ratingOf(x);
  if (r.new) return <span className="shrink-0 rounded-md bg-[#DDEBEC] px-2 py-[3px] text-caption text-[#083F46]">{t("common.new")}</span>;
  const stars = new Intl.NumberFormat(formatLocale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(r.stars);
  return (
    <span className="shrink-0 text-label" aria-label={t("common.rating_label", { stars, count: r.count })}>
      <span aria-hidden="true">{t("common.rating_short", { stars, count: r.count })}</span>
    </span>
  );
}

export function KitchenCard({ k, t, currency, formatLocale, distanceUnit, feeFrom, timeZone, language }: {
  k: Kitchen;
  t: T;
  currency: string;
  formatLocale: string;
  /** The kitchens' city time zone (GET /discover's timezone) and the visitor's language: "opens Sat 6:30 am". */
  timeZone?: string | null;
  language?: string | null;
  distanceUnit: string;
  /** No address yet: the city's lowest delivery fee ("from … delivery"). */
  feeFrom?: number | null;
}) {
  const fee = k.delivery_fee != null ? Number(k.delivery_fee) : null;
  // R36: "★4.4 (9) · Thai · 0.9 mi" under the name (the rating never shares the name's line)
  const meta = [k.cuisine_types[0] ? cuisineName(t, k.cuisine_types[0]) : null,
    k.distance != null ? t(distanceUnit === "mi" ? "common.mi" : "common.km", { n: k.distance }) : k.area].filter(Boolean).join(" · ");
  const status = cardStatus(k);
  return (
    <div className="relative" data-testid={`kitchen-card-${k.slug}`} data-status={status}>
      <Link href={k.path} className="block text-[#111418] hover:text-[#111418]">
        {/* R36: a wide photo (2.4:1), so about three kitchens show on a phone screen */}
        <div className="relative aspect-[12/5] overflow-hidden rounded-[18px]" data-testid="card-photo">
          {/* photo_url: its cover, else a dish of its own, else its cuisine's photo; else the branded tile */}
          <KitchenPhoto src={photo(kitchenPhoto(k), 800)} className="h-full w-full rounded-[18px]" />
          {k.offer && (
            <span className="absolute left-3 top-3 flex h-7 items-center rounded-full bg-[#111418] px-[10px] text-caption text-white">
              {offerBadge(k.offer, t, currency, formatLocale)}
            </span>
          )}
          {status !== "open" && <span className="absolute inset-0 bg-white/40" aria-hidden="true" />}
        </div>
        <b className="mt-[10px] line-clamp-2 break-words text-h3" data-testid="card-name">{k.name}</b>
        <div className="mt-1 flex min-w-0 items-baseline gap-[6px] text-small">
          <RatingBadge x={k} t={t} formatLocale={formatLocale} />
          {meta && <span className="min-w-0 truncate text-muted">· {meta}</span>}
        </div>
        <div className="mt-[2px] text-small tabular-nums" data-testid="card-status">
          {status === "open" ? (
            <>
              <b>{t("common.minutes", { min: k.eta_min, max: k.eta_max })}</b>
              {fee !== null && (
                <>
                  {" · "}
                  {k.free_delivery || fee === 0 ? (
                    <b className="text-[#0B5D66]">{t("common.free_delivery")}</b>
                  ) : (
                    t("common.delivery_fee", { fee: money(fee, currency, formatLocale) })
                  )}
                </>
              )}
              {fee === null && feeFrom != null && (
                <>
                  {" · "}
                  {feeFrom === 0 ? <b className="text-[#0B5D66]">{t("common.free_delivery")}</b> : t("common.delivery_from", { fee: money(feeFrom, currency, formatLocale) })}
                </>
              )}
            </>
          ) : status === "pickup_only" ? (
            <b className="text-[#0B5D66]" data-testid="pickup-only">{t("common.pickup_only")}</b>
          ) : status === "too_far" ? (
            <span className="text-muted" data-testid="too-far">{t("common.too_far")}</span>
          ) : k.closed_for_now ? (
            <span className="text-muted" data-testid="closed-for-now">{t("kitchen.closed_for_now")}</span>
          ) : k.not_taking_orders ? (
            <span className="text-muted" data-testid="not-taking-orders">{t("kitchen.not_taking_orders")}</span>
          ) : (
            <span className="text-muted" data-testid="closed">{k.opens_at ? closedOpens(t, k.opens_at, formatLocale, timeZone, language) : t("common.closed")}</span>
          )}
        </div>
      </Link>
      <div className="absolute right-3 top-3">
        <FavouriteHeart kind="restaurant" id={k.id} name={k.name} />
      </div>
    </div>
  );
}

/** R36: the card's third line: minutes and fee, pickup only, closed until when, or too far. */
export function cardStatus(k: Pick<Kitchen, "open_now" | "deliverable"> & { pickup_only?: boolean }): "open" | "pickup_only" | "closed" | "too_far" {
  // too far and no pickup can never be ordered here, open or not; a pickup-only kitchen that's closed says when it opens
  if (k.deliverable === false && !k.pickup_only) return "too_far";
  if (!k.open_now) return "closed";
  if (k.deliverable === false) return "pickup_only";
  return "open";
}

const OFFER_TINTS = ["#F6E7CC", "#DDEBEC", "#F1E3E1"];

export function OfferCard({ o, i, t, currency, formatLocale, fallbackPhoto, href }: { o: Offer; i: number; t: T; currency: string; formatLocale: string; fallbackPhoto?: string | null; href?: string }) {
  const img = photo(kitchenPhoto(o.restaurant as { photo_url?: string | null; cover_url?: string | null } | null) ?? fallbackPhoto ?? null, 800);
  return (
    // R27: at least 150 px, taller when a translated headline needs two lines (Telugu was cut off).
    <Link href={href ?? (o.restaurant?.path as string | undefined) ?? "#kitchens"} style={{ background: OFFER_TINTS[i % 3] }} className="flex min-h-[150px] overflow-hidden rounded-[20px] text-[#111418] hover:text-[#111418]">
      <span className="flex min-w-0 flex-grow flex-col justify-center py-5 pl-6 pr-5 [overflow-wrap:anywhere]">
        <b className="text-h2">{offerTitle(o, t, currency, formatLocale)}</b>
        <span className="mt-1 text-small text-[#24383B]">{offerSubtitle(o, t, currency, formatLocale)}</span>
        <span className="mt-[10px] text-caption text-muted">{o.funded_by === "restaurant" ? t("common.kitchen_pays_caps") : t("common.bhojango_pays")}</span>
      </span>
      {img && <span className="hidden w-[170px] shrink-0 sm:block"><Img src={img} /></span>}
    </Link>
  );
}

export function CuisineTile({ name, image, href }: { name: string; image: string | null; href: string }) {
  return (
    <Link href={href} className="w-[72px] shrink-0 text-center text-[#111418] hover:text-[#111418] md:w-[120px]">
      <span className="block h-[72px] w-[72px] overflow-hidden rounded-full border-[3px] border-white shadow-[0_0_0_1px_#E2E7E8] md:h-[150px] md:w-[120px]">
        <KitchenPhoto src={photo(image, 400)} className="h-full w-full rounded-full" />
      </span>
      <span className="mt-[6px] block break-words text-label [hyphens:auto] md:mt-3">{name}</span>
    </Link>
  );
}
