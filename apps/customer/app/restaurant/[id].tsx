// The restaurant: its menu by category; tap a dish to customise it.
import { color, money, radius, space, textFont, Txt, useBag } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, SectionList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../../lib/icons";
import { PlateHeader } from "../../lib/plate";
import { useMenu } from "../../lib/restaurants";

export default function RestaurantScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { menu, error } = useMenu(id);
  const bag = useBag();
  const inBag = bag.restaurantId === id ? bag.lines.reduce((n, l) => n + l.quantity, 0) : 0;

  if (!menu) {
    return (
      <SafeAreaView style={styles.center}>
        {error ? <Txt>{error}</Txt> : <ActivityIndicator color={color.peacock} />}
      </SafeAreaView>
    );
  }
  const r = menu.restaurant;
  return (
    <View style={{ flex: 1, backgroundColor: color.porcelain }}>
      <SectionList
        sections={menu.categories.map((c) => ({ title: c.name, data: c.items }))}
        keyExtractor={(i) => i.id}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={{ paddingBottom: 120 }}
        ListHeaderComponent={
          <View>
            <PlateHeader label={r.name} height={220} size={170} />
            <View style={styles.head}>
              <Txt variant="h1" accessibilityRole="header" style={{ fontSize: 30, lineHeight: 33 }}>{r.name}</Txt>
              <Text style={[textFont("400"), { color: color.muted, fontSize: 14 }]}>
                {r.cuisine_types.join(" · ")} · {r.delivery_time_min}–{r.delivery_time_max} min
              </Text>
              {r.description ? <Txt variant="small" style={{ color: color.muted }}>{r.description}</Txt> : null}
            </View>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <Txt variant="h2" style={{ paddingHorizontal: space[5], paddingTop: space[6], paddingBottom: space[2] }}>{section.title}</Txt>
        )}
        renderItem={({ item }) => {
          const off = !item.is_available || item.sold_out_today;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={item.name}
              accessibilityState={{ disabled: off }}
              disabled={off}
              onPress={() => router.push({ pathname: "/item", params: { restaurantId: r.id, itemId: item.id } })}
              style={[styles.item, off && { opacity: 0.5 }]}
            >
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={[textFont("800"), { fontSize: 16, color: color.kohl }]}>{item.name}</Text>
                {item.description ? (
                  <Text numberOfLines={2} style={[textFont("400"), { fontSize: 14, color: color.muted }]}>{item.description}</Text>
                ) : null}
                <Text style={[textFont("700"), { fontSize: 15, color: color.kohl }]}>
                  {off ? "Sold out today" : money(item.price, r.currency, { decimals: 0 })}
                </Text>
              </View>
              <View style={styles.add}><Text style={[textFont("800"), { color: color.peacock, fontSize: 22 }]}>+</Text></View>
            </Pressable>
          );
        }}
      />
      <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={styles.back}>
        <Icon name="back" />
      </Pressable>
      {inBag > 0 ? (
        <Pressable accessibilityRole="button" onPress={() => router.push("/bag")} style={styles.bagBar}>
          <Text style={[textFont("800"), { color: color.white, fontSize: 16 }]}>View bag · {inBag} {inBag === 1 ? "item" : "items"}</Text>
          <Icon name="arrow" stroke={color.white} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  head: {
    marginTop: -24, backgroundColor: color.white, borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet,
    padding: space[5], gap: 6,
  },
  item: {
    marginHorizontal: space[5], marginBottom: space[3], padding: space[4], borderRadius: radius.card, backgroundColor: color.white,
    flexDirection: "row", gap: space[3], alignItems: "center",
  },
  add: { width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  back: {
    position: "absolute", left: 16, top: 48, width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
  },
  bagBar: {
    position: "absolute", left: space[5], right: space[5], bottom: space[6], height: 56, borderRadius: radius.pill,
    backgroundColor: color.peacock, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 22,
  },
});
