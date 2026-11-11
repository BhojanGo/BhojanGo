import { Redirect, Stack } from "expo-router";
import { useAuthStore } from "@bhojango/mobile-core";

export default function AuthLayout() {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) return null;
  if (isAuthenticated) return <Redirect href="/(driver-tabs)/home" />;

  // Riders are onboarded by ops, so there is no sign-up screen in this app.
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="login" />
    </Stack>
  );
}
