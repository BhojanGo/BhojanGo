// The kitchen: its photo (photo_url, or the branded tile), "New" or its rating, the offer
// and who pays, then the menu by section. A dish shows a photo only when it has
// its own (image_url); otherwise a clean text row. Tap a dish to customise it.
import { color, cuisineName, LoadError, radius, SafeAreaView, space, Txt, type, useBag, useI18n } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, SectionList, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { FavouriteHeart } from "../../components/Heart";
import { RatingBadge } from "../../components/KitchenCard";
import { useKitchenBlock } from "../../components/PauseBanner";
import { offerBadge } from "../../lib/contract";
import { Icon } from "../../lib/icons";
import { kitchenPhoto, KitchenCover, photo, Photo } from "../../lib/plate";
import { useAvailability, useKitchenCard, useMenu, type MenuItem } from "../../lib/restaurants";

export default function RestaurantScreen() {
  const { t, money } = useI18n();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { menu, failure, reload } = useMenu(id);
  const card = useKitchenCard(id);
  // Over the cover: below the status bar in production; under the test banner (which has it) the inset is 0.
  const floatTop = useSafeAreaInsets().top + space[3];
  const bag = useBag();
  const inBag = bag.restaurantId === id ? bag.lines.reduce((n, l) => n + l.quantity, 0) : 0;
  // R19: the city's ordering paused, or the kitchen closed: every dish's "+" is off, with the reason.
  // R27: and a kitchen closed by its own hours or the city's delivery hours ("Closed · opens 6:30 am").
  const avail = useAvailability(id);
  // R27: the kitchen's tablet isn't connected: its availability says so (its discover card until that's known).
  const notTaking = avail ? avail.reason_code === "not_taking_orders" || !!avail.not_taking_orders : Boolean(card?.not_taking_orders);
  const blocked = useKitchenBlock(menu?.restaurant as { is_open?: boolean; closed_for_now?: boolean } | undefined, avail, notTaking);

  if (!menu) {
    return (
      <SafeAreaView style={styles.center}>
        {failure ? <LoadError error={failure} onRetry={reload} fill style={{ alignSelf: "stretch" }} /> : <ActivityIndicator color={color.peacock} />}
      </SafeAreaView>
    );
  }
  const r = menu.restaurant;
  const offer = card?.offer ?? null;
  const forNow = Boolean((r as { closed_for_now?: boolean }).closed_for_now || avail?.closed_for_now); // R17: paused by BhojanGo
  const open = r.is_open !== false && !forNow && avail?.open_now !== false && !notTaking;
  const total = bag.lines.reduce((n, l) => n + l.unitPrice * l.quantity, 0);
  return (
    <View testID="kitchen" style={{ flex: 1, backgroundColor: color.porcelain }}>
      <SectionList
        sections={menu.categories.map((c) => ({ title: c.name || t("kitchen.more"), data: c.items }))}
        keyExtractor={(i) => i.id}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={{ paddingBottom: 120 }}
        ListHeaderComponent={
          <View>
            <KitchenCover name={r.name} cover={kitchenPhoto(r)} height={220} width={1600} />
            <View style={styles.head}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <Txt variant="h1" accessibilityRole="header" style={{ flex: 1 }}>{r.name}</Txt>
                <RatingBadge x={r} testID="kitchen-rating" />
              </View>
              <Text style={[type.small, { color: color.muted }]}>
                {[...r.cuisine_types.slice(0, 3).map((c) => cuisineName(t, c)), t("common.minutes", { min: r.delivery_time_min, max: r.delivery_time_max })].join(" · ")}
              </Text>
              {offer ? (
                <View testID="kitchen-offer" style={styles.offer}>
                  <Text style={[type.label, { color: color.kohl }]}>{offerBadge(offer, t, money, r.currency)}</Text>
                </View>
              ) : null}
              {!open && blocked ? <Txt testID="kitchen-status" variant="label" style={{ color: color.chili }}>{blocked}</Txt> : null}
              {!open && avail?.closed_note ? <Txt testID="kitchen-closed-note" variant="small" style={{ color: color.muted }}>{avail.closed_note}</Txt> : null}
              {!open ? <Txt testID={forNow ? "kitchen-closed-for-now" : undefined} variant="small" style={{ color: color.chili }}>{t(forNow ? "kitchen.closed_for_now_note" : notTaking ? "kitchen.not_taking_orders_note" : "kitchen.closed_note")}</Txt> : null}
              {r.description ? <Txt variant="small" style={{ color: color.muted }}>{r.description}</Txt> : null}
            </View>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <Txt variant="h2" accessibilityRole="header" style={{ paddingHorizontal: space[5], paddingTop: space[6], paddingBottom: space[2] }}>{section.title}</Txt>
        )}
        renderItem={({ item }) => <DishRow item={item} restaurantId={r.id} currency={r.currency} blocked={blocked} />}
      />
      <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => (router.canGoBack() ? router.back() : router.replace("/home"))} style={[styles.round, { left: 16, top: floatTop }]}>
        <Icon name="back" />
      </Pressable>
      <View style={{ position: "absolute", right: 16, top: floatTop }}>
        <FavouriteHeart kind="restaurant" id={r.id} name={r.name} size={44} testID="kitchen-heart" />
      </View>
      {inBag > 0 ? (
        <Pressable testID="view-bag" accessibilityRole="button" onPress={() => router.push("/bag")} style={styles.bagBar}>
          {/* As the website's bar: "View cart", then the summary; no "·" between them (R12). */}
          <Text style={[type.label, { color: color.white }]}>{t("kitchen.view_bag")}</Text>
          <Text style={[type.label, { color: color.white, flexShrink: 1 }]} numberOfLines={1}>
            {t("kitchen.bar_summary", { count: inBag, total: money(total, r.currency) })}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function DishRow({ item, restaurantId, currency, blocked }: { item: MenuItem; restaurantId: string; currency: string; blocked: string | null }) {
  const { t, money } = useI18n();
  const off = !item.is_available || !!item.sold_out_today;
  // Blocked (paused or closed): the dish still opens to read about it; its "+" is off and says why.
  const plus = (
    <View testID={blocked ? "dish-add-blocked" : undefined} accessibilityState={{ disabled: !!blocked }}
      style={[styles.add, blocked ? styles.addOff : null]}>
      <Text style={[type.h2, { color: blocked ? color.muted : color.peacock }]}>+</Text>
    </View>
  );
  // Only the dish's own photo, never a stand-in.
  const pic = photo(item.image_url, 400);
  return (
    <Pressable
      testID={`dish-${item.id}`}
      accessibilityRole="button"
      accessibilityLabel={item.name}
      accessibilityHint={off ? t("kitchen.sold_out_today") : blocked ?? t("kitchen.add_dish", { name: item.name })}
      accessibilityState={{ disabled: off }}
      disabled={off}
      onPress={() => router.push({ pathname: "/item", params: { restaurantId, itemId: item.id } })}
      style={[styles.item, off && { opacity: 0.5 }]}
    >
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={[type.label, { color: color.kohl }]}>{item.name}</Text>
        <Text style={[type.label, { color: color.kohl }]}>
          {off ? t("kitchen.sold_out_today") : money(item.price, currency)}
        </Text>
        {item.description ? (
          <Text numberOfLines={2} style={[type.small, { color: color.muted }]}>{item.description}</Text>
        ) : null}
        {blocked && !off ? <Text testID="dish-blocked-reason" style={[type.small, { color: color.chili }]}>{blocked}</Text> : null}
      </View>
      {pic ? (
        <View>
          <Photo uri={pic} label={item.name} style={styles.dishPhoto} testID="photo-dish"
            fallback={plus} />
        </View>
      ) : plus}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  head: {
    marginTop: -24, backgroundColor: color.white, borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet,
    padding: space[5], gap: 6,
  },
  offer: { alignSelf: "flex-start", marginTop: 4, borderRadius: radius.pill, backgroundColor: color.plate, paddingHorizontal: 12, paddingVertical: 6 },
  item: {
    marginHorizontal: space[5], marginBottom: space[3], padding: space[4], borderRadius: radius.card, backgroundColor: color.white,
    flexDirection: "row", gap: space[3], alignItems: "center",
  },
  dishPhoto: { width: 104, height: 96, borderRadius: radius.card },
  add: { width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  addOff: { borderColor: color.line, backgroundColor: color.porcelain, opacity: 0.6 },
  round: {
    position: "absolute", width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
  },
  bagBar: {
    position: "absolute", left: space[5], right: space[5], bottom: space[6], height: 56, borderRadius: radius.pill,
    backgroundColor: color.peacock, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space[3], paddingHorizontal: 22,
  },
});
