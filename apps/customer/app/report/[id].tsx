// Report a problem (B5): which items, what went wrong, a photo if you like.
// Up to the city's limit it's refunded at once to the original payment;
// above it, support looks at it and gets back to you.
import { api, ApiError, Button, color, radius, space, textFont, unwrap, type CoreSchemas } from "@bhojango/mobile-core";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../../lib/icons";
import { uploadPhoto } from "../../lib/upload";

type Order = CoreSchemas["OrderResponse"];
type Outcome = CoreSchemas["ProblemOut"];
const REASONS = [
  { key: "missing_item", label: "Missing" },
  { key: "wrong_item", label: "Wrong item" },
  { key: "quality", label: "Not good" },
  { key: "damaged_in_transit", label: "Spilled or damaged" },
  { key: "late", label: "Very late" },
] as const;
type Reason = (typeof REASONS)[number]["key"];

export default function Report() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [pick, setPick] = useState<Record<string, number>>({});
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<{ uri: string; key: string | null } | null>(null);
  const [busy, setBusy] = useState<"photo" | "send" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Outcome | null>(null);

  useEffect(() => {
    let live = true;
    api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
      .then((r) => live && setOrder(unwrap(r))).catch(() => live && setError("We couldn't load this order."));
    return () => {
      live = false;
    };
  }, [id]);

  async function addPhoto() {
    setError(null);
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    const shot = perm.granted
      ? await ImagePicker.launchCameraAsync({ quality: 0.6 })
      : await ImagePicker.launchImageLibraryAsync({ quality: 0.6, mediaTypes: ["images"] });
    if (shot.canceled || !shot.assets[0]) return;
    const a = shot.assets[0];
    setPhoto({ uri: a.uri, key: null });
    setBusy("photo");
    try {
      setPhoto({ uri: a.uri, key: await uploadPhoto(a.uri, a.mimeType ?? "image/jpeg") });
    } catch (e) {
      setPhoto(null);
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function send() {
    if (!reason) return;
    setBusy("send");
    setError(null);
    try {
      const items = Object.entries(pick).filter(([, n]) => n > 0).map(([menu_item_id, quantity]) => ({ menu_item_id, quantity }));
      setDone(unwrap(await api.core.POST("/api/v1/orders/{order_id}/problems", {
        params: { path: { order_id: id } }, body: { items, reason, note: note.trim() || null, photo_key: photo?.key ?? null },
      })));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send your report. Try again.");
    } finally {
      setBusy(null);
    }
  }

  if (done) {
    const sym = done.currency === "INR" ? "₹" : "$";
    return (
      <SafeAreaView style={[s.screen, { justifyContent: "center", gap: space[4] }]}>
        <Text accessibilityRole="header" style={s.h1}>{done.outcome === "refunded" ? "Refunded" : "Sent to support"}</Text>
        <Text style={[textFont("400"), { fontSize: 17, lineHeight: 25, color: color.kohl }]}>{done.message}</Text>
        {done.outcome === "ticket" ? <Text style={s.muted}>Refunds above {sym}{Number(done.limit).toFixed(0)} on one order are checked by a person first.</Text> : null}
        <Button title="Back to your order" size="lg" onPress={() => router.replace(`/order/${id}`)} />
      </SafeAreaView>
    );
  }

  const items = (order?.items ?? []) as { menu_item_id: string; name: string; quantity: number }[];
  const chosen = Object.values(pick).some((n) => n > 0);
  return (
    <SafeAreaView edges={["top", "left", "right"]} style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={s.bar}>
        <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => (router.canGoBack() ? router.back() : router.replace(`/order/${id}`))} style={s.back}>
          <Icon name="back" />
        </Pressable>
        <Text accessibilityRole="header" style={[textFont("800"), { fontSize: 18 }]}>Report a problem</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[5], paddingBottom: 140 }} keyboardShouldPersistTaps="handled">
        <View style={s.card}>
          <Text style={s.h2}>Which items?</Text>
          {items.map((i) => {
            const n = pick[i.menu_item_id] ?? 0;
            const set = (v: number) => setPick((p) => ({ ...p, [i.menu_item_id]: Math.max(0, Math.min(i.quantity, v)) }));
            return (
              <View key={i.menu_item_id} style={s.row}>
                <Text style={[textFont("700"), { flex: 1, fontSize: 16 }]}>{i.name} <Text style={s.muted}>· {i.quantity} ordered</Text></Text>
                <Pressable accessibilityRole="button" accessibilityLabel={`One less ${i.name}`} onPress={() => set(n - 1)} style={s.step}><Text style={s.stepText}>−</Text></Pressable>
                <Text accessibilityLabel={`${n} ${i.name}`} style={[textFont("800"), { width: 28, textAlign: "center", fontSize: 17 }]}>{n}</Text>
                <Pressable accessibilityRole="button" accessibilityLabel={`One more ${i.name}`} onPress={() => set(n + 1)} style={s.step}><Text style={s.stepText}>+</Text></Pressable>
              </View>
            );
          })}
        </View>
        <View style={s.card}>
          <Text style={s.h2}>What went wrong?</Text>
          <View accessibilityRole="radiogroup" style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {REASONS.map((r) => (
              <Pressable key={r.key} accessibilityRole="radio" accessibilityState={{ checked: reason === r.key }} onPress={() => setReason(r.key)}
                style={[s.chip, reason === r.key && { borderColor: color.peacock, backgroundColor: color.peacockMist }]}>
                <Text style={[textFont(reason === r.key ? "800" : "600"), { fontSize: 15 }]}>{r.label}</Text>
              </Pressable>
            ))}
          </View>
          <TextInput testID="problem-note" accessibilityLabel="Tell us more (optional)" value={note} onChangeText={setNote} maxLength={300}
            placeholder="Tell us more (optional)" placeholderTextColor={color.muted} style={[textFont("600"), s.input]} />
        </View>
        <View style={s.card}>
          <Text style={s.h2}>A photo helps (optional)</Text>
          <Pressable accessibilityRole="button" onPress={addPhoto} style={s.photo}>
            {photo ? <Image source={{ uri: photo.uri }} style={StyleSheet.absoluteFill} resizeMode="cover" /> : null}
            {busy === "photo" ? <Text style={s.muted}>Uploading…</Text> : photo ? null : <Text style={[textFont("700"), { color: color.peacockDeep }]}>Add a photo</Text>}
          </Pressable>
        </View>
        {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
      </ScrollView>
      <View style={s.footer}>
        <Button title="Send report" size="lg" block loading={busy === "send"} disabled={!chosen || !reason || busy === "photo"} onPress={send} />
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.porcelain, padding: space[5] },
  h1: { ...textFont("800"), fontSize: 28, color: color.kohl },
  h2: { ...textFont("800"), fontSize: 17, color: color.kohl },
  muted: { ...textFont("400"), fontSize: 14, color: color.muted },
  bar: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: space[5], paddingVertical: space[3] },
  back: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: color.white, borderRadius: radius.card, padding: space[4], gap: space[3] },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  step: { width: 40, height: 40, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  stepText: { ...textFont("800"), fontSize: 20, color: color.kohl },
  chip: { paddingHorizontal: 16, height: 44, justifyContent: "center", borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
  input: { height: 52, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 16 },
  photo: { height: 120, borderRadius: radius.card, borderWidth: 1.5, borderStyle: "dashed", borderColor: color.lineStrong, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  footer: { position: "absolute", left: 0, right: 0, bottom: 0, padding: space[5], backgroundColor: color.white, borderTopWidth: 1, borderTopColor: color.line },
});
