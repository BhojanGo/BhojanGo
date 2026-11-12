// Sign up to ride: your name and city, then the onboarding checklist (licence,
// insurance, payout account, background check). A number that already orders
// food on BhojanGo can't also ride.
import { api, ApiError, unwrap, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RiderMark } from "../lib/icons";
import { night, radius, space, textFont, ui } from "../lib/theme";

type City = { code: string; name: string; region: string; country: string };

export default function Join() {
  const adopt = useSession((s) => s.adopt);
  const signOut = useSession((s) => s.signOut);
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
    }).catch(() => setError("Can't load the cities right now."));
  }, []);

  async function apply() {
    if (!city) return;
    setBusy(true);
    setError(null);
    try {
      const t = unwrap(await api.core.POST("/api/v1/riders/apply", { body: { full_name: name.trim(), city_code: city } }));
      await adopt(t as { access_token: string; refresh_token: string });
      router.replace("/drive");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't sign you up. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const ok = name.trim().split(/\s+/).length >= 2 && !!city && !busy;
  return (
    <SafeAreaView style={ui.screen}>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><RiderMark /><Text style={[ui.bold, { fontSize: 15 }]}>BhojanGo Rider</Text></View>
        <Text accessibilityRole="header" style={[ui.h1, { marginTop: 24 }]}>Sign up to ride</Text>
        <Text style={[ui.body, { color: night.muted }]}>Full pay shown before you accept, tips stay 100% yours, and an hourly floor in every city. Next: a few documents.</Text>
        <Text style={[ui.bold, { fontSize: 14 }]}>Your full name</Text>
        <TextInput testID="name" accessibilityLabel="Your full name" value={name} onChangeText={setName} autoCapitalize="words"
          placeholder="As on your licence" placeholderTextColor={night.muted} style={[textFont("600"), s.input]} />
        <Text style={[ui.bold, { fontSize: 14 }]}>Where you&apos;ll ride</Text>
        <View style={{ gap: 8 }}>
          {cities.map((c) => (
            <Pressable key={c.code} accessibilityRole="radio" accessibilityState={{ checked: city === c.code }} accessibilityLabel={c.name}
              onPress={() => setCity(c.code)} style={[s.city, city === c.code && { borderColor: night.kesar }]}>
              <Text style={[ui.bold, { fontSize: 16 }]}>{c.name}</Text>
              <Text style={ui.muted}>{c.region}</Text>
            </Pressable>
          ))}
        </View>
        {error ? <Text style={[textFont("600"), { color: night.sosText }]}>{error}</Text> : null}
        <Pressable accessibilityRole="button" disabled={!ok} onPress={apply} style={[ui.cta, { opacity: ok ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? "Signing you up…" : "Continue"}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={async () => { await signOut(); router.replace("/sign-in"); }}>
          <Text style={[ui.muted, { textAlign: "center" }]}>Use another number</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, paddingHorizontal: space[4], fontSize: 17,
    color: night.text, backgroundColor: night.surface },
  city: { padding: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, backgroundColor: night.surface },
});
