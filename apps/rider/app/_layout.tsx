import { useBrandFonts, useSession } from "@bhojango/mobile-core";
import * as Notifications from "expo-notifications";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import "../lib/location"; // defines the background location task at start-up
import { night } from "../lib/theme";

void SplashScreen.preventAutoHideAsync();

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

export default function RootLayout() {
  const fontsReady = useBrandFonts();
  const status = useSession((s) => s.status);
  const initialize = useSession((s) => s.initialize);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (fontsReady && status !== "loading") void SplashScreen.hideAsync();
  }, [fontsReady, status]);

  if (!fontsReady || status === "loading") return null;

  return (
    <>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: night.ground } }}>
        <Stack.Screen name="sos" options={{ presentation: "modal" }} />
        <Stack.Screen name="document" options={{ presentation: "modal" }} />
      </Stack>
    </>
  );
}
