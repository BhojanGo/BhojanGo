import { Pressable, ScrollView, Text, View } from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { useCartStore } from "@/store/cart";

export default function CartScreen() {
  const { items, restaurantName, updateQuantity, removeItem, getSubtotal, deliveryFee, getTotal } =
    useCartStore();

  if (items.length === 0) {
    return (
      <SafeAreaView className="flex-1 bg-gray-50 items-center justify-center">
        <Text className="text-5xl mb-3">🛒</Text>
        <Text className="text-xl font-semibold text-gray-900 mb-2">Your cart is empty</Text>
        <Text className="text-gray-500 mb-6">Add items from a restaurant to get started</Text>
        <Pressable
          onPress={() => router.push("/")}
          className="px-6 py-3 bg-emerald-500 rounded-xl active:opacity-80"
        >
          <Text className="text-white font-semibold">Browse Restaurants</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  const subtotal = getSubtotal();
  const tax = Math.round(subtotal * 0.1 * 100) / 100;
  const total = getTotal() + tax;

  return (
    <SafeAreaView className="flex-1 bg-gray-50" edges={["bottom"]}>
      <ScrollView>
        {restaurantName && (
          <View className="bg-white px-4 py-3 mb-2 flex-row justify-between items-center">
            <Text className="text-sm text-gray-500">From {restaurantName}</Text>
          </View>
        )}

        {/* Items */}
        <View className="bg-white mb-2">
          {items.map((item) => (
            <View key={item.menuItemId} className="flex-row items-center px-4 py-4 border-b border-gray-100">
              <View className="flex-1">
                <Text className="text-sm font-medium text-gray-900">{item.name}</Text>
                <Text className="text-sm text-gray-600 mt-0.5">
                  ${(item.price * item.quantity).toFixed(2)}
                </Text>
              </View>
              <View className="flex-row items-center gap-2">
                <Pressable
                  onPress={() => updateQuantity(item.menuItemId, item.quantity - 1)}
                  className="w-8 h-8 rounded-full border border-gray-300 items-center justify-center"
                >
                  <Text className="text-gray-600 text-lg font-medium">−</Text>
                </Pressable>
                <Text className="w-6 text-center text-sm font-semibold">{item.quantity}</Text>
                <Pressable
                  onPress={() => updateQuantity(item.menuItemId, item.quantity + 1)}
                  className="w-8 h-8 rounded-full border border-gray-300 items-center justify-center"
                >
                  <Text className="text-gray-600 text-lg font-medium">+</Text>
                </Pressable>
                <Pressable
                  onPress={() => removeItem(item.menuItemId)}
                  className="ml-1 w-7 h-7 items-center justify-center"
                >
                  <Text className="text-gray-400 text-lg">✕</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </View>

        {/* Bill */}
        <View className="bg-white px-4 py-4 mb-6">
          <Text className="font-semibold text-gray-900 mb-3">Bill Summary</Text>
          <View className="gap-2">
            <View className="flex-row justify-between">
              <Text className="text-sm text-gray-500">Item Total</Text>
              <Text className="text-sm text-gray-700">${subtotal.toFixed(2)}</Text>
            </View>
            <View className="flex-row justify-between">
              <Text className="text-sm text-gray-500">Delivery Fee</Text>
              <Text className="text-sm text-gray-700">
                {deliveryFee === 0 ? "FREE" : `$${deliveryFee.toFixed(2)}`}
              </Text>
            </View>
            <View className="flex-row justify-between">
              <Text className="text-sm text-gray-500">Tax</Text>
              <Text className="text-sm text-gray-700">${tax.toFixed(2)}</Text>
            </View>
            <View className="h-px bg-gray-100 my-1" />
            <View className="flex-row justify-between">
              <Text className="font-semibold text-gray-900">Total</Text>
              <Text className="font-semibold text-gray-900">${total.toFixed(2)}</Text>
            </View>
          </View>
        </View>
      </ScrollView>

      <View className="px-4 pb-6 bg-white border-t border-gray-100">
        <Pressable
          onPress={() => router.push("/checkout")}
          className="py-4 bg-emerald-500 rounded-xl items-center active:opacity-80"
        >
          <Text className="text-white font-semibold text-base">
            Proceed to Checkout · ${total.toFixed(2)}
          </Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
