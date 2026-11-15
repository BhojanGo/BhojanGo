// Your orders (WebOrders): what's on its way first (tap to track), then past
// orders (tap for the receipt: items, the fair bill, the PDF, rate, report).
import { color, space, StatusPill, textFont, Txt, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, RefreshControl, SectionList, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { isActive, itemsSummary, listOrders, orderCode, statusLabel, type Order } from "../../lib/account";
import { LinkButton, ui } from "../../lib/account-ui";
import { useTabBarSpace } from "../../lib/tabbar";

function OrderRow({ o, index }: { o: Order; index: number }) {
  const { t, money, date, time } = useI18n();
  const active = isActive(o.status);
  const at = o.placed_at ?? o.created_at;
  const status = statusLabel(t, o.status);
  return (
    <Pressable testID={active ? `active-order-${index}` : `past-order-${index}`} accessibilityRole="button"
      accessibilityLabel={`${o.restaurant_name}, ${status}, ${money(o.total, o.currency)}`}
      onPress={() => router.push(active ? `/order/${o.id}` : `/account/receipt/${o.id}`)}
      style={({ pressed }) => [{ backgroundColor: color.white, borderRadius: 16, padding: space[4], gap: 6 }, active && { borderWidth: 1.5, borderColor: color.peacock }, pressed && { opacity: 0.85 }]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space[2] }}>
        <Txt variant="title" numberOfLines={1} style={{ flex: 1 }}>{o.restaurant_name}</Txt>
        <Text style={[textFont("800"), { fontSize: 15, color: color.kohl, fontVariant: ["tabular-nums"] }]}>{money(o.total, o.currency)}</Text>
      </View>
      <Text numberOfLines={1} style={ui.small}>{itemsSummary(o)}</Text>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <Text numberOfLines={1} style={[ui.small, { flex: 1 }]}>{t("app.orders.when", { date: date(at), time: time(at), code: orderCode(o.id) })}</Text>
        <StatusPill status={o.status} label={status} />
      </View>
    </Pressable>
  );
}

export default function Orders() {
  const { t } = useI18n();
  const bottom = useTabBarSpace();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    listOrders()
      .then((o) => { setOrders(o); setError(false); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);
  useFocusEffect(load);

  const all = orders ?? [];
  const sections = [
    { key: "active", title: t("account.orders.active"), data: all.filter((o) => isActive(o.status)) },
    { key: "past", title: t("app.orders.past"), data: all.filter((o) => !isActive(o.status)) },
  ].filter((s) => s.data.length);

  return (
    <SafeAreaView style={ui.screen} edges={["top"]}>
      <Txt variant="h1" accessibilityRole="header" style={{ padding: space[5] }}>{t("account.orders.title")}</Txt>
      <SectionList
        testID="orders-list"
        sections={sections}
        keyExtractor={(o) => o.id}
        stickySectionHeadersEnabled={false}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingBottom: bottom }}
        renderSectionHeader={({ section }) => (
          <Text testID={`orders-${section.key}`} accessibilityRole="header" style={[ui.eyebrow, { marginTop: space[2] }]}>{section.title}</Text>
        )}
        renderItem={({ item, index }) => <OrderRow o={item} index={index} />}
        ListEmptyComponent={
          error ? (
            <View style={{ gap: 6 }}>
              <Text accessibilityRole="alert" style={ui.muted}>{t("account.orders.error")}</Text>
              <LinkButton title={t("common.retry")} onPress={load} />
            </View>
          ) : orders ? (
            <View style={{ gap: 6 }}>
              <Text testID="no-orders" style={ui.muted}>{t("account.orders.empty")}</Text>
              <LinkButton title={t("account.orders.find_food")} onPress={() => router.navigate("/home")} />
            </View>
          ) : (
            <Text style={ui.muted}>{t("account.loading")}</Text>
          )
        }
      />
    </SafeAreaView>
  );
}
