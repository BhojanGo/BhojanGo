// The onboarding checklist, from Account (after approval it shows everything done).
import { LoadError, SafeAreaView, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";

import { Checklist } from "../lib/checklist";
import { Icon } from "../lib/icons";
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
  return (
    <View style={ui.screen}>
      <SafeAreaView edges={["top"]}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.back()} style={{ width: 44, height: 44, marginLeft: 8, alignItems: "center", justifyContent: "center" }}>
          <Icon name="back" />
        </Pressable>
      </SafeAreaView>
      <View style={{ flex: 1, marginTop: -40 }}>
        <Checklist onboarding={data} onRefresh={() => (data.ready ? router.back() : void reload())} showHeader={false} />
      </View>
    </View>
  );
}
