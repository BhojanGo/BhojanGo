// A kitchen on home and search, as the website's KitchenCard: its own cover or
// initials tile, the offer with who pays, the heart, "New" or "★4.6 (23)",
// cuisines and distance, minutes and the delivery fee, closed until when.
import { color, type I18n, radius, space, textFont, Txt, type, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { offerBadge, ratingOf, type KitchenCard as Kitchen } from "../lib/contract";
import { kitchenPhoto, KitchenCover } from "../lib/plate";
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

/** "06:30" of an ISO time with its offset: the kitchen's own clock, in the country's format. */
export function wallTime(iso: string, time: I18n["time"]): string {
  const m = /T(\d{2}):(\d{2})/.exec(iso);
  if (!m) return iso;
  return time(new Date(Date.UTC(2000, 0, 1, Number(m[1]), Number(m[2]))), { hour: "numeric", minute: "2-digit", timeZone: "UTC" });
}

/** A distance as /discover sends it (already in the country's unit). */
export function useCardDistance() {
  const { t, number } = useI18n();
  return (value: number | null | undefined, unit: string | null | undefined) =>
    value != null && unit ? t(`app.units.${unit}`, { value: number(value, 1) }) : null;
}

export function KitchenCard({ k, currency, unit, compact = false }: { k: Kitchen; currency?: string | null; unit?: string | null; compact?: boolean }) {
  const { t, money, time } = useI18n();
  const dist = useCardDistance();
  const fee = k.delivery_fee != null ? Number(k.delivery_fee) : null;
  const meta = [...k.cuisine_types.slice(0, 2), dist(k.distance, unit) ?? k.area].filter(Boolean).join(" · ");
  const height = compact ? 120 : 172;
  return (
    <View testID={`kitchen-card-${k.slug}`}>
      <Pressable accessibilityRole="button" accessibilityLabel={k.name} onPress={() => router.push(`/restaurant/${k.id}`)}
        style={{ backgroundColor: color.white, borderRadius: radius.card, overflow: "hidden" }}>
        <View>
          <KitchenCover name={k.name} cover={kitchenPhoto(k)} height={height} />
          {k.offer ? (
            <View testID="offer-badge" style={{ position: "absolute", left: 12, top: 12, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: color.kohl }}>
              <Text style={[type.caption, { color: color.white }]}>{offerBadge(k.offer, t, money, currency)}</Text>
            </View>
          ) : null}
          {!k.open_now ? <View style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 0, backgroundColor: "rgba(255,255,255,0.4)" }} /> : null}
        </View>
        <View style={{ padding: space[4], gap: 4 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <Txt variant="h3" numberOfLines={1} style={{ flex: 1 }}>{k.name}</Txt>
            <RatingBadge x={k} />
          </View>
          {meta ? <Text numberOfLines={1} style={[type.small, { color: color.muted }]}>{meta}</Text> : null}
          <Text style={[type.small, { color: color.kohl }]}>
            <Text style={textFont("700")}>{t("common.minutes", { min: k.eta_min, max: k.eta_max })}</Text>
            {fee !== null ? " · " : ""}
            {fee !== null ? (
              k.free_delivery || fee === 0 ? (
                <Text style={[textFont("700"), { color: color.peacock }]}>{t("common.free_delivery")}</Text>
              ) : (
                t("common.delivery_fee", { fee: money(fee, currency) })
              )
            ) : null}
            {!k.open_now && k.closed_for_now ? <Text testID="closed-for-now" style={{ color: color.muted }}> · {t("kitchen.closed_for_now")}</Text> : null}
            {!k.open_now && k.not_taking_orders ? <Text testID="not-taking-orders" style={{ color: color.muted }}> · {t("kitchen.not_taking_orders")}</Text> : null}
            {!k.open_now && !k.closed_for_now && k.opens_at ? <Text style={{ color: color.muted }}> · {t("common.closed_opens", { time: wallTime(k.opens_at, time) })}</Text> : null}
          </Text>
        </View>
      </Pressable>
      <View style={{ position: "absolute", right: 12, top: 12 }}>
        <FavouriteHeart kind="restaurant" id={k.id} name={k.name} />
      </View>
    </View>
  );
}
