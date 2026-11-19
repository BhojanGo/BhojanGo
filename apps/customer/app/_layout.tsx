import {
  color, FontAudit, fontAuditEnabled, I18nProvider, UnreachableScreen, useBrandFonts, useKnownCountry, usePushRegistration, useSession, WithTestBanner,
} from "@bhojango/mobile-core";
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Stack, usePathname } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { PauseBanner } from "../components/PauseBanner";
import { useWhere } from "../lib/where";

void SplashScreen.preventAutoHideAsync();

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

export default function RootLayout() {
  const fontsReady = useBrandFonts();
  const status = useSession((s) => s.status);
  const initialize = useSession((s) => s.initialize);
  const failure = useSession((s) => s.failure);
  usePushRegistration(Notifications, Constants.expoConfig?.extra?.eas?.projectId); // R19: after sign-in
  // The country (as on the website, no country selector): the delivery address's
  // (its Markets city's country, else the address's own), else the IP hint, else
  // the phone's region (detectCountry, in the locale store).
  const addressCountry = useWhere((s) => s.market?.country_code || s.point?.country);
  useKnownCountry(addressCountry);

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
        {/* Signed in, but the API didn't answer at start: say so, Retry (the person stays signed in). */}
        {status === "unreachable" ? null : <PauseBanner />}
        {status === "unreachable" ? <UnreachableScreen error={failure} onRetry={initialize} /> : (
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: color.porcelain } }}>
            <Stack.Screen name="item" options={{ presentation: "modal" }} />
          </Stack>
        )}
      </WithTestBanner>
    </I18nProvider>
  );
}
