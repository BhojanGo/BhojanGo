// Apply with a kitchen (B1): your name, the kitchen, where it is. The kitchen is
// created pending approval and the partner application (FSSAI, GST and bank,
// menu) follows. BhojanGo checks it and switches the kitchen on.
import { api, ApiError, unwrap, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useKitchen } from "../lib/data";
import { Btn, color, radius, t, textFont } from "../lib/ui";

type City = { code: string; name: string; region: string; country: string; lat: number; lng: number };

export default function Join() {
  const adopt = useSession((s) => s.adopt);
  const signOut = useSession((s) => s.signOut);
  const load = useKitchen((s) => s.load);
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState<City | null>(null);
  const [f, setF] = useState({ full_name: "", kitchen_name: "", street: "", area: "", zip: "", cuisines: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.core.GET("/api/v1/markets/cities").then((r) => {
      const list = unwrap(r) as City[];
      setCities(list);
      setCity((c) => c ?? list[0] ?? null);
    }).catch(() => setError("Can't load the cities right now."));
  }, []);
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
      setError(e instanceof ApiError ? e.message : "Couldn't send your application. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const ok = f.full_name.trim().length > 2 && f.kitchen_name.trim().length > 1 && f.street.trim().length > 2 && f.area.trim().length > 1
    && f.zip.trim().length > 2 && f.cuisines.trim().length > 1 && !!city && !busy;
  const field = (k: keyof typeof f, label: string, hint: string, props: object = {}) => (
    <View style={{ flex: 1, gap: 6 }}>
      <Text style={t.label}>{label}</Text>
      <TextInput testID={k} accessibilityLabel={label} value={f[k]} onChangeText={set(k)} placeholder={hint} placeholderTextColor={color.muted}
        style={[textFont("600"), s.input]} {...props} />
    </View>
  );
  return (
    <SafeAreaView edges={["left", "right", "top"]} style={{ flex: 1, backgroundColor: color.porcelain }}>
      <ScrollView contentContainerStyle={{ padding: 32, gap: 16, maxWidth: 900, alignSelf: "center", width: "100%" }}>
        <Text accessibilityRole="header" style={t.big}>Apply with your kitchen</Text>
        <Text style={t.muted}>Commission on food only, paid out weekly; you set your own prices and offers. Your terms show on the next screen. Next: your FSSAI licence, GST and bank.</Text>
        <View style={s.row}>{field("full_name", "Your name", "Owner or manager")}{field("kitchen_name", "Kitchen name", "As customers will see it")}</View>
        <Text style={t.label}>City</Text>
        <View style={s.row}>
          {cities.map((c) => (
            <Pressable key={c.code} accessibilityRole="radio" accessibilityState={{ checked: city?.code === c.code }} accessibilityLabel={c.name}
              onPress={() => setCity(c)} style={[s.city, city?.code === c.code && { borderColor: color.peacock, backgroundColor: color.peacockMist }]}>
              <Text style={t.title}>{c.name}</Text><Text style={t.muted}>{c.region}</Text>
            </Pressable>
          ))}
        </View>
        <View style={s.row}>{field("street", "Street address", "Plot, building and road")}{field("area", "Area", "e.g. Banjara Hills")}</View>
        <View style={s.row}>{field("zip", "PIN / ZIP code", "500034", { keyboardType: "number-pad" })}{field("cuisines", "Cuisines", "Separate with commas: Andhra, Thali")}</View>
        {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
        <View style={{ flexDirection: "row", gap: 12, justifyContent: "flex-end" }}>
          <Btn title="Use another number" onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
          <Btn title="Send application" kind="primary" height={56} busy={busy} disabled={!ok} onPress={apply} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: "row", gap: 16 },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 17, backgroundColor: color.white },
  city: { flex: 1, padding: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
});
