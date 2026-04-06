import { useCallback, useState } from "react";
import {
  FlatList,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Restaurant } from "@bhojango/types";

function RestaurantItem({ item }: { item: Restaurant }) {
  return (
    <Pressable
      onPress={() => router.push(`/restaurant/${item.id}`)}
      className="bg-white rounded-xl mb-3 overflow-hidden border border-gray-100"
    >
      {item.banner_url ? (
        <Image source={{ uri: item.banner_url }} className="w-full h-36" resizeMode="cover" />
      ) : (
        <View className="w-full h-36 bg-emerald-50 items-center justify-center">
          <Text className="text-4xl">🍽️</Text>
        </View>
      )}
      <View className="p-3">
        <View className="flex-row items-center justify-between">
          <Text className="text-base font-semibold text-gray-900 flex-1" numberOfLines={1}>
            {item.name}
          </Text>
          <View className={`px-2 py-0.5 rounded-full ml-2 ${item.is_open ? "bg-green-50" : "bg-red-50"}`}>
            <Text className={`text-xs font-medium ${item.is_open ? "text-green-700" : "text-red-600"}`}>
              {item.is_open ? "Open" : "Closed"}
            </Text>
          </View>
        </View>
        <Text className="text-xs text-gray-500 mt-0.5">{item.cuisine_types?.join(", ")}</Text>
        <View className="flex-row items-center gap-3 mt-2">
          <Text className="text-xs text-gray-600">
            ⭐ {item.rating?.toFixed(1)}
          </Text>
          <Text className="text-xs text-gray-400">·</Text>
          <Text className="text-xs text-gray-600">
            {item.delivery_time_min}–{item.delivery_time_max} min
          </Text>
          <Text className="text-xs text-gray-400">·</Text>
          <Text className="text-xs text-gray-600">
            {item.currency === "INR" ? "₹" : "$"}{item.delivery_fee} delivery
          </Text>
        </View>
      </View>
    </Pressable>
  );
}

export default function HomeScreen() {
  const user = useAuthStore((s) => s.user);
  const [searchText, setSearchText] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const { data, refetch, isLoading } = useQuery({
    queryKey: ["restaurants-home"],
    queryFn: async () => {
      const { data } = await api.get("/restaurant/restaurants?limit=20&sort_by=rating");
      return data as { items: Restaurant[]; total: number };
    },
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  return (
    <SafeAreaView className="flex-1 bg-gray-50">
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#f97316" />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View className="px-4 pt-2 pb-4 bg-white">
          <Text className="text-2xl font-bold text-emerald-500">BhojanGo</Text>
          <Text className="text-gray-500 text-sm mt-0.5">
            {user ? `Hey, ${user.full_name?.split(" ")[0]}! 👋` : "Order delicious food"}
          </Text>
        </View>

        {/* Search */}
        <View className="px-4 py-3 bg-white border-b border-gray-100">
          <Pressable
            onPress={() => router.push("/search")}
            className="flex-row items-center bg-gray-100 rounded-xl px-4 py-3 gap-2"
          >
            <Text className="text-gray-400">🔍</Text>
            <Text className="text-gray-400 text-sm">Search restaurants or dishes...</Text>
          </Pressable>
        </View>

        {/* Featured */}
        <View className="px-4 pt-5">
          <View className="flex-row justify-between items-center mb-3">
            <Text className="text-lg font-bold text-gray-900">Top Restaurants</Text>
            <Pressable onPress={() => router.push("/search")}>
              <Text className="text-sm text-emerald-500 font-medium">View All</Text>
            </Pressable>
          </View>

          {isLoading && (
            <View className="space-y-3">
              {[1, 2, 3].map((i) => (
                <View key={i} className="bg-white rounded-xl h-52 animate-pulse" />
              ))}
            </View>
          )}

          {data?.items.map((restaurant) => (
            <RestaurantItem key={restaurant.id} item={restaurant} />
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
