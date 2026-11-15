// Sign up to ride: your name and city, then the onboarding checklist (licence,
// insurance, payout account, background check). A number that already orders
// food on BhojanGo can't also ride.
import { api, ApiError, field, type, unwrap, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RiderMark } from "../lib/icons";
import { night, radius, space, ui } from "../lib/theme";

type City = { code: string; name: string; region: string; country: string };

export default function Join() {
  const adopt = useSession((s) => s.adopt);
  const signOut = useSession((s) => s.signOut);
  const { t } = useI18n();
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.core.GET("/api/v1/markets/cities").then((r) => {
      const list = unwrap(r) as City[];
      setCities(list);
      setCity((c) => c ?? list[0]?.code ?? null);
    }).catch(() => setError(t("rider.join.cities_failed")));
  }, [t]);

  async function apply() {
    if (!city) return;
    setBusy(true);
    setError(null);
    try {
      const tokens = unwrap(await api.core.POST("/api/v1/riders/apply", { body: { full_name: name.trim(), city_code: city } }));
      await adopt(tokens as { access_token: string; refresh_token: string });
      router.replace("/drive");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("rider.join.failed"));
    } finally {
      setBusy(false);
    }
  }

  const ok = name.trim().split(/\s+/).length >= 2 && !!city && !busy;
  return (
    <SafeAreaView testID="join-screen" style={ui.screen}>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><RiderMark /><Text style={ui.bold}>{t("rider.brand")}</Text></View>
        <Text accessibilityRole="header" style={[ui.h1, { marginTop: 24 }]}>{t("rider.join.title")}</Text>
        <Text style={[ui.body, { color: night.muted }]}>{t("rider.join.sub")}</Text>
        <Text style={ui.bold}>{t("rider.join.name")}</Text>
        <TextInput testID="name" accessibilityLabel={t("rider.join.name")} value={name} onChangeText={setName} autoCapitalize="words"
          placeholder={t("rider.join.name_hint")} placeholderTextColor={night.muted} style={[field.bodyLg, s.input]} />
        <Text style={ui.bold}>{t("rider.join.city")}</Text>
        <View style={{ gap: 8 }}>
          {cities.map((c) => (
            <Pressable key={c.code} accessibilityRole="radio" accessibilityState={{ checked: city === c.code }} accessibilityLabel={c.name}
              onPress={() => setCity(c.code)} style={[s.city, city === c.code && { borderColor: night.kesar }]}>
              <Text style={ui.bold}>{c.name}</Text>
              <Text style={ui.muted}>{c.region}</Text>
            </Pressable>
          ))}
        </View>
        {error ? <Text style={[type.small, { color: night.sosText }]}>{error}</Text> : null}
        <Pressable testID="join-continue" accessibilityRole="button" disabled={!ok} onPress={apply} style={[ui.cta, { opacity: ok ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? t("rider.join.signing_up") : t("rider.join.continue")}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={async () => { await signOut(); router.replace("/sign-in"); }}>
          <Text style={[ui.muted, { textAlign: "center" }]}>{t("rider.join.another_number")}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, paddingHorizontal: space[4],
    color: night.text, backgroundColor: night.surface },
  city: { padding: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, backgroundColor: night.surface },
});
