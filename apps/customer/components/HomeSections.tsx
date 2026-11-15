// The personal home's parts (the website's HomeFeed / PersonalHome): the
// active-order bar, Order again, the cuisine row and the offers near you.
import { color, displayFont, errorMessage, radius, space, textFont, Txt, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import {
  initials, minutesUntil, offerPayer, offerSubtitle, offerTitle, orderAgain, riderFirstName, type CuisineTileData, type Offer, type Order,
} from "../lib/contract";
import { reorder } from "../lib/orders";
import { photo, Photo, Thumb } from "../lib/plate";

const OFFER_TINTS = [color.plate, color.peacockTint, "#F1E3E1"];

/** The order on its way: kitchen, status, minutes, the rider's first name and the door PIN. Taps to tracking. */
export function ActiveOrderBar({ order, cover }: { order: Order; cover: string | null }) {
  const { t } = useI18n();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(tick);
  }, []);
  const onWay = order.status === "picked_up";
  const minutes = minutesUntil(order.estimated_delivery_time, now);
  const rider = riderFirstName(order);
  const pin = order.pin ?? null;
  const sub = [
    minutes != null && minutes < 600 ? t("home.order_minutes", { count: minutes }) : null,
    rider ? t("home.order_rider", { rider }) : null,
    pin ? t("home.order_pin", { pin }) : null,
  ].filter(Boolean).join(" · ");
  const title = t(onWay ? "home.order_on_way" : "home.order_preparing", { kitchen: order.restaurant_name });
  return (
    <Pressable
      testID="active-order"
      accessibilityRole="button"
      accessibilityLabel={[title, sub, t("home.track_order")].filter(Boolean).join(". ")}
      onPress={() => router.push(`/order/${order.id}`)}
      style={{ marginHorizontal: space[5], marginTop: space[4], borderRadius: radius.card, backgroundColor: color.kohl, padding: 12, flexDirection: "row", alignItems: "center", gap: 12 }}
    >
      <Thumb name={order.restaurant_name} uri={cover} size={44} />
      <View style={{ flex: 1 }}>
        <Text numberOfLines={2} style={[textFont("800"), { fontSize: 14, color: "#F2F5F5" }]}>{title}</Text>
        {sub ? <Text testID="active-order-sub" numberOfLines={1} style={[textFont("400"), { fontSize: 12, color: "#A9B8BA", marginTop: 2 }]}>{sub}</Text> : null}
      </View>
      <Text style={[textFont("800"), { fontSize: 14, color: color.kesarBright }]}>{t("home.track")}</Text>
    </Pressable>
  );
}

/** The latest delivered order from up to three kitchens, each one tap from a new bag. */
export function OrderAgain({ orders, covers }: { orders: Order[]; covers: Record<string, string | null> }) {
  const { t, money } = useI18n();
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const past = orderAgain(orders);
  if (!past.length) return null;

  async function again(o: Order) {
    setBusy(o.id);
    setProblem(null);
    try {
      if (await reorder(o)) router.push("/bag");
      else setProblem(t("home.reorder_none"));
    } catch (e) {
      setProblem(errorMessage((e as { body?: unknown }).body, t("common.error")));
    } finally {
      setBusy(null);
    }
  }

  return (
    <View style={{ marginTop: space[8] }} testID="order-again">
      <View style={{ paddingHorizontal: space[5], flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
        <Txt variant="h2" accessibilityRole="header">{t("home.order_again")}</Txt>
        <Text accessibilityRole="link" onPress={() => router.push("/orders")} style={[textFont("700"), { fontSize: 14, color: color.peacock }]}>{t("home.all_orders")}</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingTop: space[3] }}>
        {past.map((o) => (
          <View key={o.id} style={{ width: 250, flexDirection: "row", alignItems: "center", gap: 10, padding: 10, borderRadius: radius.card, backgroundColor: color.white, borderWidth: 1, borderColor: color.line }}>
            <Thumb name={o.restaurant_name} uri={covers[o.restaurant_id] ?? null} />
            <View style={{ flex: 1 }}>
              <Text numberOfLines={1} style={[textFont("800"), { fontSize: 14 }]}>{o.restaurant_name}</Text>
              <Text style={[textFont("400"), { fontSize: 12, color: color.muted }]}>{money(o.total, o.currency)}</Text>
              <Pressable
                testID={`order-again-${o.id}`}
                accessibilityRole="button"
                accessibilityLabel={t("home.order_again_from", { kitchen: o.restaurant_name })}
                disabled={busy !== null}
                onPress={() => void again(o)}
                hitSlop={8}
              >
                <Text style={[textFont("800"), { fontSize: 13, color: color.peacock, opacity: busy && busy !== o.id ? 0.5 : 1 }]}>
                  {busy === o.id ? t("common.loading") : t("home.order_again_button")}
                </Text>
              </Pressable>
            </View>
          </View>
        ))}
      </ScrollView>
      {problem ? <Text accessibilityRole="alert" style={[textFont("600"), { color: color.chili, fontSize: 13, paddingHorizontal: space[5], marginTop: 6 }]}>{problem}</Text> : null}
    </View>
  );
}

/** Cuisines with 2+ kitchens, each with its own photo; a tap filters the kitchens (again: all of them). */
export function CuisineRow({ tiles, selected, onSelect }: { tiles: CuisineTileData[]; selected: string | null; onSelect: (name: string | null) => void }) {
  const { t } = useI18n();
  if (!tiles.length) return null;
  return (
    <View style={{ marginTop: space[8] }}>
      <Txt variant="h2" accessibilityRole="header" style={{ paddingHorizontal: space[5] }}>{t("home.craving")}</Txt>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space[5], gap: 14, paddingTop: space[3] }}>
        {tiles.map((c) => {
          const on = selected === c.name;
          return (
            <Pressable key={c.name} testID={`cuisine-${c.name}`} accessibilityRole="button" accessibilityState={{ selected: on }}
              accessibilityLabel={c.name} onPress={() => onSelect(on ? null : c.name)} style={{ width: 76, alignItems: "center" }}>
              <View style={{ width: 72, height: 72, borderRadius: 36, borderWidth: 3, borderColor: on ? color.peacock : color.white, overflow: "hidden", backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" }}>
                <Photo uri={photo(c.photo, 400)} style={{ width: 66, height: 66 }}
                  fallback={<Text style={[displayFont("600"), { fontSize: 22, color: color.peacockDeep }]}>{initials(c.name)}</Text>} />
              </View>
              <Text numberOfLines={1} style={[textFont(on ? "800" : "700"), { fontSize: 13, marginTop: 6, color: on ? color.peacockDeep : color.kohl }]}>{c.name}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

/** Offers near you; every one says who pays for it. */
export function OfferRow({ offers, currency, covers }: { offers: Offer[]; currency?: string | null; covers: Record<string, string | null> }) {
  const { t, money } = useI18n();
  if (!offers.length) return null;
  return (
    <View style={{ marginTop: space[8] }} testID="offers">
      <View style={{ paddingHorizontal: space[5] }}>
        <Txt variant="h2" accessibilityRole="header">{t("offers.near_you")}</Txt>
        <Txt variant="small" style={{ color: color.muted, marginTop: 2 }}>{t("offers.who_pays")}</Txt>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingTop: space[3] }}>
        {offers.slice(0, 6).map((o, i) => {
          const kitchenId = o.restaurant?.id as string | undefined;
          const cover = kitchenId ? (covers[kitchenId] ?? null) : null;
          return (
            <Pressable key={o.id} testID={`offer-${o.id}`} accessibilityRole="button" disabled={!kitchenId}
              onPress={() => kitchenId && router.push(`/restaurant/${kitchenId}`)}
              style={{ width: 280, height: 132, flexDirection: "row", borderRadius: radius.card, overflow: "hidden", backgroundColor: OFFER_TINTS[i % 3] }}>
              <View style={{ flex: 1, padding: space[4], justifyContent: "center" }}>
                <Text numberOfLines={2} style={[displayFont("600"), { fontSize: 19, color: color.kohl }]}>{offerTitle(o, t, money, currency)}</Text>
                <Text numberOfLines={2} style={[textFont("400"), { fontSize: 13, color: "#24383B", marginTop: 4 }]}>{offerSubtitle(o, t, money, currency)}</Text>
                <Text style={[textFont("800"), { fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: color.muted, marginTop: 8 }]}>{offerPayer(o, t)}</Text>
              </View>
              {cover ? <Photo uri={photo(cover, 400)} style={{ width: 96, height: 132 }} /> : null}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
