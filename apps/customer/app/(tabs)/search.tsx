// Search the kitchens that deliver to the drop point. With nothing typed: the cuisine row and every kitchen
// (the same /discover answer as home). R36: once something is typed the cuisine row goes, and
// /discover/search answers with "Restaurants" (name, cuisine, tag) and "Dishes" (dish names: "curry" finds
// every kitchen's curries), each dish with its kitchen, price and an add button.
import { api, color, Input, LoadError, radius, SafeAreaView, space, Txt, type, unwrap, useBag, useI18n, type CoreSchemas } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, SectionList, Text, View } from "react-native";

import { CuisineRow } from "../../components/HomeSections";
import { KitchenCard } from "../../components/KitchenCard";
import { cuisineTiles, ofCuisine, type KitchenCard as Kitchen } from "../../lib/contract";
import { photo, Photo } from "../../lib/plate";
import { useDiscover } from "../../lib/restaurants";
import { TabEnd, useTabBarSpace } from "../../lib/tabbar";
import { useWhere } from "../../lib/where";

type Hits = CoreSchemas["SearchOut"];
type Dish = CoreSchemas["DishHit"];
type Row = { kind: "kitchen"; k: Kitchen } | { kind: "dish"; d: Dish };

/** R36: the server's search for 2+ characters (debounced), for the same point as the list. */
function useSearch(lat: number | null, lng: number | null, q: string) {
  const needle = q.trim();
  const key = lat != null && lng != null && needle.length >= 2 ? `${lat},${lng},${needle}` : null;
  const [got, setGot] = useState<{ key: string; hits: Hits | null } | null>(null);
  useEffect(() => {
    if (!key || lat == null || lng == null) return;
    let live = true;
    const timer = setTimeout(() => {
      api.core.GET("/api/v1/discover/search", { params: { query: { q: needle, lat, lng } } })
        .then((r) => { if (live) setGot({ key, hits: unwrap(r) }); })
        .catch(() => { if (live) setGot({ key, hits: null }); });
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [key, lat, lng, needle]);
  const hits = key && got?.key === key ? got.hits : null;
  return { hits, busy: !!key && got?.key !== key };
}

export default function Search() {
  const { t } = useI18n();
  const bottom = useTabBarSpace();
  const point = useWhere((s) => s.point);
  const market = useWhere((s) => s.market);
  const where = market?.serviceable ? point : null;
  const { data, kitchens, loading, error, failure, reload } = useDiscover(where);
  const [q, setQ] = useState("");
  const [cuisine, setCuisine] = useState<string | null>(null);
  const tiles = useMemo(() => cuisineTiles(data?.cuisines, kitchens), [data, kitchens]);
  const needle = q.trim().toLocaleLowerCase();
  const typed = needle.length > 0;
  const { hits, busy } = useSearch(where?.lat ?? null, where?.lng ?? null, q);
  // One letter: the list filtered here; two or more: the server's restaurants and dishes.
  const local = ofCuisine(kitchens, typed ? null : cuisine).filter(
    (k) => !needle || [k.name, k.area ?? "", ...k.cuisine_types, ...k.tags].join(" ").toLocaleLowerCase().includes(needle),
  );
  const restaurants: Kitchen[] = hits ? hits.restaurants ?? [] : local;
  const dishes: Dish[] = hits ? hits.dishes ?? [] : [];
  const sections: { key: string; title: string | null; data: Row[] }[] = [
    ...(restaurants.length ? [{ key: "restaurants", title: typed ? t("app.search.restaurants") : null, data: restaurants.map((k): Row => ({ kind: "kitchen", k })) }] : []),
    ...(dishes.length ? [{ key: "dishes", title: t("app.search.dishes"), data: dishes.map((d): Row => ({ kind: "dish", d })) }] : []),
  ];
  const count = restaurants.length + dishes.length;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <View style={{ padding: space[5], gap: space[4] }}>
        <Txt variant="h2" accessibilityRole="header">{t("tabs.search")}</Txt>
        <Input testID="search-input" shape="pill" placeholder={t("common.search_placeholder")} value={q} onChangeText={setQ} autoFocus
          accessibilityLabel={t("common.search_label")} />
      </View>
      <SectionList
        sections={sections}
        keyExtractor={(r) => (r.kind === "kitchen" ? `k-${r.k.id}` : `d-${r.d.id}`)}
        keyboardShouldPersistTaps="handled"
        stickySectionHeadersEnabled={false}
        // R36: the cuisine circles only before anything is typed
        ListHeaderComponent={typed ? undefined : (
          <View testID="search-cuisines" style={{ marginTop: -space[8], marginBottom: space[4], marginHorizontal: -space[5] }}>
            <CuisineRow tiles={tiles} selected={cuisine} onSelect={setCuisine} />
          </View>
        )}
        contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingBottom: bottom }}
        renderSectionHeader={({ section }) => section.title ? (
          <Txt testID={`search-${section.key}`} variant="h3" accessibilityRole="header" style={{ paddingTop: space[2] }}>{section.title}</Txt>
        ) : null}
        ListEmptyComponent={
          <View testID="search-last">
            {/* R9: the kitchens didn't load (offline, our servers): say so and Retry, not "no restaurants". */}
            {error && !kitchens.length ? <LoadError error={failure} onRetry={reload} />
              : loading || busy ? <ActivityIndicator color={color.peacock} />
              : <Txt style={{ color: color.muted }}>{needle ? t("app.search.no_match", { q: q.trim() }) : kitchens.length ? t("home.no_filter_match") : t("home.no_kitchens")}</Txt>}
          </View>
        }
        ListFooterComponent={<TabEnd tab="search" />}
        renderItem={({ item, index, section }) => {
          const last = section.key === sections[sections.length - 1]?.key && index === section.data.length - 1 && count > 0;
          return (
            <View testID={last ? "search-last" : undefined}>
              {item.kind === "kitchen"
                ? <KitchenCard k={item.k} currency={data?.currency} unit={data?.distance_unit} compact />
                : <DishResult d={item.d} currency={data?.currency ?? null} />}
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

/** R36: a dish found by name: its name, its kitchen, its price, and add (or open it when there's a choice to make). */
function DishResult({ d, currency }: { d: Dish; currency: string | null }) {
  const { t, money } = useI18n();
  const bag = useBag();
  const orderable = d.open_now && (d.deliverable || d.pickup_only);
  const qty = bag.restaurantId === d.restaurant_id ? bag.lines.filter((l) => l.menuItemId === d.id).reduce((n, l) => n + l.quantity, 0) : 0;
  const open = () => router.push({ pathname: "/item", params: { restaurantId: d.restaurant_id, itemId: d.id } });
  const add = () => {
    if (!orderable) return;
    if (d.has_options || (bag.restaurantId && bag.restaurantId !== d.restaurant_id)) return open();
    if (d.pickup_only) bag.setFulfillment("pickup");
    bag.add({ id: d.restaurant_id, name: d.restaurant_name }, { menuItemId: d.id, name: d.name, unitPrice: Number(d.price), quantity: 1, picks: [], summary: "" });
  };
  const pic = photo(d.photo_url, 400);
  return (
    <Pressable testID={`dish-hit-${d.id}`} accessibilityRole="button" accessibilityLabel={`${d.name}, ${d.restaurant_name}`}
      onPress={() => router.push(`/restaurant/${d.restaurant_id}`)}
      style={{ flexDirection: "row", alignItems: "center", gap: space[3], padding: space[3], borderRadius: radius.card, backgroundColor: color.white }}>
      {pic ? <Photo uri={pic} label={d.name} style={{ width: 64, height: 64, borderRadius: radius.card }} /> : null}
      <View style={{ flex: 1, gap: 2 }}>
        <Text numberOfLines={2} style={[type.label, { color: color.kohl }]}>{d.name}</Text>
        <Text testID="dish-hit-restaurant" numberOfLines={1} style={[type.small, { color: color.muted }]}>{d.restaurant_name}</Text>
        <Text style={[type.label, { color: color.kohl }]}>{money(d.price, currency)}</Text>
        {!orderable ? <Text style={[type.small, { color: color.chili }]}>{d.open_now ? t("common.too_far") : t("common.closed")}</Text> : null}
      </View>
      <Pressable testID={`dish-hit-add-${d.id}`} accessibilityRole="button" accessibilityLabel={t("kitchen.add_dish", { name: d.name })}
        accessibilityState={{ disabled: !orderable }} disabled={!orderable} onPress={add} hitSlop={6}
        style={{ minWidth: 44, height: 44, paddingHorizontal: qty ? 12 : 0, borderRadius: radius.pill, borderWidth: 1.5,
          borderColor: orderable ? color.lineStrong : color.line, alignItems: "center", justifyContent: "center", opacity: orderable ? 1 : 0.5 }}>
        <Text style={[type.h3, { color: orderable ? color.peacock : color.muted }]}>{qty ? `${qty} +` : "+"}</Text>
      </Pressable>
    </Pressable>
  );
}
