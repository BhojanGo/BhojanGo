// CustomerMenu.html: customise a dish (size cards, segmented choices, add-ons), then add to bag.
import { color, defaultPicks, money, radius, Segmented, space, textFont, Txt, useBag, type OptionGroup, type Pick } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { PlateHeader } from "../lib/plate";
import { useMenu } from "../lib/restaurants";

export default function Item() {
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
    <View style={{ flex: 1, backgroundColor: color.plate }}>
      <PlateHeader label={item.name} height={284} size={200} uri={item.image_url} />
      <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={styles.back}>
        <Icon name="back" />
      </Pressable>
      <View style={styles.sheet} accessibilityLabel={`Customise ${item.name}`}>
        <ScrollView contentContainerStyle={{ padding: space[5], paddingTop: space[6], gap: 20 }}>
          <View>
            <Text style={[textFont("600"), { fontSize: 13, color: color.muted }]}>{menu.restaurant.name}</Text>
            <Txt variant="h1" accessibilityRole="header" style={{ fontSize: 30, lineHeight: 32, marginTop: 4 }}>{item.name}</Txt>
            {item.description ? <Txt style={{ color: color.muted, fontSize: 15, marginTop: 8 }}>{item.description}</Txt> : null}
          </View>
          {groups.map((g) => (
            <View key={g.id} accessibilityRole="radiogroup" accessibilityLabel={g.name}>
              <View style={styles.legend}>
                <Text style={[textFont("800"), { fontSize: 15 }]}>{g.name}</Text>
                <Text style={[textFont("600"), { fontSize: 13, color: color.muted }]}>
                  {g.max_picks === 1 ? (g.min_picks ? "Choose 1" : "Optional") : `Up to ${g.max_picks}`}
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
                        <Text style={[textFont(on ? "800" : "700"), { fontSize: 15 }]}>{title}</Text>
                        <Text style={[textFont("400"), { fontSize: 13, color: color.muted }]}>
                          {sub ? `${sub[0]?.toUpperCase()}${sub.slice(1)} · ` : ""}{money(Number(item.price) + Number(o.price), currency, { decimals: 0 })}
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
                      <Text style={[textFont("400"), { fontSize: 15, flex: 1 }]}>{o.name}</Text>
                      <Text style={[textFont("600"), { fontSize: 15 }]}>+{money(o.price, currency, { decimals: 0 })}</Text>
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
            <Pressable accessibilityRole="button" accessibilityLabel="Fewer" onPress={() => setQty((q) => Math.max(1, q - 1))} style={styles.step}>
              <Text style={[textFont("400"), { fontSize: 22 }]}>−</Text>
            </Pressable>
            <Text style={[textFont("800"), { width: 16, textAlign: "center" }]}>{qty}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="More" onPress={() => setQty((q) => Math.min(20, q + 1))} style={styles.step}>
              <Text style={[textFont("400"), { fontSize: 22, color: color.peacock }]}>+</Text>
            </Pressable>
          </View>
          <Pressable
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
            <Text style={[textFont("800"), { color: color.white, fontSize: 16 }]}>Add to bag</Text>
            <Text style={[textFont("800"), { color: color.white, fontSize: 16, fontVariant: ["tabular-nums"] }]}>
              {money(unit * qty, currency, { decimals: 0 })}
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
    alignItems: "center", justifyContent: "space-between", paddingHorizontal: 22,
  },
});
