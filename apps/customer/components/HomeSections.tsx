// The personal home's parts (the website's HomeFeed / PersonalHome): the
// active-order bar, Order again, the cuisine row and the offers near you.
import { color, cuisineName, errorMessage, num, radius, space, Txt, type, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import {
  minutesUntil, offerPayer, offerSubtitle, offerTitle, orderAgain, riderFirstName, type CuisineTileData, type Offer, type Order,
} from "../lib/contract";
import { okToReplaceBag } from "../lib/newBag";
import { reorder } from "../lib/orders";
import { BrandTile, photo, Photo, Thumb } from "../lib/plate";

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
  const pin = onWay ? order.pin ?? null : null; // the door PIN once picked up (R27)
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
        <Text numberOfLines={2} style={[type.label, { color: "#F2F5F5" }]}>{title}</Text>
        {sub ? <Text testID="active-order-sub" numberOfLines={1} style={[type.small, { color: "#A9B8BA", marginTop: 2 }]}>{sub}</Text> : null}
      </View>
      <Text style={[type.label, { color: color.kesarBright }]}>{t("home.track")}</Text>
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
    if (!(await okToReplaceBag(o.restaurant_id, t))) return; // R28: asks before clearing another kitchen's bag
    setBusy(o.id);
    setProblem(null);
    try {
      const { added, notes } = await reorder(o);
      const said = notes.map((n) => t(n.key, n.values));
      if (!added) setProblem([...said, t("home.reorder_none")].join(" "));
      else if (said.length) setProblem([...said, t("account.receipt.reorder.rest_added")].join(" "));
      else router.push("/bag");
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
        <Text accessibilityRole="link" onPress={() => router.push("/orders")} style={[type.label, { color: color.peacock }]}>{t("home.all_orders")}</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingTop: space[3] }}>
        {past.map((o) => (
          <View key={o.id} style={{ width: 250, flexDirection: "row", alignItems: "center", gap: 10, padding: 10, borderRadius: radius.card, backgroundColor: color.white, borderWidth: 1, borderColor: color.line }}>
            <Thumb name={o.restaurant_name} uri={covers[o.restaurant_id] ?? null} />
            <View style={{ flex: 1 }}>
              <Text numberOfLines={1} style={type.label}>{o.restaurant_name}</Text>
              <Text style={[type.small, num, { color: color.muted }]}>{money(o.total, o.currency)}</Text>
              <Pressable
                testID={`order-again-${o.id}`}
                accessibilityRole="button"
                accessibilityLabel={t("home.order_again_from", { kitchen: o.restaurant_name })}
                disabled={busy !== null}
                onPress={() => void again(o)}
                hitSlop={8}
              >
                <Text style={[type.label, { color: color.peacock, opacity: busy && busy !== o.id ? 0.5 : 1 }]}>
                  {busy === o.id ? t("common.loading") : t("home.order_again_button")}
                </Text>
              </Pressable>
            </View>
          </View>
        ))}
      </ScrollView>
      {problem ? <Text accessibilityRole="alert" style={[type.small, { color: color.chili, paddingHorizontal: space[5], marginTop: 6 }]}>{problem}</Text> : null}
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
              accessibilityLabel={cuisineName(t, c.name)} onPress={() => onSelect(on ? null : c.name)} style={{ width: 76, alignItems: "center" }}>
              <View style={{ width: 72, height: 72, borderRadius: 36, borderWidth: 3, borderColor: on ? color.peacock : color.white, overflow: "hidden", backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" }}>
                <Photo uri={photo(c.photo, 400)} style={{ width: 66, height: 66 }}
                  fallback={<BrandTile width={66} height={66} rounded={33} />} />
              </View>
              <Text numberOfLines={1} style={[type.label, { marginTop: 6, color: on ? color.peacockDeep : color.kohl }]}>{cuisineName(t, c.name)}</Text>
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
                <Text numberOfLines={2} style={[type.h3, { color: color.kohl }]}>{offerTitle(o, t, money, currency)}</Text>
                <Text numberOfLines={2} style={[type.small, { color: "#24383B", marginTop: 4 }]}>{offerSubtitle(o, t, money, currency)}</Text>
                <Text style={[type.caption, { color: color.muted, marginTop: 8 }]}>{offerPayer(o, t)}</Text>
              </View>
              {cover ? <Photo uri={photo(cover, 400)} style={{ width: 96, height: 132 }} /> : null}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
