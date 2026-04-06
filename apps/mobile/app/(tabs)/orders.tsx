import { FlatList, Pressable, Text, View } from "react-native";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import type { Order } from "@bhojango/types";

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: "bg-yellow-50", text: "text-yellow-700" },
  confirmed: { bg: "bg-blue-50", text: "text-blue-700" },
  preparing: { bg: "bg-orange-50", text: "text-orange-700" },
  ready_for_pickup: { bg: "bg-purple-50", text: "text-purple-700" },
  picked_up: { bg: "bg-indigo-50", text: "text-indigo-700" },
  delivered: { bg: "bg-green-50", text: "text-green-700" },
  cancelled: { bg: "bg-red-50", text: "text-red-600" },
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  preparing: "Preparing",
  ready_for_pickup: "Ready for Pickup",
  picked_up: "Out for Delivery",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

function OrderCard({ order }: { order: Order }) {
  const colors = STATUS_COLORS[order.status] ?? { bg: "bg-gray-50", text: "text-gray-700" };
  const isActive = !["delivered", "cancelled"].includes(order.status);

  return (
    <Pressable
      onPress={() => router.push(`/order/${order.id}`)}
      className="bg-white rounded-xl p-4 mb-3 border border-gray-100"
    >
      <View className="flex-row justify-between items-start mb-2">
        <Text className="font-semibold text-gray-900 text-sm">
          #{order.id.slice(0, 8).toUpperCase()}
        </Text>
        <View className={`px-2.5 py-1 rounded-full ${colors.bg}`}>
          <Text className={`text-xs font-semibold ${colors.text}`}>
            {STATUS_LABELS[order.status] ?? order.status}
          </Text>
        </View>
      </View>
      <Text className="text-sm text-gray-700">{order.restaurant_name ?? "Restaurant"}</Text>
      <Text className="text-xs text-gray-400 mt-1">
        {order.items?.length ?? 0} items · {order.currency === "INR" ? "₹" : "$"}
        {order.total?.toFixed(2)}
      </Text>
      {isActive && (
        <View className="flex-row items-center gap-1 mt-2">
          <View className="w-2 h-2 rounded-full bg-brand-500" />
          <Text className="text-xs text-brand-500 font-medium">Track Order</Text>
        </View>
      )}
    </Pressable>
  );
}

export default function OrdersScreen() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const { data } = await api.get("/order/orders?limit=50");
      return data as { items: Order[]; total: number };
    },
  });

  return (
    <SafeAreaView className="flex-1 bg-gray-50">
      <View className="px-4 pt-4 pb-2">
        <Text className="text-2xl font-bold text-gray-900">Your Orders</Text>
      </View>

      <FlatList
        data={data?.items ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ padding: 16, paddingTop: 8 }}
        refreshing={isLoading}
        onRefresh={refetch}
        ListEmptyComponent={
          !isLoading ? (
            <View className="flex-1 items-center justify-center pt-20">
              <Text className="text-5xl mb-3">📦</Text>
              <Text className="text-lg font-semibold text-gray-900 mb-1">No orders yet</Text>
              <Text className="text-gray-500 text-sm mb-4">Your order history will appear here</Text>
              <Pressable
                onPress={() => router.push("/")}
                className="px-6 py-2.5 bg-brand-500 rounded-xl"
              >
                <Text className="text-white font-semibold">Order Now</Text>
              </Pressable>
            </View>
          ) : null
        }
        renderItem={({ item }) => <OrderCard order={item} />}
      />
    </SafeAreaView>
  );
}
