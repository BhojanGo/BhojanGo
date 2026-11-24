// A kitchen on home and search, as the website's KitchenCard: its own cover or
// initials tile, the offer with who pays, the heart, "New" or "★4.6 (23)",
// cuisines and distance, minutes and the delivery fee, closed until when.
import { color, cuisineName, radius, space, textFont, Txt, type, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { Pressable, Text, useWindowDimensions, View } from "react-native";

import { offerBadge, ratingOf, type KitchenCard as Kitchen } from "../lib/contract";
import { kitchenPhoto, KitchenCover } from "../lib/plate";
import { useDiscoverStore } from "../lib/restaurants";
import { FavouriteHeart } from "./Heart";

/** "New" until a kitchen has 5 ratings, then "★4.6 (23)". */
export function RatingBadge({ x, testID }: { x: Parameters<typeof ratingOf>[0]; testID?: string }) {
  const { t, number } = useI18n();
  const r = ratingOf(x);
  if (r.new) {
    return (
      <View testID={testID ?? "rating-new"} style={{ borderRadius: 6, backgroundColor: color.peacockTint, paddingHorizontal: 8, paddingVertical: 3 }}>
        <Text style={[type.caption, { color: color.peacockDeep }]}>{t("common.new")}</Text>
      </View>
    );
  }
  const stars = number(r.stars, 1);
  return (
    <Text testID={testID ?? "rating"} accessibilityLabel={t("common.rating_label", { stars, count: r.count })} style={[type.label, { color: color.kohl }]}>
      {t("common.rating_short", { stars, count: r.count })}
    </Text>
  );
}

/** A distance as /discover sends it (already in the country's unit). */
export function useCardDistance() {
  const { t, number } = useI18n();
  return (value: number | null | undefined, unit: string | null | undefined) =>
    value != null && unit ? t(`app.units.${unit}`, { value: number(value, 1) }) : null;
}

/** R36: the list's photo ratio (wide, so about three restaurants show on a phone screen). */
export const CARD_PHOTO_RATIO = 2.4;

/** R36: what the card's third line says: minutes and fee, pickup only, closed until when, or too far. */
export function cardStatus(k: Pick<Kitchen, "open_now" | "deliverable" | "closed_for_now" | "not_taking_orders" | "opens_at"> & { pickup_only?: boolean }):
  "open" | "pickup_only" | "closed" | "too_far" {
  // too far and no pickup can never be ordered here, open or not; a pickup-only kitchen that's closed says when it opens
  if (k.deliverable === false && !k.pickup_only) return "too_far";
  if (!k.open_now) return "closed";
  if (k.deliverable === false) return "pickup_only";
  return "open";
}

export function KitchenCard({ k, currency, unit, compact = false }: { k: Kitchen; currency?: string | null; unit?: string | null; compact?: boolean }) {
  const { t, money, opens } = useI18n();
  const dist = useCardDistance();
  const { width } = useWindowDimensions();
  // R27: "Closed · opens 6:30 am" (another day: "Closed · opens Sat 6:30 am") on the kitchen's city clock.
  const zone = useDiscoverStore((s) => s.data?.timezone ?? null);
  const fee = k.delivery_fee != null ? Number(k.delivery_fee) : null;
  const status = cardStatus(k);
  // R36: one line under the name: rating, first cuisine, distance (the rating never shares the name's line)
  const meta = [k.cuisine_types[0] ? cuisineName(t, k.cuisine_types[0]) : null, dist(k.distance, unit) ?? k.area].filter(Boolean).join(" · ");
  const height = Math.round(Math.min(width - space[5] * 2, 560) / CARD_PHOTO_RATIO) - (compact ? 8 : 0);
  const dim = status !== "open";
  return (
    <View testID={`kitchen-card-${k.slug}`}>
      <Pressable accessibilityRole="button" accessibilityLabel={k.name} onPress={() => router.push(`/restaurant/${k.id}`)}
        style={{ backgroundColor: color.white, borderRadius: radius.card, overflow: "hidden" }}>
        <View testID="card-photo" style={{ height }}>
          <KitchenCover name={k.name} cover={kitchenPhoto(k)} height={height} />
          {k.offer ? (
            <View testID="offer-badge" style={{ position: "absolute", left: 10, top: 10, paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill, backgroundColor: color.kohl }}>
              <Text style={[type.caption, { color: color.white }]}>{offerBadge(k.offer, t, money, currency)}</Text>
            </View>
          ) : null}
          {dim ? <View style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 0, backgroundColor: "rgba(255,255,255,0.4)" }} /> : null}
        </View>
        <View style={{ paddingHorizontal: space[4], paddingTop: space[3], paddingBottom: space[4], gap: 3 }}>
          <Txt testID="card-name" variant="h3" numberOfLines={2}>{k.name}</Txt>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <RatingBadge x={k} />
            {meta ? <Text numberOfLines={1} style={[type.small, { color: color.muted, flexShrink: 1 }]}>· {meta}</Text> : null}
          </View>
          <Text testID="card-status" numberOfLines={1} style={[type.small, { color: color.kohl }]}>
            {status === "open" ? (
              <>
                <Text style={textFont("700")}>{t("common.minutes", { min: k.eta_min, max: k.eta_max })}</Text>
                {fee !== null ? " · " : ""}
                {fee !== null ? (
                  k.free_delivery || fee === 0 ? (
                    <Text style={[textFont("700"), { color: color.peacock }]}>{t("common.free_delivery")}</Text>
                  ) : (
                    t("common.delivery_fee", { fee: money(fee, currency) })
                  )
                ) : null}
              </>
            ) : status === "pickup_only" ? (
              <Text testID="pickup-only" style={[textFont("700"), { color: color.peacock }]}>{t("common.pickup_only")}</Text>
            ) : status === "too_far" ? (
              <Text testID="too-far" style={{ color: color.muted }}>{t("common.too_far")}</Text>
            ) : k.closed_for_now ? (
              <Text testID="closed-for-now" style={{ color: color.muted }}>{t("kitchen.closed_for_now")}</Text>
            ) : k.not_taking_orders ? (
              <Text testID="not-taking-orders" style={{ color: color.muted }}>{t("kitchen.not_taking_orders")}</Text>
            ) : (
              <Text testID="closed" style={{ color: color.muted }}>{k.opens_at ? opens(k.opens_at, zone) : t("common.closed")}</Text>
            )}
          </Text>
        </View>
      </Pressable>
      <View style={{ position: "absolute", right: 10, top: 10 }}>
        <FavouriteHeart kind="restaurant" id={k.id} name={k.name} />
      </View>
    </View>
  );
}
