// Your orders: what's on its way first, then past orders.
import { ACTIVE_STATUSES, api, color, money, space, StatusPill, textFont, Txt, unwrap, type CoreSchemas, type OrderStatus } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

type Order = CoreSchemas["OrderResponse"];

export default function Orders() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(() => {
    setLoading(true);
    api.core.GET("/api/v1/orders", { params: { query: { limit: 50 } } })
      .then((r) => setOrders((unwrap(r) as { items: Order[] }).items))
      .finally(() => setLoading(false));
  }, []);
  useFocusEffect(load);

  const shown = (orders ?? []).filter((o) => o.status !== "pending_payment");
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <Txt variant="h1" accessibilityRole="header" style={{ padding: space[5] }}>Orders</Txt>
      <FlatList
        data={shown.sort((a, b) => Number(ACTIVE_STATUSES.includes(b.status as OrderStatus)) - Number(ACTIVE_STATUSES.includes(a.status as OrderStatus)))}
        keyExtractor={(o) => o.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingBottom: 120 }}
        ListEmptyComponent={orders ? <Txt style={{ color: color.muted }}>No orders yet. Your first one will show up here.</Txt> : undefined}
        renderItem={({ item: o }) => (
          <Pressable accessibilityRole="button" accessibilityLabel={`${o.restaurant_name}, ${o.status}`} onPress={() => router.push(`/order/${o.id}`)}
            style={{ backgroundColor: color.white, borderRadius: 16, padding: space[4], gap: 8 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Txt variant="title" style={{ flex: 1 }}>{o.restaurant_name}</Txt>
              <Text style={[textFont("800"), { fontSize: 15, fontVariant: ["tabular-nums"] }]}>{money(o.total, o.currency)}</Text>
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <StatusPill status={o.status} />
              <Text style={[textFont("400"), { fontSize: 13, color: color.muted }]}>{new Date(o.created_at).toLocaleString()}</Text>
            </View>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}
