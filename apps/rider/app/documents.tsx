// The onboarding checklist, from Account (after approval it shows everything done).
import { LoadError, SafeAreaView, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { ActivityIndicator } from "react-native";

import { Checklist } from "../lib/checklist";
import { useOnboarding } from "../lib/rider";
import { night, ui } from "../lib/theme";

export default function Documents() {
  const { data, failure, reload } = useOnboarding();
  const { t } = useI18n();
  useFocusEffect(useCallback(() => void reload(), [reload]));
  if (!data) {
    return (
      <SafeAreaView style={[ui.screen, { alignItems: "center", justifyContent: "center" }]}>
        {failure ? <LoadError error={failure} onRetry={reload} tone="dark" fill style={{ alignSelf: "stretch" }} />
          : <ActivityIndicator accessibilityLabel={t("common.loading")} color={night.kesar} />}
      </SafeAreaView>
    );
  }
  // R26: the Back button sat under the checklist (pulled up by -40) and could be neither seen nor tapped.
  // The checklist now draws the header itself: Back + title, like Payouts.
  return (
    <Checklist onboarding={data} onBack={() => router.back()} title={t("rider.account.documents")}
      onRefresh={() => (data.ready ? router.back() : void reload())} />
  );
}
