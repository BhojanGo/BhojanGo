// The kitchen shell (PartnerOrders.html): the dark rail on the left, the screen on the right.
import { useI18n, useSession } from "@bhojango/mobile-core";
import { Redirect, router, Slot, usePathname, type Href } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useBoard, useBoardLoop, NEW } from "../../lib/board";
import { useKitchen } from "../../lib/data";
import { Icon, Mark, textFont, tone, type IconName } from "../../lib/ui";

type RailItem = { href: string; key: "orders" | "menu" | "payouts" | "help"; icon: IconName };

const RAIL: RailItem[] = [
  { href: "/orders", key: "orders", icon: "orders" },
  { href: "/menu", key: "menu", icon: "menu" },
  { href: "/payouts", key: "payouts", icon: "payouts" },
];

export default function KitchenLayout() {
  const status = useSession((s) => s.status);
  const kitchen = useKitchen((s) => s.kitchen);
  const path = usePathname();
  const { t } = useI18n();
  useBoardLoop(kitchen?.status === "active" ? kitchen.id : undefined);
  const waiting = useBoard((s) => s.orders.filter((o) => NEW.includes(o.status)).length);

  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  if (!kitchen) return <Redirect href="/" />;
  if (kitchen.status !== "active") return <Redirect href="/apply" />;

  const item = (r: RailItem, extra?: object) => {
    const on = path.startsWith(r.href);
    const title = t(`partner.rail.${r.key}`);
    return (
      <Pressable key={r.href} testID={`rail-${r.key}`} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={title}
        onPress={() => router.replace(r.href as Href)} style={[s.item, on && { backgroundColor: tone.railOn }, extra]}>
        <Icon name={r.icon} stroke={on ? tone.white : tone.railText} />
        <Text style={[textFont(on ? "800" : "600"), { fontSize: 12, color: on ? tone.white : tone.railText, textAlign: "center" }]} numberOfLines={1}>{title}</Text>
        {r.href === "/orders" && waiting > 0 && !on ? <View style={s.dot} /> : null}
      </Pressable>
    );
  };

  return (
    <View style={s.screen}>
      <SafeAreaView edges={["left", "top", "bottom"]} style={s.rail}>
        <View style={{ marginBottom: 12 }}><Mark size={40} /></View>
        {RAIL.map((r) => item(r))}
        <View style={{ flex: 1 }} />
        {item({ href: "/help", key: "help", icon: "help" })}
      </SafeAreaView>
      <View style={{ flex: 1 }}>
        <Slot />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, flexDirection: "row", backgroundColor: tone.porcelain },
  rail: { width: 88, backgroundColor: tone.rail, alignItems: "center", paddingVertical: 20, gap: 8 },
  item: { width: 72, height: 64, borderRadius: 16, alignItems: "center", justifyContent: "center", gap: 4 },
  dot: { position: "absolute", top: 8, right: 14, width: 10, height: 10, borderRadius: 5, backgroundColor: tone.chili },
});
