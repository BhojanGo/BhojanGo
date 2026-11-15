import {
  color, FontAudit, fontAuditEnabled, I18nProvider, regionOf, useBrandFonts, useKnownCountry, useLocaleStore, useSession,
  WithTestBanner,
} from "@bhojango/mobile-core";
import * as Notifications from "expo-notifications";
import { Stack, usePathname } from "expo-router";
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
  // The country (as on the website): the delivery address's, else the one chosen
  // on this phone, else the phone's region when it's a Markets country; the
  // account's country only when none of those says anything.
  const addressCountry = useWhere((s) => s.point?.country);
  const accountCountry = useSession((s) => s.user?.country);
  const chosen = useLocaleStore((s) => s.chosenCountry);
  const deviceKnown = useLocaleStore((s) => {
    const region = regionOf(s.device);
    return !!region && s.countries.some((c) => c.code.toUpperCase() === region);
  });
  useKnownCountry(addressCountry || (chosen || deviceKnown ? null : accountCountry));

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
      {fontAuditEnabled ? <FontAudit usePathname={usePathname} /> : null}
      <WithTestBanner>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: color.porcelain } }}>
          <Stack.Screen name="item" options={{ presentation: "modal" }} />
        </Stack>
      </WithTestBanner>
    </I18nProvider>
  );
}
