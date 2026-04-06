import { useState } from "react";
import {
  FlatList,
  Image,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { useCartStore } from "@/store/cart";
import type { MenuItem, MenuCategory, Restaurant } from "@bhojango/types";

interface RestaurantWithMenu extends Restaurant {
  categories: (MenuCategory & { items: MenuItem[] })[];
}

function MenuItemRow({ item, restaurant }: { item: MenuItem; restaurant: Restaurant }) {
  const { addItem, items } = useCartStore();
  const cartItem = items.find((i) => i.menuItemId === item.id);

  return (
    <View className="flex-row gap-3 py-4 border-b border-gray-100">
      <View className="flex-1">
        <View className="flex-row items-center gap-1.5 mb-1">
          <View
            className={`w-4 h-4 rounded-sm border-2 items-center justify-center ${
              item.is_veg ? "border-green-500" : "border-red-500"
            }`}
          >
            <View className={`w-2 h-2 rounded-full ${item.is_veg ? "bg-green-500" : "bg-red-500"}`} />
          </View>
          {item.is_popular && (
            <Text className="text-xs text-brand-500 font-medium">Bestseller</Text>
          )}
        </View>
        <Text className="text-sm font-medium text-gray-900">{item.name}</Text>
        <Text className="text-sm font-semibold text-gray-800 mt-1">
          {item.currency === "INR" ? "₹" : "$"}{item.price}
        </Text>
        {item.description ? (
          <Text className="text-xs text-gray-500 mt-1" numberOfLines={2}>
            {item.description}
          </Text>
        ) : null}
      </View>
      <View className="items-center gap-2">
        {item.image_url && (
          <Image source={{ uri: item.image_url }} className="w-24 h-20 rounded-xl" resizeMode="cover" />
        )}
        {cartItem ? (
          <View className="flex-row items-center border border-brand-500 rounded-lg overflow-hidden">
            <Pressable
              onPress={() => useCartStore.getState().updateQuantity(item.id, cartItem.quantity - 1)}
              className="w-8 h-8 items-center justify-center bg-brand-500"
            >
              <Text className="text-white font-bold">−</Text>
            </Pressable>
            <Text className="w-8 text-center text-sm font-semibold text-gray-900">
              {cartItem.quantity}
            </Text>
            <Pressable
              onPress={() => addItem({ id: restaurant.id, name: restaurant.name }, item)}
              className="w-8 h-8 items-center justify-center bg-brand-500"
            >
              <Text className="text-white font-bold">+</Text>
            </Pressable>
          </View>
        ) : (
          <Pressable
            onPress={() => addItem({ id: restaurant.id, name: restaurant.name }, item)}
            className="px-4 py-1.5 border border-brand-500 rounded-lg active:bg-brand-50"
          >
            <Text className="text-brand-500 font-semibold text-sm">Add</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

export default function RestaurantScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const cart = useCartStore();
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const { data: restaurant, isLoading } = useQuery({
    queryKey: ["restaurant", id],
    queryFn: async () => {
      const { data } = await api.get(`/restaurant/restaurants/${id}`);
      return data as RestaurantWithMenu;
    },
  });

  if (isLoading || !restaurant) {
    return (
      <View className="flex-1 bg-white items-center justify-center">
        <Text className="text-gray-400">Loading...</Text>
      </View>
    );
  }

  const categories = activeCategory
    ? restaurant.categories?.filter((c) => c.id === activeCategory)
    : restaurant.categories;

  return (
    <SafeAreaView className="flex-1 bg-gray-50" edges={["bottom"]}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Banner */}
        <View className="h-48 bg-gray-200">
          {restaurant.banner_url && (
            <Image source={{ uri: restaurant.banner_url }} className="w-full h-full" resizeMode="cover" />
          )}
        </View>

        {/* Info */}
        <View className="bg-white px-4 py-4 mb-3">
          <View className="flex-row justify-between items-start">
            <View className="flex-1">
              <Text className="text-xl font-bold text-gray-900">{restaurant.name}</Text>
              <Text className="text-sm text-gray-500 mt-0.5">{restaurant.cuisine_types?.join(", ")}</Text>
            </View>
            <View className={`px-2.5 py-1 rounded-full ${restaurant.is_open ? "bg-green-50" : "bg-red-50"}`}>
              <Text className={`text-xs font-medium ${restaurant.is_open ? "text-green-700" : "text-red-600"}`}>
                {restaurant.is_open ? "Open" : "Closed"}
              </Text>
            </View>
          </View>
          <View className="flex-row items-center gap-4 mt-2">
            <Text className="text-sm text-gray-600">⭐ {restaurant.rating?.toFixed(1)}</Text>
            <Text className="text-gray-300">·</Text>
            <Text className="text-sm text-gray-600">
              {restaurant.delivery_time_min}–{restaurant.delivery_time_max} min
            </Text>
            <Text className="text-gray-300">·</Text>
            <Text className="text-sm text-gray-600">
              {restaurant.currency === "INR" ? "₹" : "$"}{restaurant.delivery_fee} delivery
            </Text>
          </View>
        </View>

        {/* Category pills */}
        {restaurant.categories?.length > 1 && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 8, gap: 8 }}
          >
            <Pressable
              onPress={() => setActiveCategory(null)}
              className={`px-4 py-1.5 rounded-full border ${!activeCategory ? "bg-brand-500 border-brand-500" : "bg-white border-gray-300"}`}
            >
              <Text className={`text-sm font-medium ${!activeCategory ? "text-white" : "text-gray-700"}`}>
                All
              </Text>
            </Pressable>
            {restaurant.categories.map((cat) => (
              <Pressable
                key={cat.id}
                onPress={() => setActiveCategory(cat.id)}
                className={`px-4 py-1.5 rounded-full border ${activeCategory === cat.id ? "bg-brand-500 border-brand-500" : "bg-white border-gray-300"}`}
              >
                <Text className={`text-sm font-medium ${activeCategory === cat.id ? "text-white" : "text-gray-700"}`}>
                  {cat.name}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        )}

        {/* Menu */}
        {categories?.map((category) => (
          <View key={category.id} className="bg-white px-4 mb-3">
            <Text className="text-base font-bold text-gray-900 py-3">{category.name}</Text>
            {category.items?.map((item) => (
              <MenuItemRow key={item.id} item={item} restaurant={restaurant} />
            ))}
          </View>
        ))}

        <View className="h-24" />
      </ScrollView>

      {/* Cart button */}
      {cart.restaurantId === restaurant.id && cart.items.length > 0 && (
        <View className="absolute bottom-6 left-4 right-4">
          <Pressable
            onPress={() => router.push("/cart")}
            className="bg-brand-500 rounded-2xl py-4 px-5 flex-row items-center justify-between shadow-lg active:opacity-80"
          >
            <View className="bg-white/20 rounded-full w-7 h-7 items-center justify-center">
              <Text className="text-white font-bold text-sm">{cart.getItemCount()}</Text>
            </View>
            <Text className="text-white font-semibold text-base">View Cart</Text>
            <Text className="text-white font-semibold">
              {restaurant.currency === "INR" ? "₹" : "$"}{cart.getTotal().toFixed(2)}
            </Text>
          </Pressable>
        </View>
      )}
    </SafeAreaView>
  );
}
