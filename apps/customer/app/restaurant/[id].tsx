// The kitchen: its photo (photo_url, or the branded tile), "New" or its rating, the offer
// and who pays, then the menu by section. A dish shows a photo only when it has
// its own (image_url); otherwise a clean text row. Tap a dish to customise it.
// R36: under the name the rating, distance and minutes, then Delivery / Pickup (the delivery fee /
// "Pickup · 5% fee"); every dish has a visible "+" (on its photo's corner, or round), which becomes
// "− 1 +" once added. Too far: "Too far to deliver · Pickup available" (locked to Pickup), or no adds at
// all; closed: "Closed · opens 11:00 am", browse only.
import { color, LoadError, radius, SafeAreaView, Segmented, space, Txt, type, useBag, useI18n, type BagLine } from "@bhojango/mobile-core";
import { useEffect } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, SectionList, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { FavouriteHeart } from "../../components/Heart";
import { useCardDistance } from "../../components/KitchenCard";
import { useKitchenBlock } from "../../components/PauseBanner";
import { offerBadge, ratingOf } from "../../lib/contract";
import { Icon } from "../../lib/icons";
import { kitchenPhoto, KitchenCover, photo, Photo } from "../../lib/plate";
import { useAvailability, useDiscoverStore, useKitchenCard, useMenu, type MenuItem } from "../../lib/restaurants";

export default function RestaurantScreen() {
  const { t, money, number } = useI18n();
  const dist = useCardDistance();
  const unit = useDiscoverStore((s) => s.data?.distance_unit ?? null);
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
  const closedBlock = useKitchenBlock(menu?.restaurant as { is_open?: boolean; closed_for_now?: boolean } | undefined, avail, notTaking);
  // R36: delivery or pickup. Too far to deliver: pickup only when the kitchen takes it (the switch is locked).
  const pickupOn = Boolean(card?.pickup_enabled ?? (menu?.restaurant as { pickup_enabled?: boolean } | undefined)?.pickup_enabled);
  const tooFar = card?.deliverable === false;
  const lockPickup = tooFar && pickupOn;
  const how = lockPickup ? "pickup" : pickupOn ? bag.fulfillment : "delivery";
  const setHow = bag.setFulfillment;
  useEffect(() => {
    if (lockPickup && bag.fulfillment !== "pickup") setHow("pickup");
  }, [lockPickup, bag.fulfillment, setHow]);
  const blocked = closedBlock ?? (tooFar && !pickupOn ? t("common.too_far") : null);

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
  const rating = ratingOf(r);
  const fee = card?.delivery_fee != null ? Number(card.delivery_fee) : null;
  const meta = [rating.new ? t("common.new") : t("common.rating_short", { stars: number(rating.stars, 1), count: rating.count }),
    dist(card?.distance, unit), t("common.minutes", { min: r.delivery_time_min, max: r.delivery_time_max })].filter(Boolean).join(" · ");
  const deliveryLabel = card?.free_delivery || fee === 0 ? t("common.free_delivery")
    : fee != null ? t("common.delivery_fee", { fee: money(fee, r.currency) }) : t("checkout.delivery");
  const pickupLabel = card?.pickup_fee_percent ? t("kitchen.pickup_fee", { pct: number(Number(card.pickup_fee_percent), 1) }) : t("checkout.pickup");
  const mine = bag.restaurantId === r.id ? bag.lines : [];
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
              <Txt variant="h1" accessibilityRole="header">{r.name}</Txt>
              <Text testID="kitchen-meta" style={[type.label, { color: color.kohl }]}>{meta}</Text>
              {offer ? (
                <View testID="kitchen-offer" style={styles.offer}>
                  <Text style={[type.label, { color: color.kohl }]}>{offerBadge(offer, t, money, r.currency)}</Text>
                </View>
              ) : null}
              {!open && closedBlock ? (
                <View testID="kitchen-banner-closed" accessibilityRole="alert" style={styles.banner}>
                  <Txt testID="kitchen-status" variant="label" style={{ color: color.chili }}>{closedBlock}</Txt>
                </View>
              ) : null}
              {open && tooFar ? (
                <View testID={pickupOn ? "kitchen-banner-pickup" : "kitchen-banner-too-far"} accessibilityRole="alert" style={styles.banner}>
                  <Txt variant="label" style={{ color: color.chili }}>{pickupOn ? t("kitchen.too_far_pickup") : t("common.too_far")}</Txt>
                </View>
              ) : null}
              {pickupOn ? (
                <View testID="kitchen-how" style={{ marginTop: 4 }}>
                  <Segmented label={t("checkout.how")} value={how} onChange={setHow} disabled={lockPickup ? ["delivery"] : []}
                    options={[{ value: "delivery", label: deliveryLabel, testID: "how-delivery" }, { value: "pickup", label: pickupLabel, testID: "how-pickup" }]} />
                </View>
              ) : (
                <Text testID="kitchen-delivery-fee" style={[type.small, { color: color.muted }]}>{tooFar ? t("common.too_far") : deliveryLabel}</Text>
              )}
              {!open && avail?.closed_note ? <Txt testID="kitchen-closed-note" variant="small" style={{ color: color.muted }}>{avail.closed_note}</Txt> : null}
              {!open ? <Txt testID={forNow ? "kitchen-closed-for-now" : undefined} variant="small" style={{ color: color.chili }}>{t(forNow ? "kitchen.closed_for_now_note" : notTaking ? "kitchen.not_taking_orders_note" : "kitchen.closed_note")}</Txt> : null}
              {r.description ? <Txt variant="small" style={{ color: color.muted }}>{r.description}</Txt> : null}
            </View>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <Txt variant="h2" accessibilityRole="header" style={{ paddingHorizontal: space[5], paddingTop: space[6], paddingBottom: space[2] }}>{section.title}</Txt>
        )}
        renderItem={({ item }) => <DishRow item={item} restaurant={{ id: r.id, name: r.name }} currency={r.currency} blocked={blocked}
          lines={mine.filter((l) => l.menuItemId === item.id)} otherCart={bag.restaurantId != null && bag.restaurantId !== r.id} />}
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

function DishRow({ item, restaurant, currency, blocked, lines, otherCart }: {
  item: MenuItem; restaurant: { id: string; name: string }; currency: string; blocked: string | null; lines: BagLine[]; otherCart: boolean;
}) {
  const { t, money } = useI18n();
  const bag = useBag();
  const off = !item.is_available || !!item.sold_out_today;
  const qty = lines.reduce((n, l) => n + l.quantity, 0);
  const choose = item.option_groups.some((g) => g.min_picks > 0); // a size or spice to pick first
  const open = () => router.push({ pathname: "/item", params: { restaurantId: restaurant.id, itemId: item.id } });
  // R36: "+" adds the dish as it is; one with a choice to make (or a cart from another kitchen) opens it first.
  const add = () => {
    if (blocked || off) return;
    if (choose || otherCart) return open();
    bag.add(restaurant, { menuItemId: item.id, name: item.name, unitPrice: Number(item.price), quantity: 1, picks: [], summary: "" });
  };
  const less = () => {
    const last = lines[lines.length - 1];
    if (last) bag.setQuantity(last.key, last.quantity - 1);
  };
  const disabled = !!blocked || off;
  const control = qty > 0 && !disabled ? (
    <View testID={`dish-stepper-${item.id}`} style={styles.stepper}>
      <Pressable testID={`dish-minus-${item.id}`} accessibilityRole="button" accessibilityLabel={t("kitchen.one_less", { name: item.name })}
        onPress={less} hitSlop={6} style={styles.stepBtn}>
        <Text style={[type.h3, { color: color.peacock }]}>−</Text>
      </Pressable>
      <Text testID={`dish-qty-${item.id}`} style={[type.label, { color: color.kohl, minWidth: 18, textAlign: "center" }]}>{qty}</Text>
      <Pressable testID={`dish-plus-${item.id}`} accessibilityRole="button" accessibilityLabel={t("kitchen.add_dish", { name: item.name })}
        onPress={add} hitSlop={6} style={styles.stepBtn}>
        <Text style={[type.h3, { color: color.peacock }]}>+</Text>
      </Pressable>
    </View>
  ) : (
    <Pressable testID={disabled ? (blocked ? "dish-add-blocked" : undefined) : `dish-add-${item.id}`} accessibilityRole="button"
      accessibilityLabel={t("kitchen.add_dish", { name: item.name })} accessibilityState={{ disabled }} disabled={disabled} onPress={add} hitSlop={6}
      style={[styles.add, disabled ? styles.addOff : null]}>
      <Text style={[type.h2, { color: disabled ? color.muted : color.peacock }]}>+</Text>
    </Pressable>
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
      onPress={open}
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
        <View testID="dish-photo-wrap" style={styles.dishPhotoWrap}>
          <Photo uri={pic} label={item.name} style={styles.dishPhoto} testID="photo-dish"
            fallback={<View style={[styles.dishPhoto, { backgroundColor: color.porcelain }]} />} />
          <View testID="dish-on-photo" style={styles.onPhoto}>{control}</View>
        </View>
      ) : control}
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
  dishPhotoWrap: { width: 112, height: 104 },
  dishPhoto: { width: 112, height: 104, borderRadius: radius.card },
  // R36: the "+" (or "− 1 +") sits on the photo's bottom-right corner
  onPhoto: { position: "absolute", right: -6, bottom: -6 },
  stepper: {
    flexDirection: "row", alignItems: "center", gap: 6, height: 40, paddingHorizontal: 6, borderRadius: radius.pill,
    backgroundColor: color.white, borderWidth: 1.5, borderColor: color.lineStrong,
  },
  stepBtn: { width: 28, height: 28, alignItems: "center", justifyContent: "center" },
  banner: { alignSelf: "stretch", marginTop: 6, borderRadius: radius.card, backgroundColor: "#F8ECEA", paddingHorizontal: 12, paddingVertical: 8 },
  add: { width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center" },
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
