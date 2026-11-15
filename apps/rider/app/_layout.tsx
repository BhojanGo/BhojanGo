import { I18nProvider, useBrandFonts, useKnownCountry, useSession, WithTestBanner } from "@bhojango/mobile-core";
import * as Notifications from "expo-notifications";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { stopTracking } from "../lib/location"; // also defines the background location task at start-up
import { night } from "../lib/theme";

void SplashScreen.preventAutoHideAsync();

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

export default function RootLayout() {
  const fontsReady = useBrandFonts();
  const status = useSession((s) => s.status);
  const initialize = useSession((s) => s.initialize);
  useKnownCountry(useSession((s) => s.user?.country)); // the rider's account country (Markets)

  useEffect(() => {
    void initialize();
  }, [initialize]);

  // Signed out (here, or everywhere from another phone: the API then refuses this
  // phone's token): this phone stops sharing its location.
  useEffect(() => {
    if (status === "signed-out") void stopTracking();
  }, [status]);

  useEffect(() => {
    if (fontsReady && status !== "loading") void SplashScreen.hideAsync();
  }, [fontsReady, status]);

  if (!fontsReady || status === "loading") return null;

  return (
    <I18nProvider>
      <StatusBar style="light" />
      <WithTestBanner tone="dark">
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: night.ground } }}>
          <Stack.Screen name="sos" options={{ presentation: "modal" }} />
          <Stack.Screen name="document" options={{ presentation: "modal" }} />
        </Stack>
      </WithTestBanner>
    </I18nProvider>
  );
}
