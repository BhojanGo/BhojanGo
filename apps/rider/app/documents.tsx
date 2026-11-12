// The onboarding checklist, from Account (after approval it shows everything done).
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Checklist } from "../lib/checklist";
import { Icon } from "../lib/icons";
import { useOnboarding } from "../lib/rider";
import { night, ui } from "../lib/theme";

export default function Documents() {
  const { data, error, reload } = useOnboarding();
  useFocusEffect(useCallback(() => void reload(), [reload]));
  if (!data) {
    return <SafeAreaView style={[ui.screen, { alignItems: "center", justifyContent: "center" }]}>{error ? <Text style={ui.body}>{error}</Text> : <ActivityIndicator color={night.kesar} />}</SafeAreaView>;
  }
  return (
    <View style={ui.screen}>
      <SafeAreaView edges={["top"]}>
        <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={{ width: 44, height: 44, marginLeft: 8, alignItems: "center", justifyContent: "center" }}>
          <Icon name="back" />
        </Pressable>
      </SafeAreaView>
      <View style={{ flex: 1, marginTop: -40 }}>
        <Checklist onboarding={data} onRefresh={() => (data.ready ? router.back() : void reload())} showHeader={false} />
      </View>
    </View>
  );
}
