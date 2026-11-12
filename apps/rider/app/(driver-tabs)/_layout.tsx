import { useEffect } from "react";
import { Redirect, Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuthStore } from "@bhojango/mobile-core";

export default function DriverTabsLayout() {
  const { isAuthenticated, isLoading, user, logout } = useAuthStore();
  // `user` is only known after a fresh login (the store does not refetch it on
  // app start), so only sign out when we know the account is not a rider.
  const notRider = user != null && user.role !== "driver";

  useEffect(() => {
    if (notRider) void logout();
  }, [notRider, logout]);

  if (isLoading) return null;
  if (!isAuthenticated || notRider) return <Redirect href="/(auth)/login" />;

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: "#059669",
        tabBarInactiveTintColor: "#6B7280",
        headerShown: false,
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color as string} />,
        }}
      />
      <Tabs.Screen
        name="active"
        options={{
          title: "Active",
          tabBarIcon: ({ color, size }) => <Ionicons name="navigate" size={size} color={color as string} />,
        }}
      />
      <Tabs.Screen
        name="earnings"
        options={{
          title: "Earnings",
          tabBarIcon: ({ color, size }) => <Ionicons name="wallet" size={size} color={color as string} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => <Ionicons name="person" size={size} color={color as string} />,
        }}
      />
    </Tabs>
  );
}
