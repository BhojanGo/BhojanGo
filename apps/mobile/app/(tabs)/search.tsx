import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import type { Restaurant } from "@bhojango/types";

const CUISINES = ["All", "Indian", "Chinese", "Italian", "Mexican", "Fast Food", "Thai"];

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const [cuisine, setCuisine] = useState("All");

  const { data, isLoading } = useQuery({
    queryKey: ["search", query, cuisine],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "20" });
      if (query) params.set("q", query);
      if (cuisine !== "All") params.set("cuisine_type", cuisine.toLowerCase());
      const { data } = await api.get(`/restaurant/restaurants?${params.toString()}`);
      return data as { items: Restaurant[]; total: number };
    },
    enabled: true,
  });

  return (
    <SafeAreaView className="flex-1 bg-gray-50">
      {/* Search bar */}
      <View className="bg-white px-4 py-3 border-b border-gray-100">
        <View className="flex-row items-center bg-gray-100 rounded-xl px-4 gap-2">
          <Text className="text-gray-400">🔍</Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search restaurants or dishes..."
            placeholderTextColor="#9ca3af"
            className="flex-1 py-3 text-sm text-gray-900"
            returnKeyType="search"
            autoFocus
          />
          {query ? (
            <Pressable onPress={() => setQuery("")}>
              <Text className="text-gray-400 text-lg">✕</Text>
            </Pressable>
          ) : null}
        </View>
      </View>

      {/* Cuisine filters */}
      <View className="bg-white border-b border-gray-100">
        <FlatList
          data={CUISINES}
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 10, gap: 8 }}
          keyExtractor={(item) => item}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => setCuisine(item)}
              className={`px-4 py-1.5 rounded-full border ${
                cuisine === item
                  ? "bg-brand-500 border-brand-500"
                  : "bg-white border-gray-300"
              }`}
            >
              <Text className={`text-sm font-medium ${cuisine === item ? "text-white" : "text-gray-700"}`}>
                {item}
              </Text>
            </Pressable>
          )}
        />
      </View>

      {isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#f97316" />
        </View>
      ) : (
        <FlatList
          data={data?.items ?? []}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 16, gap: 12 }}
          ListEmptyComponent={
            <View className="flex-1 items-center justify-center pt-20">
              <Text className="text-4xl mb-3">🍽️</Text>
              <Text className="text-gray-500">No restaurants found</Text>
            </View>
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push(`/restaurant/${item.id}`)}
              className="bg-white rounded-xl overflow-hidden border border-gray-100 flex-row"
            >
              <View className="w-24 h-24 bg-orange-50 items-center justify-center">
                {item.logo_url ? (
                  <Image source={{ uri: item.logo_url }} className="w-24 h-24" resizeMode="cover" />
                ) : (
                  <Text className="text-3xl">🍽️</Text>
                )}
              </View>
              <View className="flex-1 p-3 justify-center">
                <Text className="font-semibold text-gray-900" numberOfLines={1}>{item.name}</Text>
                <Text className="text-xs text-gray-500 mt-0.5" numberOfLines={1}>
                  {item.cuisine_types?.join(", ")}
                </Text>
                <View className="flex-row items-center gap-2 mt-1.5">
                  <Text className="text-xs text-gray-600">⭐ {item.rating?.toFixed(1)}</Text>
                  <Text className="text-gray-300">·</Text>
                  <Text className="text-xs text-gray-600">
                    {item.delivery_time_min}–{item.delivery_time_max} min
                  </Text>
                </View>
              </View>
            </Pressable>
          )}
        />
      )}
    </SafeAreaView>
  );
}
