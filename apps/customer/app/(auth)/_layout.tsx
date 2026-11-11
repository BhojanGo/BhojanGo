import { Redirect, Stack } from "expo-router";
import { useAuthStore } from "@bhojango/mobile-core";

export default function AuthLayout() {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) return null;
  // Riders use the BhojanGo Rider app; in this app every account is a customer.
  if (isAuthenticated) return <Redirect href="/(tabs)" />;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="login" />
      <Stack.Screen name="signup" />
    </Stack>
  );
}
