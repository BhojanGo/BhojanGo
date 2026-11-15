// "Change city" (round 6): where the food goes, as a full screen (no bottom sheet).
// The saved addresses with a map pin, the phone's location, or a new address. The
// one chosen decides the city on the home's location line, and so the country:
// its currency, its kitchens and the languages on the pill (Markets data).
import { Button, color, space, type, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ScreenBar, Section, ui } from "../lib/account-ui";
import { Icon } from "../lib/icons";
import { useWhere, type DropPoint } from "../lib/where";

export default function Where() {
  const { t } = useI18n();
  const { point, saved, setPoint, goHere } = useWhere();
  const [list, setList] = useState<DropPoint[] | null | "error">(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(() => {
    saved().then(setList).catch(() => setList("error"));
  }, [saved]);
  useFocusEffect(load);

  const done = () => (router.canGoBack() ? router.back() : router.replace("/home"));
  async function go(pick: () => Promise<void>) {
    setBusy(true);
    setProblem(null);
    try {
      await pick();
      done();
    } catch {
      setProblem(t("app.home.locate_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView testID="where-screen" style={ui.screen} edges={["top", "left", "right", "bottom"]}>
      <ScreenBar title={t("cities.choose_title")} fallback="/home" testID="where-title" />
      <ScrollView contentContainerStyle={ui.scroll}>
        <Text style={ui.muted}>{t("cities.choose_note")}</Text>
        <Section title={t("account.addresses.title")} testID="where-saved">
          {list === null ? <ActivityIndicator color={color.peacock} /> : null}
          {list === "error" ? <Text style={ui.muted}>{t("account.addresses.unavailable")}</Text> : null}
          {Array.isArray(list) && !list.length ? <Text style={ui.muted}>{t("account.addresses.empty")}</Text> : null}
          {Array.isArray(list) ? list.map((p, i) => {
            const on = !!point?.addressId && point.addressId === p.addressId;
            return (
              <Pressable key={p.addressId ?? i} testID={`where-address-${i}`} accessibilityRole="button" accessibilityState={{ selected: on }}
                disabled={busy} onPress={() => void go(() => setPoint(p))}
                style={({ pressed }) => [styles.row, i === list.length - 1 && { borderBottomWidth: 0 }, pressed && { opacity: 0.85 }]}>
                <Icon name="pin" size={20} stroke={color.peacock} />
                <View style={{ flex: 1 }}>
                  <Text style={[type.label, { color: color.kohl }]}>{p.label || t("app.home.current_location")}</Text>
                  {p.city ? <Text style={[type.small, { color: color.muted }]}>{[p.city, p.country].filter(Boolean).join(", ")}</Text> : null}
                </View>
                {on ? <Icon name="check" size={18} stroke={color.peacock} /> : null}
              </Pressable>
            );
          }) : null}
        </Section>
        {problem ? <Text accessibilityRole="alert" style={[type.small, { color: color.chili }]}>{problem}</Text> : null}
        <View style={{ gap: space[3] }}>
          <Button testID="where-here" title={t("app.home.use_location")} variant="secondary" block loading={busy} onPress={() => void go(goHere)} />
          <Button testID="where-add" title={t("account.addresses.add")} variant="secondary" block onPress={() => router.push("/account/address")} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 56, borderBottomWidth: 1, borderBottomColor: color.divider },
});
