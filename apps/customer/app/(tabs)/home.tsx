// CustomerHome.html (+ CustomerLoading.html while kitchens load), with the
// website's personal home (HomeFeed): the order on its way, Order again, the
// cuisine row, offers that say who pays, and the kitchens for the drop point
// from GET /discover.
import { Button, color, Sheet, radius, space, textFont, Txt, useBag, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { HeartIcon } from "../../components/Heart";
import { ActiveOrderBar, CuisineRow, OfferRow, OrderAgain } from "../../components/HomeSections";
import { KitchenCard } from "../../components/KitchenCard";
import { activeOrder, cuisineTiles, ofCuisine } from "../../lib/contract";
import { Icon } from "../../lib/icons";
import { useMyOrders } from "../../lib/orders";
import { useDiscover } from "../../lib/restaurants";
import { partOfDay, useWhere, type DropPoint } from "../../lib/where";
import { useTabBarSpace } from "../../lib/tabbar";

export default function Home() {
  const user = useSession((s) => s.user);
  const { t } = useI18n();
  const { point, market, status, locate, setPoint, goHere, saved } = useWhere();
  const [picking, setPicking] = useState<DropPoint[] | null>(null);
  const [cuisine, setCuisine] = useState<string | null>(null);
  const bagCount = useBag((s) => s.lines.reduce((n, l) => n + l.quantity, 0));

  useEffect(() => {
    if (status === "idle") void locate();
  }, [status, locate]);

  useEffect(() => {
    if (status === "ready" && market && !market.serviceable) router.replace("/out-of-area");
  }, [status, market]);

  const served = status === "ready" && !!market?.serviceable;
  const { data, kitchens, loading, error, reload } = useDiscover(served ? point : null);
  const orders = useMyOrders();
  const active = activeOrder(orders);
  const covers = useMemo(() => Object.fromEntries(kitchens.map((k) => [k.id, k.cover_url])), [kitchens]);
  const tiles = useMemo(() => cuisineTiles(data?.cuisines, kitchens), [data, kitchens]);
  const shown = ofCuisine(kitchens, cuisine);
  const currency = data?.currency ?? market?.currency;
  const unit = data?.distance_unit;

  const first = (user?.full_name ?? "").trim().split(/\s+/)[0];
  const pod = partOfDay(market?.timezone);
  const bottom = useTabBarSpace();
  const where = point ? (point.label || t("app.home.current_location")) : status === "failed" ? t("app.home.choose_address") : t("app.home.finding_you");

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <ScrollView testID="home" contentContainerStyle={{ paddingBottom: bottom }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={() => void reload()} />}>
        <View style={styles.top}>
          <Pressable testID="where" accessibilityRole="button" accessibilityLabel={t("header.change_address")} onPress={() => void saved().then(setPicking)} style={styles.where}>
            <Icon name="pin" size={20} stroke={color.peacock} />
            <Text numberOfLines={1} style={[textFont("700"), { fontSize: 15, color: color.kohl, flexShrink: 1 }]}>{where}</Text>
            <Icon name="chevron" size={16} />
          </Pressable>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable testID="open-favourites" accessibilityRole="button" accessibilityLabel={t("header.favourites")} onPress={() => router.push("/favourites")} style={styles.avatar}>
              <HeartIcon on={false} size={20} />
            </Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={t("common.your_account")} onPress={() => router.push("/account")} style={styles.avatar}>
              <Text style={[textFont("700"), { fontSize: 14 }]}>{initials(user?.full_name)}</Text>
            </Pressable>
          </View>
        </View>

        {active ? <ActiveOrderBar order={active} cover={covers[active.restaurant_id] ?? null} /> : null}

        <View style={{ paddingHorizontal: space[5], paddingTop: space[4] }}>
          <Txt variant="hero" accessibilityRole="header">
            {first ? t(`app.home.hello_name.${pod}`, { name: first }) : t(`app.home.hello.${pod}`)}
          </Txt>
          <Txt variant="hero" style={{ color: color.muted }}>{t(`app.home.ask.${pod}`)}</Txt>
        </View>

        <Pressable testID="home-search" accessibilityRole="search" accessibilityLabel={t("common.search_label")} onPress={() => router.push("/search")} style={styles.search}>
          <Icon name="search" size={20} stroke={color.muted} />
          <Text style={[textFont("400"), { fontSize: 16, color: color.muted }]}>{t("common.search_placeholder")}</Text>
        </Pressable>

        {orders ? <OrderAgain orders={orders} covers={covers} /> : null}
        <CuisineRow tiles={tiles} selected={cuisine} onSelect={setCuisine} />
        <OfferRow offers={data?.offers ?? []} currency={currency} covers={covers} />

        <View style={styles.sectionHead}>
          <Txt variant="h2" accessibilityRole="header">{cuisine ? t("app.home.cuisine_near", { cuisine }) : t("home.kitchens_near")}</Txt>
          {cuisine ? (
            <Text testID="clear-cuisine" accessibilityRole="button" onPress={() => setCuisine(null)} style={[textFont("700"), { fontSize: 14, color: color.peacock }]}>
              {t("app.home.all_kitchens")}
            </Text>
          ) : null}
        </View>

        {status === "failed" ? (
          <View style={{ paddingHorizontal: space[5], gap: space[3] }}>
            <Txt style={{ color: color.muted }}>{t("app.home.locate_failed")}</Txt>
            <Button title={t("app.home.choose_address")} variant="secondary" onPress={() => void saved().then(setPicking)} />
          </View>
        ) : status !== "ready" || loading ? (
          <Loading near={market?.zone_name ?? point?.label?.split("· ")[1] ?? (point?.label || null)} />
        ) : error && !kitchens.length ? (
          <View style={{ paddingHorizontal: space[5], gap: space[3] }}>
            <Txt style={{ color: color.muted }}>{t("common.error")}</Txt>
            <Button title={t("common.retry")} variant="secondary" onPress={() => void reload()} />
          </View>
        ) : (
          <View testID="kitchens" style={{ gap: space[4], paddingHorizontal: space[5] }}>
            {shown.length === 0 ? (
              <Txt style={{ color: color.muted }}>{kitchens.length ? t("home.no_filter_match") : t("home.no_kitchens")}</Txt>
            ) : null}
            {shown.map((k) => <KitchenCard key={k.id} k={k} currency={currency} unit={unit} />)}
          </View>
        )}
      </ScrollView>
      <Sheet visible={picking != null} onClose={() => setPicking(null)} title={t("checkout.deliver_to")}>
        {(picking ?? []).map((p) => (
          <Pressable key={p.addressId ?? p.label} accessibilityRole="button" onPress={() => { setPicking(null); void setPoint(p); }} style={styles.pick}>
            <Icon name="pin" size={20} stroke={color.peacock} />
            <Text style={[textFont("600"), { fontSize: 15, flex: 1 }]}>{p.label || t("app.home.current_location")}</Text>
          </Pressable>
        ))}
        <Button title={t("app.home.use_location")} variant="secondary" block onPress={() => { setPicking(null); void goHere(); }} />
      </Sheet>
      {bagCount > 0 ? (
        <Pressable testID="bag-pill" accessibilityRole="button" accessibilityLabel={t("common.bag_count", { count: bagCount })} onPress={() => router.push("/bag")} style={styles.bagPill}>
          <Icon name="bag" size={18} stroke={color.white} />
          <Text style={[textFont("800"), { color: color.white, fontSize: 15 }]}>{t("common.bag_count", { count: bagCount })}</Text>
        </Pressable>
      ) : null}
    </SafeAreaView>
  );
}

/** CustomerLoading.html: grey shapes where the cards will be, and what we're doing. */
function Loading({ near }: { near?: string | null }) {
  const { t } = useI18n();
  const label = near ? t("app.home.finding_kitchens", { place: near }) : t("app.home.finding_kitchens_here");
  return (
    <View accessibilityLabel={label} style={{ paddingHorizontal: space[5], gap: space[3] }}>
      {[0, 1].map((i) => (
        <View key={i} style={{ backgroundColor: color.white, borderRadius: radius.card, overflow: "hidden" }}>
          <View style={{ height: 172, backgroundColor: color.divider }} />
          <View style={{ padding: space[4], gap: 8 }}>
            <View style={{ height: 18, width: "60%", borderRadius: 6, backgroundColor: color.divider }} />
            <View style={{ height: 12, width: "80%", borderRadius: 6, backgroundColor: color.divider }} />
          </View>
        </View>
      ))}
      <View style={{ flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", marginTop: space[2] }}>
        <ActivityIndicator color={color.peacock} />
        <Txt variant="small" style={{ color: color.muted }}>{label}</Txt>
      </View>
    </View>
  );
}

function initials(name?: string | null): string {
  return (name ?? "").split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "·";
}

const styles = StyleSheet.create({
  top: { paddingHorizontal: space[5], paddingTop: space[4], flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  // Rounded, so the Android focus highlight (after a tap) follows the pill instead of a grey box.
  where: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, borderRadius: radius.pill, paddingHorizontal: 4, overflow: "hidden", flexShrink: 1 },
  avatar: {
    width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1, borderColor: color.line, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
  },
  search: {
    marginHorizontal: space[5], marginTop: space[6], height: 54, borderRadius: radius.pill, backgroundColor: color.white,
    flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 18,
    borderWidth: 1, borderColor: color.line, // a hairline, not an Android elevation box
  },
  sectionHead: {
    paddingHorizontal: space[5], paddingTop: space[8], paddingBottom: space[3], flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 12,
  },
  pick: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 48, borderBottomWidth: 1, borderBottomColor: color.divider },
  bagPill: {
    position: "absolute", right: space[5], bottom: 104, height: 48, paddingHorizontal: space[5], borderRadius: radius.pill,
    backgroundColor: color.peacock, flexDirection: "row", alignItems: "center", gap: 8,
  },
});
