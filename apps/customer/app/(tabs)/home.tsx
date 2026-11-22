// CustomerHome.html (+ CustomerLoading.html while kitchens load), with the
// website's personal home (HomeFeed): the order on its way, Order again, the
// cuisine row, offers that say who pays, and the kitchens for the drop point
// from GET /discover. The header is minimal (round 6, like the website's): the
// language pill, favourites and the account; where the food goes sits on the
// page, one line above the greeting, with one action (round 20, as on the website):
// a live city "<City>, <ST> · Change" (ST: the state's short code from Markets,
// "<City>, ID"); anything else only "Set your delivery location" (it opens Change
// city). Never a city we guessed, never a city we don't serve.
import {
  Button, color, cuisineName, LanguagePill, LoadError, radius, SafeAreaView, space, Txt, type, useBag, useCountry, useI18n, useSession,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { HeartIcon } from "../../components/Heart";
import { ActiveOrderBar, CuisineRow, OfferRow, OrderAgain } from "../../components/HomeSections";
import { KitchenCard } from "../../components/KitchenCard";
import { kitchenPhoto } from "../../lib/plate";
import { activeOrder, cuisineTiles, greetingZone, ofCuisine } from "../../lib/contract";
import { Icon } from "../../lib/icons";
import { useMyOrders } from "../../lib/orders";
import { useDiscover } from "../../lib/restaurants";
import { partOfDay, useWhere } from "../../lib/where";
import { TabEnd, useTabBarOffsets, useTabBarSpace } from "../../lib/tabbar";

const BAG_PILL = 48;

export default function Home() {
  const user = useSession((s) => s.user);
  const { t } = useI18n();
  const { country } = useCountry();
  const { point, market, status, locate, apiFailure } = useWhere();
  const [cuisine, setCuisine] = useState<string | null>(null);
  const bagCount = useBag((s) => s.lines.reduce((n, l) => n + l.quantity, 0));

  useEffect(() => {
    if (status === "idle") void locate();
  }, [status, locate]);

  useEffect(() => {
    if (status === "ready" && market && !market.serviceable) router.replace("/out-of-area");
  }, [status, market]);

  const served = status === "ready" && !!market?.serviceable;
  const { data, kitchens, loading, error, failure, reload } = useDiscover(served ? point : null);
  const orders = useMyOrders();
  const active = activeOrder(orders);
  const covers = useMemo(() => Object.fromEntries(kitchens.map((k) => [k.id, kitchenPhoto(k)])), [kitchens]);
  const tiles = useMemo(() => cuisineTiles(data?.cuisines, kitchens), [data, kitchens]);
  const shown = ofCuisine(kitchens, cuisine);
  const currency = data?.currency ?? market?.currency;
  const unit = data?.distance_unit;

  const first = (user?.full_name ?? "").trim().split(/\s+/)[0];
  const pod = partOfDay(greetingZone(market?.timezone, country?.timezone)); // the delivery address's clock
  // The bag pill floats just above the tab bar: when it shows, the scroll leaves room for it too.
  const bottom = useTabBarSpace(bagCount > 0 ? [BAG_PILL] : []);
  const { above } = useTabBarOffsets();
  // A live city (GET /markets/locate: the drop point is inside an open zone): "<City>, <ST>".
  const st = market?.region_short_code || market?.country_code;
  const city = market?.serviceable && market.city_name && st ? t("location.place", { city: market.city_name, country: st }) : null;
  const locating = status !== "ready" && status !== "failed";
  const changeCity = () => router.push("/where");

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <ScrollView testID="home" contentContainerStyle={{ paddingBottom: bottom }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={() => void reload()} />}>
        <View style={styles.top}>
          <LanguagePill />
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable testID="open-favourites" accessibilityRole="button" accessibilityLabel={t("header.favourites")} onPress={() => router.push("/favourites")} style={styles.avatar}>
              <HeartIcon on={false} size={20} />
            </Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={t("common.your_account")} onPress={() => router.push("/account")} style={styles.avatar}>
              <Text style={type.label} maxFontSizeMultiplier={1.3}>{initials(user?.full_name)}</Text>
            </Pressable>
          </View>
        </View>

        <View testID="location-line" style={styles.where}>
          <Icon name="pin" size={18} stroke={color.peacock} />
          {city ? (
            <>
              <Text testID="location-city" numberOfLines={1} style={[type.label, { color: color.kohl, flexShrink: 1 }]}>{city}</Text>
              <Text style={[type.label, { color: color.muted }]}>·</Text>
              <Pressable testID="change-city" accessibilityRole="link" accessibilityLabel={t("location.change_city")} onPress={changeCity} hitSlop={8} style={styles.change}>
                <Text style={[type.label, { color: color.peacock }]}>{t("location.change")}</Text>
              </Pressable>
            </>
          ) : locating ? (
            <Text testID="location-finding" numberOfLines={1} style={[type.label, { color: color.muted, flexShrink: 1 }]}>{t("app.home.finding_you")}</Text>
          ) : (
            <Pressable testID="set-location" accessibilityRole="button" onPress={changeCity} hitSlop={8} style={[styles.change, { flexShrink: 1 }]}>
              <Text numberOfLines={1} style={[type.label, { color: color.peacock }]}>{t("location.set")}</Text>
            </Pressable>
          )}
        </View>

        {active ? <ActiveOrderBar order={active} cover={covers[active.restaurant_id] ?? null} /> : null}

        <View style={{ paddingHorizontal: space[5], paddingTop: space[4] }}>
          <Txt variant="h1" accessibilityRole="header">
            {first ? t(`app.home.hello_name.${pod}`, { name: first }) : t(`app.home.hello.${pod}`)}
          </Txt>
          <Txt variant="h1" style={{ color: color.muted }}>{t(`app.home.ask.${pod}`)}</Txt>
        </View>

        <Pressable testID="home-search" accessibilityRole="search" accessibilityLabel={t("common.search_label")} onPress={() => router.push("/search")} style={styles.search}>
          <Icon name="search" size={20} stroke={color.muted} />
          <Text numberOfLines={1} style={[type.body, { color: color.muted, flex: 1 }]}>{t("common.search_placeholder")}</Text>
        </Pressable>

        {orders ? <OrderAgain orders={orders} covers={covers} /> : null}
        <CuisineRow tiles={tiles} selected={cuisine} onSelect={setCuisine} />
        <OfferRow offers={data?.offers ?? []} currency={currency} covers={covers} />

        <View style={styles.sectionHead}>
          <Txt variant="h2" accessibilityRole="header">{cuisine ? t("app.home.cuisine_near", { cuisine: cuisineName(t, cuisine) }) : t("home.kitchens_near")}</Txt>
          {cuisine ? (
            <Text testID="clear-cuisine" accessibilityRole="button" onPress={() => setCuisine(null)} style={[type.label, { color: color.peacock }]}>
              {t("app.home.all_kitchens")}
            </Text>
          ) : null}
        </View>

        {status === "failed" && apiFailure ? (
          <View testID="home-last" style={{ paddingHorizontal: space[5] }}>
            <LoadError error={apiFailure} onRetry={locate} />
          </View>
        ) : status === "failed" ? (
          <View testID="home-last" style={{ paddingHorizontal: space[5], gap: space[3] }}>
            <Txt style={{ color: color.muted }}>{t("app.home.locate_failed")}</Txt>
            <Button title={t("app.home.choose_address")} variant="secondary" onPress={changeCity} />
          </View>
        ) : status !== "ready" || loading ? (
          <Loading near={market?.zone_name ?? point?.label?.split("· ")[1] ?? (point?.label || null)} />
        ) : error && !kitchens.length ? (
          <View testID="home-last" style={{ paddingHorizontal: space[5] }}>
            <LoadError error={failure} onRetry={reload} />
          </View>
        ) : (
          <View testID="kitchens" style={{ gap: space[4], paddingHorizontal: space[5] }}>
            {shown.length === 0 ? (
              <View testID="home-last">
                <Txt style={{ color: color.muted }}>{kitchens.length ? t("home.no_filter_match") : t("home.no_kitchens")}</Txt>
              </View>
            ) : null}
            {shown.map((k, i) => (i === shown.length - 1
              ? <View key={k.id} testID="home-last"><KitchenCard k={k} currency={currency} unit={unit} /></View>
              : <KitchenCard key={k.id} k={k} currency={currency} unit={unit} />))}
          </View>
        )}
        <TabEnd tab="home" />
      </ScrollView>
      {bagCount > 0 ? (
        <Pressable testID="bag-pill" accessibilityRole="button" accessibilityLabel={t("common.bag_count", { count: bagCount })} onPress={() => router.push("/bag")} style={[styles.bagPill, { bottom: above }]}>
          <Icon name="bag" size={18} stroke={color.white} />
          <Text style={[type.label, { color: color.white }]}>{t("common.bag_count", { count: bagCount })}</Text>
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
    <View testID="home-last" accessibilityLabel={label} style={{ paddingHorizontal: space[5], gap: space[3] }}>
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
  where: { flexDirection: "row", alignItems: "center", gap: 6, minHeight: 44, paddingHorizontal: space[5], paddingTop: space[3] },
  // Rounded, so the Android focus highlight (after a tap) follows the link instead of a grey box.
  change: { minHeight: 44, justifyContent: "center", borderRadius: radius.pill, paddingHorizontal: 2 },
  avatar: {
    // min, not fixed: the largest phone font setting (200 %) clipped the initial (R9).
    minWidth: 44, minHeight: 44, paddingHorizontal: 4, borderRadius: radius.pill, borderWidth: 1, borderColor: color.line, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
  },
  search: {
    marginHorizontal: space[5], marginTop: space[6], minHeight: 54, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: color.white,
    flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 18,
    borderWidth: 1, borderColor: color.line, // a hairline, not an Android elevation box
  },
  sectionHead: {
    paddingHorizontal: space[5], paddingTop: space[8], paddingBottom: space[3], flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 12,
  },
  bagPill: {
    position: "absolute", right: space[5], height: BAG_PILL, paddingHorizontal: space[5], borderRadius: radius.pill,
    backgroundColor: color.peacock, flexDirection: "row", alignItems: "center", gap: 8,
  },
});
