// The kitchen shell (PartnerOrders.html): the dark rail on the left, the screen on the right.
import { useSession } from "@bhojango/mobile-core";
import { Redirect, router, Slot, usePathname, type Href } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useBoard, useBoardLoop, NEW } from "../../lib/board";
import { useKitchen } from "../../lib/data";
import { Icon, Mark, textFont, tone, type IconName } from "../../lib/ui";

const RAIL: { href: string; title: string; icon: IconName }[] = [
  { href: "/orders", title: "Orders", icon: "orders" },
  { href: "/menu", title: "Menu", icon: "menu" },
  { href: "/payouts", title: "Payouts", icon: "payouts" },
];

export default function KitchenLayout() {
  const status = useSession((s) => s.status);
  const kitchen = useKitchen((s) => s.kitchen);
  const path = usePathname();
  useBoardLoop(kitchen?.status === "active" ? kitchen.id : undefined);
  const waiting = useBoard((s) => s.orders.filter((o) => NEW.includes(o.status)).length);

  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  if (!kitchen) return <Redirect href="/" />;
  if (kitchen.status !== "active") return <Redirect href="/apply" />;

  const item = (r: { href: string; title: string; icon: IconName }, extra?: object) => {
    const on = path.startsWith(r.href);
    return (
      <Pressable key={r.href} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={r.title}
        onPress={() => router.replace(r.href as Href)} style={[s.item, on && { backgroundColor: tone.railOn }, extra]}>
        <Icon name={r.icon} stroke={on ? tone.white : tone.railText} />
        <Text style={[textFont(on ? "800" : "600"), { fontSize: 12, color: on ? tone.white : tone.railText }]}>{r.title}</Text>
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
        {item({ href: "/help", title: "Help", icon: "help" })}
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
