import { useState } from "react";
import { Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useCartStore } from "@/store/cart";

type PaymentMethod = "card" | "wallet" | "upi" | "cash_on_delivery";

const PAYMENT_OPTIONS: { value: PaymentMethod; label: string }[] = [
  { value: "card", label: "Credit / Debit Card" },
  { value: "wallet", label: "BhojanGo Wallet" },
  { value: "upi", label: "UPI" },
  { value: "cash_on_delivery", label: "Cash on Delivery" },
];

export default function CheckoutScreen() {
  const user = useAuthStore((s) => s.user);
  const { items, restaurantId, restaurantName, deliveryFee, getSubtotal, clearCart } =
    useCartStore();

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("card");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressState, setAddressState] = useState("");
  const [addressPostal, setAddressPostal] = useState("");
  const [specialInstructions, setSpecialInstructions] = useState("");
  const [tip, setTip] = useState(0);
  const [loading, setLoading] = useState(false);

  const subtotal = getSubtotal();
  const taxRate = user?.country === "IN" ? 0.18 : 0.08;
  const taxes = Math.round(subtotal * taxRate * 100) / 100;
  const total = Math.round((subtotal + deliveryFee + taxes + tip) * 100) / 100;
  const currencySymbol = user?.preferred_currency === "INR" ? "\u20B9" : "$";

  const isAddressValid = addressStreet.trim().length > 0 && addressCity.trim().length > 0;

  const placeOrder = async () => {
    if (!isAddressValid) {
      Alert.alert("Missing Address", "Please enter your delivery address.");
      return;
    }
    if (!restaurantId || items.length === 0) {
      Alert.alert("Empty Cart", "Your cart is empty.");
      return;
    }

    setLoading(true);
    try {
      const orderPayload = {
        restaurant_id: restaurantId,
        items: items.map((item) => ({
          menu_item_id: item.menuItemId,
          quantity: item.quantity,
          customizations: [],
        })),
        delivery_address: {
          street: addressStreet.trim(),
          city: addressCity.trim(),
          state: addressState.trim(),
          postal_code: addressPostal.trim(),
          country: user?.country || "US",
        },
        payment_method: paymentMethod,
        special_instructions: specialInstructions.trim() || undefined,
        tip,
        loyalty_points_to_use: 0,
      };

      const res = await api.post("/order/orders", orderPayload, {
        headers: { "X-Idempotency-Key": crypto.randomUUID() },
      });

      const order = res.data;
      clearCart();
      router.replace(`/order/${order.id}`);
    } catch (e: any) {
      const msg = e?.response?.data?.detail?.message || e?.response?.data?.detail || "Failed to place order. Please try again.";
      Alert.alert("Order Failed", msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-gray-50" edges={["bottom"]}>
      <ScrollView className="flex-1" keyboardShouldPersistTaps="handled">
        {/* Restaurant */}
        <View className="bg-white px-4 py-3 mb-2">
          <Text className="text-xs text-gray-500 uppercase font-semibold">Ordering from</Text>
          <Text className="text-base font-semibold text-gray-900 mt-1">{restaurantName}</Text>
        </View>

        {/* Delivery Address */}
        <View className="bg-white px-4 py-4 mb-2">
          <Text className="text-sm font-semibold text-gray-900 mb-3">Delivery Address</Text>
          <TextInput
            placeholder="Street address *"
            value={addressStreet}
            onChangeText={setAddressStreet}
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm mb-2"
          />
          <View className="flex-row gap-2">
            <TextInput
              placeholder="City *"
              value={addressCity}
              onChangeText={setAddressCity}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2.5 text-sm"
            />
            <TextInput
              placeholder="State"
              value={addressState}
              onChangeText={setAddressState}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2.5 text-sm"
            />
          </View>
          <TextInput
            placeholder="Postal code"
            value={addressPostal}
            onChangeText={setAddressPostal}
            keyboardType="number-pad"
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm mt-2"
          />
        </View>

        {/* Special Instructions */}
        <View className="bg-white px-4 py-4 mb-2">
          <Text className="text-sm font-semibold text-gray-900 mb-2">Special Instructions</Text>
          <TextInput
            placeholder="Any notes for the restaurant? (optional)"
            value={specialInstructions}
            onChangeText={setSpecialInstructions}
            multiline
            numberOfLines={2}
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm"
          />
        </View>

        {/* Payment Method */}
        <View className="bg-white px-4 py-4 mb-2">
          <Text className="text-sm font-semibold text-gray-900 mb-3">Payment Method</Text>
          {PAYMENT_OPTIONS.map((opt) => (
            <Pressable
              key={opt.value}
              onPress={() => setPaymentMethod(opt.value)}
              className="flex-row items-center py-3 border-b border-gray-100"
            >
              <View
                className={`w-5 h-5 rounded-full border-2 mr-3 items-center justify-center ${
                  paymentMethod === opt.value ? "border-emerald-600" : "border-gray-300"
                }`}
              >
                {paymentMethod === opt.value && (
                  <View className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
                )}
              </View>
              <Text className="text-sm text-gray-800">{opt.label}</Text>
            </Pressable>
          ))}
        </View>

        {/* Tip */}
        <View className="bg-white px-4 py-4 mb-2">
          <Text className="text-sm font-semibold text-gray-900 mb-3">Tip for Delivery Partner</Text>
          <View className="flex-row gap-2">
            {[0, 10, 20, 50].map((amount) => (
              <Pressable
                key={amount}
                onPress={() => setTip(amount)}
                className={`flex-1 py-2 rounded-lg items-center ${
                  tip === amount ? "bg-emerald-600" : "bg-gray-100"
                }`}
              >
                <Text className={`text-sm font-medium ${tip === amount ? "text-white" : "text-gray-700"}`}>
                  {amount === 0 ? "No tip" : `${currencySymbol}${amount}`}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Order Summary */}
        <View className="bg-white px-4 py-4 mb-6">
          <Text className="text-sm font-semibold text-gray-900 mb-3">Order Summary</Text>
          {items.map((item) => (
            <View key={item.menuItemId} className="flex-row justify-between py-1">
              <Text className="text-sm text-gray-600">
                {item.name} x{item.quantity}
              </Text>
              <Text className="text-sm text-gray-800">
                {currencySymbol}{(item.price * item.quantity).toFixed(2)}
              </Text>
            </View>
          ))}
          <View className="h-px bg-gray-100 my-2" />
          <View className="flex-row justify-between py-1">
            <Text className="text-sm text-gray-500">Subtotal</Text>
            <Text className="text-sm text-gray-700">{currencySymbol}{subtotal.toFixed(2)}</Text>
          </View>
          <View className="flex-row justify-between py-1">
            <Text className="text-sm text-gray-500">Delivery Fee</Text>
            <Text className="text-sm text-gray-700">
              {deliveryFee === 0 ? "FREE" : `${currencySymbol}${deliveryFee.toFixed(2)}`}
            </Text>
          </View>
          <View className="flex-row justify-between py-1">
            <Text className="text-sm text-gray-500">Taxes ({Math.round(taxRate * 100)}%)</Text>
            <Text className="text-sm text-gray-700">{currencySymbol}{taxes.toFixed(2)}</Text>
          </View>
          {tip > 0 && (
            <View className="flex-row justify-between py-1">
              <Text className="text-sm text-gray-500">Tip</Text>
              <Text className="text-sm text-gray-700">{currencySymbol}{tip.toFixed(2)}</Text>
            </View>
          )}
          <View className="h-px bg-gray-100 my-2" />
          <View className="flex-row justify-between py-1">
            <Text className="font-semibold text-gray-900">Total</Text>
            <Text className="font-semibold text-emerald-700">{currencySymbol}{total.toFixed(2)}</Text>
          </View>
        </View>
      </ScrollView>

      {/* Place Order Button */}
      <View className="px-4 pb-6 bg-white border-t border-gray-100">
        <Pressable
          onPress={placeOrder}
          disabled={loading || !isAddressValid}
          className={`py-4 rounded-xl items-center ${
            loading || !isAddressValid ? "bg-gray-300" : "bg-emerald-600 active:opacity-80"
          }`}
        >
          <Text className="text-white font-semibold text-base">
            {loading ? "Placing Order..." : `Place Order \u00B7 ${currencySymbol}${total.toFixed(2)}`}
          </Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
