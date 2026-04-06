import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuthStore } from "@/store/auth";
import { useCartStore } from "@/store/cart";

interface MenuRow {
  icon: string;
  label: string;
  onPress: () => void;
  danger?: boolean;
}

export default function ProfileScreen() {
  const { user, logout } = useAuthStore();
  const clearCart = useCartStore((s) => s.clearCart);

  function handleLogout() {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign Out",
        style: "destructive",
        onPress: async () => {
          clearCart();
          await logout();
          router.replace("/(auth)/login");
        },
      },
    ]);
  }

  const menuItems: MenuRow[] = [
    { icon: "📋", label: "My Orders", onPress: () => router.push("/orders") },
    { icon: "👛", label: "Wallet", onPress: () => router.push("/wallet") },
    { icon: "📍", label: "Saved Addresses", onPress: () => {} },
    { icon: "🔔", label: "Notifications", onPress: () => {} },
    { icon: "🌐", label: "Language & Region", onPress: () => {} },
    { icon: "🔒", label: "Privacy & Security", onPress: () => {} },
    { icon: "❓", label: "Help & Support", onPress: () => {} },
    { icon: "🚪", label: "Sign Out", onPress: handleLogout, danger: true },
  ];

  return (
    <SafeAreaView className="flex-1 bg-gray-50">
      <ScrollView>
        {/* Header */}
        <View className="bg-white px-4 py-5 mb-4">
          <View className="flex-row items-center gap-4">
            <View className="w-16 h-16 rounded-full bg-emerald-100 items-center justify-center">
              <Text className="text-emerald-700 text-2xl font-bold">
                {user?.full_name?.[0]?.toUpperCase() ?? "?"}
              </Text>
            </View>
            <View>
              <Text className="text-lg font-bold text-gray-900">{user?.full_name}</Text>
              <Text className="text-sm text-gray-500">{user?.email}</Text>
              {user?.phone && <Text className="text-xs text-gray-400 mt-0.5">{user.phone}</Text>}
            </View>
          </View>
        </View>

        {/* Loyalty points */}
        {user?.loyalty_points !== undefined && user.loyalty_points > 0 && (
          <View className="mx-4 mb-4 bg-gradient-to-r from-emerald-500 to-emerald-700 rounded-xl p-4 flex-row items-center justify-between">
            <View>
              <Text className="text-white text-xs">Loyalty Points</Text>
              <Text className="text-white text-2xl font-bold">{user.loyalty_points}</Text>
            </View>
            <Text className="text-3xl">🏆</Text>
          </View>
        )}

        {/* Menu */}
        <View className="bg-white rounded-xl mx-4 overflow-hidden">
          {menuItems.map((item, index) => (
            <Pressable
              key={item.label}
              onPress={item.onPress}
              className={`flex-row items-center px-4 py-4 gap-3 ${
                index < menuItems.length - 1 ? "border-b border-gray-100" : ""
              } active:bg-gray-50`}
            >
              <Text className="text-xl w-8">{item.icon}</Text>
              <Text className={`flex-1 text-sm font-medium ${item.danger ? "text-red-600" : "text-gray-900"}`}>
                {item.label}
              </Text>
              {!item.danger && <Text className="text-gray-400">›</Text>}
            </Pressable>
          ))}
        </View>

        <Text className="text-xs text-gray-400 text-center mt-6 mb-4">
          BhojanGo v1.0.0
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
