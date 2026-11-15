import { color, I18nProvider, useBrandFonts, useKnownCountry, useSession, WithTestBanner } from "@bhojango/mobile-core";
import * as Notifications from "expo-notifications";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { useWhere } from "../lib/where";

void SplashScreen.preventAutoHideAsync();

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

export default function RootLayout() {
  const fontsReady = useBrandFonts();
  const status = useSession((s) => s.status);
  const initialize = useSession((s) => s.initialize);
  // The country: the delivery address's, else the account's (then a stored choice or the phone's region).
  const addressCountry = useWhere((s) => s.point?.country);
  const accountCountry = useSession((s) => s.user?.country);
  useKnownCountry(addressCountry || accountCountry);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (fontsReady && status !== "loading") void SplashScreen.hideAsync();
  }, [fontsReady, status]);

  if (!fontsReady || status === "loading") return null;

  return (
    <I18nProvider>
      <StatusBar style="dark" />
      <WithTestBanner>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: color.porcelain } }}>
          <Stack.Screen name="item" options={{ presentation: "modal" }} />
        </Stack>
      </WithTestBanner>
    </I18nProvider>
  );
}
