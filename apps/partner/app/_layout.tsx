import {
  color, FontAudit, fontAuditEnabled, I18nProvider, UnreachableScreen, useBrandFonts, useKnownCountry, usePushRegistration, useSession, WithTestBanner,
} from "@bhojango/mobile-core";
import Constants from "expo-constants";
import * as Sentry from "@sentry/react-native";
import { useKeepAwake } from "expo-keep-awake";
import * as Notifications from "expo-notifications";
import { Stack, usePathname } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { useKitchen } from "../lib/data";
import { useOrientationLock } from "../lib/layout";

void SplashScreen.preventAutoHideAsync();

// Error reports to Sentry (R19, the free plan), only when the build sets EXPO_PUBLIC_SENTRY_DSN
// (without it: no init, no network).
if (process.env.EXPO_PUBLIC_SENTRY_DSN) {
  Sentry.init({ dsn: process.env.EXPO_PUBLIC_SENTRY_DSN, environment: process.env.EXPO_PUBLIC_APP_ENV || "development", tracesSampleRate: 0 });
}

export default function RootLayout() {
  useKeepAwake(); // a kitchen tablet stays on: new orders must never wait for the screen
  useOrientationLock(); // phones upright, tablets sideways (lib/formFactor.ts)
  const fontsReady = useBrandFonts();
  const status = useSession((s) => s.status);
  const initialize = useSession((s) => s.initialize);
  const failure = useSession((s) => s.failure);
  usePushRegistration(Notifications, Constants.expoConfig?.extra?.eas?.projectId); // R19: after sign-in
  // R20: the languages are the kitchen's country's (Markets locales): the kitchen's country once it
  // has loaded, else the account's; signed out, the phone's region (I18nProvider rule "partner").
  const accountCountry = useSession((s) => s.user?.country);
  const kitchenCountry = useKitchen((s) => s.kitchen?.country);
  useKnownCountry(accountCountry ? kitchenCountry || accountCountry : null);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (fontsReady && status !== "loading") void SplashScreen.hideAsync();
  }, [fontsReady, status]);

  if (!fontsReady || status === "loading") return null;

  return (
    <I18nProvider rule="partner">
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
