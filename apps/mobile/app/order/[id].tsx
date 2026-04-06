import { useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import MapView, { Marker } from "react-native-maps";
import { SafeAreaView } from "react-native-safe-area-context";
import * as SecureStore from "expo-secure-store";

import { api } from "@/lib/api";
import type { Order } from "@bhojango/types";

const STATUS_STEPS = ["confirmed", "preparing", "ready_for_pickup", "picked_up", "delivered"] as const;
const STATUS_LABELS: Record<string, string> = {
  confirmed: "Confirmed",
  preparing: "Preparing",
  ready_for_pickup: "Ready",
  picked_up: "On the way",
  delivered: "Delivered",
};

export default function OrderDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const wsRef = useRef<WebSocket | null>(null);
  const [driverLocation, setDriverLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [etaMinutes, setEtaMinutes] = useState<number | null>(null);
  const [driverName, setDriverName] = useState<string | null>(null);

  const { data: order, refetch } = useQuery({
    queryKey: ["order", id],
    queryFn: async () => {
      const { data } = await api.get(`/order/orders/${id}`);
      return data as Order;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || ["delivered", "cancelled"].includes(status)) return false;
      return 30_000;
    },
  });

  useEffect(() => {
    if (!order || ["delivered", "cancelled"].includes(order.status)) return;

    async function connectWs() {
      const token = await SecureStore.getItemAsync("access_token");
      if (!token) return;

      const wsUrl = `${process.env.EXPO_PUBLIC_WS_URL ?? "ws://localhost:8003"}/ws/track/${id}?token=${token}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string);
          if (msg.type === "location_update") {
            setDriverLocation({ lat: msg.lat, lng: msg.lng });
            if (msg.driver_name) setDriverName(msg.driver_name);
            if (msg.eta_minutes) setEtaMinutes(msg.eta_minutes);
          } else if (msg.type === "status_update") {
            void refetch();
          }
        } catch {
          // ignore
        }
      };
    }

    void connectWs();
    return () => wsRef.current?.close();
  }, [order?.status, id, refetch]);

  if (!order) {
    return (
      <View className="flex-1 bg-white items-center justify-center">
        <Text className="text-gray-400">Loading order...</Text>
      </View>
    );
  }

  const currentStepIndex = STATUS_STEPS.indexOf(order.status as (typeof STATUS_STEPS)[number]);
  const isActive = !["delivered", "cancelled"].includes(order.status);
  const currencySymbol = order.currency === "INR" ? "₹" : "$";

  return (
    <SafeAreaView className="flex-1 bg-gray-50" edges={["bottom"]}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Map */}
        {isActive && driverLocation ? (
          <MapView
            style={{ height: 200 }}
            region={{
              latitude: driverLocation.lat,
              longitude: driverLocation.lng,
              latitudeDelta: 0.02,
              longitudeDelta: 0.02,
            }}
          >
            <Marker
              coordinate={{ latitude: driverLocation.lat, longitude: driverLocation.lng }}
              title={driverName ?? "Driver"}
            />
          </MapView>
        ) : isActive ? (
          <View className="h-40 bg-gray-100 items-center justify-center">
            <Text className="text-gray-400 text-sm">Waiting for driver location...</Text>
          </View>
        ) : null}

        <View className="px-4 py-4">
          {/* Status + ETA */}
          <View className="bg-white rounded-xl p-4 mb-3">
            <View className="flex-row justify-between items-center mb-3">
              <Text className="font-semibold text-gray-900">
                #{order.id.slice(0, 8).toUpperCase()}
              </Text>
              {etaMinutes && (
                <Text className="text-emerald-500 text-sm font-medium">
                  ~{etaMinutes} min away
                </Text>
              )}
            </View>

            {/* Timeline */}
            {order.status !== "cancelled" && (
              <View className="flex-row items-center">
                {STATUS_STEPS.map((step, i) => (
                  <View key={step} className="flex-1 items-center">
                    <View
                      className={`w-4 h-4 rounded-full ${
                        i <= currentStepIndex ? "bg-emerald-500" : "bg-gray-200"
                      }`}
                    />
                    {i < STATUS_STEPS.length - 1 && (
                      <View
                        className={`absolute top-2 left-1/2 right-0 h-0.5 ${
                          i < currentStepIndex ? "bg-emerald-500" : "bg-gray-200"
                        }`}
                      />
                    )}
                    <Text className={`text-xs mt-1 text-center ${i <= currentStepIndex ? "text-emerald-700" : "text-gray-400"}`}>
                      {STATUS_LABELS[step]}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {order.status === "cancelled" && (
              <View className="bg-red-50 rounded-lg px-3 py-2">
                <Text className="text-red-700 font-medium text-sm">Order Cancelled</Text>
              </View>
            )}
          </View>

          {/* Driver info */}
          {driverName && (
            <View className="bg-white rounded-xl p-4 mb-3 flex-row items-center gap-3">
              <View className="w-10 h-10 rounded-full bg-emerald-100 items-center justify-center">
                <Text className="text-emerald-700 font-bold">{driverName[0]}</Text>
              </View>
              <View>
                <Text className="text-xs text-gray-500">Delivery Partner</Text>
                <Text className="text-sm font-medium text-gray-900">{driverName}</Text>
              </View>
            </View>
          )}

          {/* Restaurant + Items */}
          <View className="bg-white rounded-xl p-4 mb-3">
            <Text className="font-semibold text-gray-900 mb-3">{order.restaurant_name}</Text>
            {order.items?.map((item) => (
              <View key={item.id} className="flex-row justify-between mb-2">
                <Text className="text-sm text-gray-700">
                  {item.name} × {item.quantity}
                </Text>
                <Text className="text-sm text-gray-700">
                  {currencySymbol}{(item.unit_price * item.quantity).toFixed(2)}
                </Text>
              </View>
            ))}
            <View className="h-px bg-gray-100 my-2" />
            <View className="flex-row justify-between">
              <Text className="font-semibold text-gray-900">Total</Text>
              <Text className="font-semibold text-gray-900">
                {currencySymbol}{order.total?.toFixed(2)}
              </Text>
            </View>
          </View>

          {/* Reorder */}
          {order.status === "delivered" && (
            <Pressable
              onPress={() => {
                if (order.restaurant_id) router.push(`/restaurant/${order.restaurant_id}`);
              }}
              className="border border-emerald-500 rounded-xl py-3 items-center active:bg-emerald-50"
            >
              <Text className="text-emerald-500 font-semibold">Reorder</Text>
            </Pressable>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
