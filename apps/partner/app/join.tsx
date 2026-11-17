// Apply with a kitchen (B1): your name, the kitchen, where it is. The kitchen is
// created pending approval and the partner application (FSSAI, GST and bank,
// menu) follows. BhojanGo checks it and switches the kitchen on.
import { api, ApiError, field as input, LoadError, SafeAreaView, type, unwrap, useFirstLoad, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { useKitchen } from "../lib/data";
import { useLayout } from "../lib/layout";
import { Btn, color, radius, t } from "../lib/ui";

type City = { code: string; name: string; region: string; country: string; lat: number; lng: number };

export default function Join() {
  const adopt = useSession((s) => s.adopt);
  const signOut = useSession((s) => s.signOut);
  const load = useKitchen((s) => s.load);
  const { t: tr } = useI18n();
  const { narrow } = useLayout();
  // Markets' cities (R9: a spinner while they load, the error and Retry if they can't).
  const cityList = useFirstLoad(async () => unwrap(await api.core.GET("/api/v1/markets/cities")) as City[], []);
  const cities = cityList.data ?? [];
  const [picked, setCity] = useState<City | null>(null);
  const city = picked ?? cities[0] ?? null;
  const [f, setF] = useState({ full_name: "", kitchen_name: "", street: "", area: "", zip: "", cuisines: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (v: string) => setF((x) => ({ ...x, [k]: v }));

  async function apply() {
    if (!city) return;
    setBusy(true);
    setError(null);
    try {
      const body = {
        full_name: f.full_name.trim(), kitchen_name: f.kitchen_name.trim(), city_code: city.code, street: f.street.trim(), area: f.area.trim(),
        zip: f.zip.trim(), cuisines: f.cuisines.split(",").map((c) => c.trim()).filter(Boolean),
        // The tablet has no GPS: the city centre stands in until we check the pin with you.
        lat: city.lat, lng: city.lng,
      };
      const r = unwrap(await api.core.POST("/api/v1/restaurants/apply", { body }));
      await adopt(r as { access_token: string; refresh_token: string });
      await load();
      router.replace("/apply");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : tr("partner.join.failed"));
    } finally {
      setBusy(false);
    }
  }

  const ok = f.full_name.trim().length > 2 && f.kitchen_name.trim().length > 1 && f.street.trim().length > 2 && f.area.trim().length > 1
    && f.zip.trim().length > 2 && f.cuisines.trim().length > 1 && !!city && !busy;
  const field = (k: keyof typeof f, label: string, hint: string, props: object = {}) => (
    <View style={{ flex: 1, minWidth: narrow ? 200 : 240, gap: 6 }}>
      <Text style={t.label}>{label}</Text>
      <TextInput disableFullscreenUI testID={k} accessibilityLabel={label} value={f[k]} onChangeText={set(k)} placeholder={hint} placeholderTextColor={color.muted}
        style={[input.bodyLg, s.input]} {...props} />
    </View>
  );
  return (
    <SafeAreaView edges={["left", "right", "top"]} style={{ flex: 1, backgroundColor: color.porcelain }}>
      <ScrollView contentContainerStyle={{ padding: narrow ? 20 : 32, gap: 16, maxWidth: 900, alignSelf: "center", width: "100%" }}>
        <Text accessibilityRole="header" style={t.big}>{tr("partner.join.title")}</Text>
        <Text style={t.muted}>{tr("partner.join.sub")}</Text>
        <View style={s.row}>{field("full_name", tr("partner.join.name"), tr("partner.join.name_hint"))}{field("kitchen_name", tr("partner.join.kitchen"), tr("partner.join.kitchen_hint"))}</View>
        <Text style={t.label}>{tr("partner.join.city")}</Text>
        {cityList.status === "error" && !cities.length ? <LoadError error={cityList.error} onRetry={cityList.retry} title={tr("partner.join.cities_failed")} /> : null}
        {cityList.status === "loading" && !cities.length ? <ActivityIndicator accessibilityLabel={tr("common.loading")} color={color.peacock} /> : null}
        <View style={s.row}>
          {cities.map((c) => (
            <Pressable key={c.code} accessibilityRole="radio" accessibilityState={{ checked: city?.code === c.code }} accessibilityLabel={c.name}
              onPress={() => setCity(c)} style={[s.city, city?.code === c.code && { borderColor: color.peacock, backgroundColor: color.peacockMist }]}>
              <Text style={t.title}>{c.name}</Text><Text style={t.muted}>{c.region}</Text>
            </Pressable>
          ))}
        </View>
        <View style={s.row}>{field("street", tr("partner.join.street"), tr("partner.join.street_hint"))}{field("area", tr("partner.join.area"), tr("partner.join.area_hint"))}</View>
        <View style={s.row}>{field("zip", tr("partner.join.zip"), tr("partner.join.zip_hint"), { keyboardType: "number-pad" })}{field("cuisines", tr("partner.join.cuisines"), tr("partner.join.cuisines_hint"))}</View>
        {error ? <Text style={[type.small, { color: color.chili }]}>{error}</Text> : null}
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12, justifyContent: "flex-end" }}>
          <Btn title={tr("partner.join.another_number")} onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
          <Btn testID="send-application" title={tr("partner.join.send")} kind="primary" height={56} busy={busy} disabled={!ok} onPress={apply} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 16 },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, backgroundColor: color.white },
  city: { flex: 1, minWidth: 180, padding: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
});
