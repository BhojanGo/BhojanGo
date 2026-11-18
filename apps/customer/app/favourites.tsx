// Favourites (GET /me/favourites): saved kitchens and dishes, as on the website's
// account favourites. Reached from home (the heart) and from Account (link to /favourites).
import { Button, color, num, radius, SafeAreaView, space, Txt, type, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { FavouriteHeart } from "../components/Heart";
import { RatingBadge } from "../components/KitchenCard";
import { Icon } from "../lib/icons";
import { useFavourites } from "../lib/favourites";
import { kitchenPhoto, KitchenCover, Thumb } from "../lib/plate";

export default function FavouritesScreen() {
  const { t, money } = useI18n();
  const { list, loading, error, load } = useFavourites();
  useEffect(() => {
    void load(true);
  }, [load]);

  const kitchens = list?.restaurants ?? [];
  const dishes = list?.items ?? [];
  const empty = list && !kitchens.length && !dishes.length;

  return (
    <SafeAreaView testID="favourites" style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={styles.top}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => (router.canGoBack() ? router.back() : router.replace("/home"))} style={styles.back}>
          <Icon name="back" />
        </Pressable>
        <Txt variant="h2" accessibilityRole="header">{t("favourites.title")}</Txt>
      </View>
      <ScrollView contentContainerStyle={{ padding: space[5], paddingTop: space[2], gap: space[3], paddingBottom: space[12] }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={() => void load(true)} />}>
        {!list && loading ? <ActivityIndicator color={color.peacock} /> : null}
        {!list && error ? (
          <View style={{ gap: space[3] }}>
            <Txt style={{ color: color.muted }}>{t("favourites.error")}</Txt>
            <Button title={t("common.retry")} variant="secondary" onPress={() => void load(true)} />
          </View>
        ) : null}
        {empty ? (
          <View style={{ gap: space[3] }}>
            <Txt style={{ color: color.muted }}>{t("favourites.empty")}</Txt>
            <Button title={t("favourites.find_food")} onPress={() => router.replace("/home")} />
          </View>
        ) : null}

        {kitchens.length ? <Txt variant="h2" accessibilityRole="header" style={{ marginTop: space[2] }}>{t("favourites.kitchens", { count: kitchens.length })}</Txt> : null}
        {kitchens.map((k) => (
          <View key={k.id} testID={`fav-kitchen-${k.slug}`}>
            <Pressable accessibilityRole="button" accessibilityLabel={k.name} onPress={() => router.push(`/restaurant/${k.id}`)} style={styles.kitchen}>
              <KitchenCover name={k.name} cover={kitchenPhoto(k)} height={120} width={800} />
              <View style={{ padding: space[4], gap: 4 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <Txt variant="h3" numberOfLines={1} style={{ flex: 1 }}>{k.name}</Txt>
                  <RatingBadge x={k} />
                </View>
                <Text numberOfLines={1} style={[type.small, { color: color.muted }]}>
                  {[...k.cuisine_types.slice(0, 2), t("common.minutes", { min: k.delivery_time_min, max: k.delivery_time_max })].join(" · ")}
                </Text>
              </View>
            </Pressable>
            <View style={{ position: "absolute", right: 12, top: 12 }}>
              <FavouriteHeart kind="restaurant" id={k.id} name={k.name} />
            </View>
          </View>
        ))}

        {dishes.length ? <Txt variant="h2" accessibilityRole="header" style={{ marginTop: space[4] }}>{t("favourites.dishes", { count: dishes.length })}</Txt> : null}
        {dishes.map((d) => (
          <View key={d.id} testID={`fav-dish-${d.id}`} style={styles.dish}>
            <Pressable accessibilityRole="button" accessibilityLabel={t("favourites.add_dish", { name: d.name, kitchen: d.restaurant.name })}
              disabled={!d.available}
              onPress={() => router.push({ pathname: "/item", params: { restaurantId: d.restaurant.id, itemId: d.id } })}
              style={{ flex: 1, flexDirection: "row", alignItems: "center", gap: 12, opacity: d.available ? 1 : 0.5 }}>
              {d.image_url ? <Thumb name={d.name} uri={d.image_url} size={56} /> : null}
              <View style={{ flex: 1 }}>
                <Text numberOfLines={1} style={type.label}>{d.name}</Text>
                <Text numberOfLines={1} style={[type.small, { color: color.muted }]}>{d.restaurant.name}</Text>
                <Text style={[type.label, num]}>{d.available ? money(d.price, d.currency) : t("favourites.sold_out")}</Text>
              </View>
            </Pressable>
            <FavouriteHeart kind="item" id={d.id} name={d.name} size={36} />
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "center", gap: 4, paddingLeft: space[2], paddingRight: space[5], paddingTop: space[3], paddingBottom: space[2] },
  back: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  kitchen: { backgroundColor: color.white, borderRadius: radius.card, overflow: "hidden" },
  dish: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: color.white, borderRadius: radius.card, padding: space[3] },
});
