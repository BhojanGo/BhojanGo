// CustomerMenu.html: customise a dish (size cards, segmented choices, add-ons), then add to bag.
// The dish's own photo on top when it has one; otherwise no photo frame at all.
import {
  color, defaultPicks, num, type OptionGroup, type Pick, radius, Segmented, space, Txt, type, useBag, useI18n,
} from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { FavouriteHeart } from "../components/Heart";
import { Icon } from "../lib/icons";
import { photo, Photo } from "../lib/plate";
import { useMenu } from "../lib/restaurants";

export default function Item() {
  const { t, money } = useI18n();
  const { restaurantId, itemId } = useLocalSearchParams<{ restaurantId: string; itemId: string }>();
  const { menu } = useMenu(restaurantId);
  const item = menu?.categories.flatMap((c) => c.items).find((i) => i.id === itemId);
  const groups = useMemo(() => (item?.option_groups ?? []).filter((g) => g.options.length > 0), [item]);
  const [picks, setPicks] = useState<Pick[] | null>(null);
  const [qty, setQty] = useState(1);
  const add = useBag((s) => s.add);
  if (!menu || !item) return null;
  const chosen = picks ?? defaultPicks(groups);
  const currency = menu.restaurant.currency;
  const pic = photo(item.image_url, 800);

  const isPicked = (g: OptionGroup, o: string) => chosen.some((p) => p.group === g.name && p.option === o);
  const toggle = (g: OptionGroup, o: string) => {
    const others = chosen.filter((p) => p.group !== g.name);
    const mine = chosen.filter((p) => p.group === g.name);
    if (g.max_picks === 1) return setPicks([...others, { group: g.name, option: o }]);
    const on = mine.some((p) => p.option === o);
    if (!on && mine.length >= g.max_picks) return;
    setPicks([...others, ...(on ? mine.filter((p) => p.option !== o) : [...mine, { group: g.name, option: o }])]);
  };
  const extras = chosen.reduce((sum, p) => {
    const o = groups.find((g) => g.name === p.group)?.options.find((x) => x.name === p.option);
    return sum + Number(o?.price ?? 0);
  }, 0);
  const unit = Number(item.price) + extras;
  const complete = groups.every((g) => chosen.filter((p) => p.group === g.name).length >= g.min_picks);

  return (
    <View style={{ flex: 1, backgroundColor: pic ? color.plate : color.porcelain }}>
      {pic ? <Photo uri={pic} label={item.name} style={{ height: 284 }} testID="item-photo" fallback={<View style={{ height: 284 }} />} /> : null}
      <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}>
        <Icon name="back" />
      </Pressable>
      <View style={{ position: "absolute", right: 16, top: 16 }}>
        <FavouriteHeart kind="item" id={item.id} name={item.name} size={44} testID="item-heart" />
      </View>
      <View testID="item" style={[styles.sheet, !pic && styles.sheetTop]} accessibilityLabel={t("app.item.customise", { name: item.name })}>
        <ScrollView contentContainerStyle={{ padding: space[5], paddingTop: space[6], gap: 20 }}>
          <View>
            <Text style={[type.small, { color: color.muted }]}>{menu.restaurant.name}</Text>
            <Txt variant="h1" accessibilityRole="header" style={{ marginTop: 4 }}>{item.name}</Txt>
            {item.description ? <Txt style={{ color: color.muted, marginTop: 8 }}>{item.description}</Txt> : null}
          </View>
          {groups.map((g) => (
            <View key={g.id} accessibilityRole="radiogroup" accessibilityLabel={g.name}>
              <View style={styles.legend}>
                <Text style={type.label}>{g.name}</Text>
                <Text style={[type.small, { color: color.muted }]}>
                  {g.min_picks > 0
                    ? (g.min_picks === g.max_picks ? t("kitchen.required_pick", { count: g.min_picks }) : t("kitchen.required_range", { min: g.min_picks, max: g.max_picks }))
                    : t("kitchen.optional_upto", { count: g.max_picks })}
                </Text>
              </View>
              {g.max_picks === 1 && g.options.every((o) => Number(o.price) === 0) && g.options.length <= 4 ? (
                <Segmented
                  label={g.name}
                  value={chosen.find((p) => p.group === g.name)?.option ?? ""}
                  onChange={(o) => toggle(g, o)}
                  options={g.options.filter((o) => o.is_available).map((o) => ({ value: o.name, label: o.name }))}
                />
              ) : g.max_picks === 1 ? (
                <View style={styles.cards}>
                  {g.options.filter((o) => o.is_available).map((o) => {
                    const on = isPicked(g, o.name);
                    const [title, sub] = o.name.split(" · ");
                    return (
                      <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ checked: on }} accessibilityLabel={o.name}
                        onPress={() => toggle(g, o.name)} style={[styles.card, on && styles.cardOn]}>
                        <Text style={type.label}>{title}</Text>
                        <Text style={[type.small, { color: color.muted }]}>
                          {sub ? `${sub[0]?.toUpperCase()}${sub.slice(1)} · ` : ""}{money(Number(item.price) + Number(o.price), currency, { whole: true })}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              ) : (
                g.options.filter((o) => o.is_available).map((o) => {
                  const on = isPicked(g, o.name);
                  return (
                    <Pressable key={o.id} accessibilityRole="checkbox" accessibilityState={{ checked: on }} accessibilityLabel={o.name}
                      onPress={() => toggle(g, o.name)} style={styles.addon}>
                      <Text style={[type.body, { flex: 1 }]}>{o.name}</Text>
                      <Text style={type.label}>+{money(o.price, currency, { whole: true })}</Text>
                      <View style={[styles.check, on && styles.checkOn]}>{on ? <Icon name="check" size={16} stroke={color.white} /> : null}</View>
                    </Pressable>
                  );
                })
              )}
            </View>
          ))}
        </ScrollView>
        <View style={styles.footer}>
          <View style={styles.stepper}>
            <Pressable accessibilityRole="button" accessibilityLabel={t("kitchen.less")} onPress={() => setQty((q) => Math.max(1, q - 1))} style={styles.step}>
              <Text style={type.h2}>−</Text>
            </Pressable>
            <Text style={[type.label, num, { minWidth: 16, textAlign: "center" }]}>{qty}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={t("kitchen.more_qty")} onPress={() => setQty((q) => Math.min(20, q + 1))} style={styles.step}>
              <Text style={[type.h2, { color: color.peacock }]}>+</Text>
            </Pressable>
          </View>
          <Pressable
            testID="add-to-bag"
            accessibilityRole="button"
            accessibilityState={{ disabled: !complete }}
            disabled={!complete}
            onPress={() => {
              const summary = chosen.map((p) => p.option.split(" · ")[0]?.toLowerCase()).join(", ");
              add({ id: menu.restaurant.id, name: menu.restaurant.name },
                { menuItemId: item.id, name: item.name, unitPrice: unit, quantity: qty, picks: chosen, summary });
              router.back();
            }}
            style={[styles.addBtn, !complete && { opacity: 0.5 }]}
          >
            <Text style={[type.label, num, { color: color.white }]}>
              {t("kitchen.add_to_bag", { price: money(unit * qty, currency, { whole: true }) })}
            </Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  back: {
    position: "absolute", left: 16, top: 16, width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
  },
  sheet: { position: "absolute", left: 0, right: 0, top: 256, bottom: 0, borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet, backgroundColor: color.white },
  // No photo: the sheet starts under the back button (no empty frame above it).
  sheetTop: { top: 72 },
  legend: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 },
  cards: { flexDirection: "row", gap: space[3] },
  card: { flex: 1, padding: 14, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.line, gap: 2 },
  cardOn: { borderWidth: 2, borderColor: color.peacock, backgroundColor: color.peacockMist },
  addon: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 48, borderBottomWidth: 1, borderBottomColor: color.divider },
  check: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  checkOn: { backgroundColor: color.peacock, borderColor: color.peacock },
  footer: { flexDirection: "row", gap: 10, alignItems: "center", paddingHorizontal: space[5], paddingTop: space[3], paddingBottom: space[6] },
  stepper: { flexDirection: "row", alignItems: "center", borderRadius: radius.pill, backgroundColor: color.porcelain, height: 56 },
  step: { width: 48, height: 56, alignItems: "center", justifyContent: "center" },
  addBtn: {
    flex: 1, height: 56, borderRadius: radius.pill, backgroundColor: color.peacock, flexDirection: "row",
    alignItems: "center", justifyContent: "center", paddingHorizontal: 22,
  },
});
