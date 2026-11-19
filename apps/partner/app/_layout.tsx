import {
  color, FontAudit, fontAuditEnabled, I18nProvider, UnreachableScreen, useBrandFonts, useKnownCountry, usePushRegistration, useSession, WithTestBanner,
} from "@bhojango/mobile-core";
import Constants from "expo-constants";
import { useKeepAwake } from "expo-keep-awake";
import * as Notifications from "expo-notifications";
import { Stack, usePathname } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { useOrientationLock } from "../lib/layout";

void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  useKeepAwake(); // a kitchen tablet stays on: new orders must never wait for the screen
  useOrientationLock(); // phones upright, tablets sideways (lib/formFactor.ts)
  const fontsReady = useBrandFonts();
  const status = useSession((s) => s.status);
  const initialize = useSession((s) => s.initialize);
  const failure = useSession((s) => s.failure);
  usePushRegistration(Notifications, Constants.expoConfig?.extra?.eas?.projectId); // R19: after sign-in
  useKnownCountry(useSession((s) => s.user?.country)); // the partner's account country (Markets)

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
        {status === "unreachable" ? <UnreachableScreen error={failure} onRetry={initialize} /> : (
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: color.porcelain } }} />
        )}
      </WithTestBanner>
    </I18nProvider>
  );
}
