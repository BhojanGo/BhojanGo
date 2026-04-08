import { Redirect, Stack } from "expo-router";
import { useAuthStore } from "@/store/auth";

export default function AuthLayout() {
  const { isAuthenticated, isLoading, user } = useAuthStore();

  if (isLoading) return null;
  if (isAuthenticated) {
    if (user?.role === "driver") return <Redirect href="/(driver-tabs)/home" />;
    return <Redirect href="/(tabs)" />;
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="login" />
      <Stack.Screen name="signup" />
    </Stack>
  );
}
