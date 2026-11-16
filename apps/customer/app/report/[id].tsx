// Report a problem (B5): which items, what went wrong, a photo if you like.
// Up to the city's limit it's refunded at once to the original payment;
// above it, support looks at it and gets back to you.
import {
  api, ApiError, Button, color, type CoreSchemas, field, LoadError, radius, SafeAreaView, space, textStyles, type, unwrap, useFirstLoad, useI18n,
} from "@bhojango/mobile-core";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { Icon } from "../../lib/icons";
import { uploadPhoto } from "../../lib/upload";

type Order = CoreSchemas["OrderResponse"];
type Outcome = CoreSchemas["ProblemOut"];
const REASONS = ["missing_item", "wrong_item", "quality", "damaged_in_transit", "late"] as const;
type Reason = (typeof REASONS)[number];

export default function Report() {
  const { t, money } = useI18n();
  const { id } = useLocalSearchParams<{ id: string }>();
  // The order's dishes to pick from (R9: loading, and an error with Retry, instead of an empty form).
  const loaded = useFirstLoad(async () => unwrap(await api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })) as Order, [id]);
  const order = loaded.data;
  const [pick, setPick] = useState<Record<string, number>>({});
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<{ uri: string; key: string | null } | null>(null);
  const [busy, setBusy] = useState<"photo" | "send" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Outcome | null>(null);

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
      // A TypeError is fetch's "Network request failed": never shown raw.
      setError((!(e instanceof TypeError) && (e as Error).message) || t("account.report.photo_failed"));
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
      setError(e instanceof ApiError ? e.message : t("account.report.send_failed"));
    } finally {
      setBusy(null);
    }
  }

  if (done) {
    return (
      <SafeAreaView style={[s.screen, { justifyContent: "center", gap: space[4] }]}>
        <Text accessibilityRole="header" style={s.h1}>{done.outcome === "refunded" ? t("account.report.refunded") : t("account.report.ticket")}</Text>
        <Text style={[type.bodyLg, { color: color.kohl }]}>{done.message}</Text>
        {done.outcome === "ticket" ? <Text style={s.muted}>{t("account.report.ticket_note", { amount: money(done.limit, done.currency, { whole: true }) })}</Text> : null}
        <Button testID="back-to-order" title={t("account.report.back_to_order")} size="lg" onPress={() => (router.canGoBack() ? router.back() : router.replace(`/account/receipt/${id}`))} />
      </SafeAreaView>
    );
  }

  const items = (order?.items ?? []) as { menu_item_id: string; name: string; quantity: number }[];
  const chosen = Object.values(pick).some((n) => n > 0);
  return (
    <SafeAreaView edges={["top", "left", "right"]} style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={s.bar}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => (router.canGoBack() ? router.back() : router.replace(`/account/receipt/${id}`))} style={s.back}>
          <Icon name="back" />
        </Pressable>
        <Text accessibilityRole="header" style={type.h3}>{t("account.report.title")}</Text>
      </View>
      {!order ? (
        <View style={{ flex: 1, padding: space[5], justifyContent: "center" }}>
          {loaded.status === "error" ? (
            <LoadError error={loaded.error} onRetry={loaded.retry}
              title={loadedRefused(loaded.error) ? t("account.report.not_found") : undefined} />
          ) : <ActivityIndicator accessibilityLabel={t("common.loading")} color={color.peacock} />}
        </View>
      ) : (
      <>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[5], paddingBottom: 140 }} keyboardShouldPersistTaps="handled">
        <View style={s.card}>
          <Text style={s.h2}>{t("account.report.which_items")}</Text>
          {items.map((i) => {
            const n = pick[i.menu_item_id] ?? 0;
            const set = (v: number) => setPick((p) => ({ ...p, [i.menu_item_id]: Math.max(0, Math.min(i.quantity, v)) }));
            return (
              <View key={i.menu_item_id} style={s.row}>
                <Text style={[type.label, { flex: 1 }]}>{i.name} <Text style={s.muted}>· {t("account.report.ordered", { count: i.quantity })}</Text></Text>
                <Pressable accessibilityRole="button" accessibilityLabel={t("kitchen.one_less", { name: i.name })} onPress={() => set(n - 1)} style={s.step}><Text style={s.stepText}>−</Text></Pressable>
                <Text accessibilityLabel={`${t("account.report.how_many", { item: i.name })}: ${n}`} style={[type.h3, { width: 28, textAlign: "center" }]}>{n}</Text>
                <Pressable accessibilityRole="button" accessibilityLabel={t("kitchen.one_more", { name: i.name })} onPress={() => set(n + 1)} style={s.step}><Text style={s.stepText}>+</Text></Pressable>
              </View>
            );
          })}
        </View>
        <View style={s.card}>
          <Text style={s.h2}>{t("account.report.what_wrong")}</Text>
          <View accessibilityRole="radiogroup" style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {REASONS.map((r) => (
              <Pressable key={r} testID={`reason-${r}`} accessibilityRole="radio" accessibilityState={{ checked: reason === r }} onPress={() => setReason(r)}
                style={[s.chip, reason === r && { borderColor: color.peacock, backgroundColor: color.peacockMist }]}>
                <Text style={type.label}>{t(`account.report.reason_${r}`)}</Text>
              </Pressable>
            ))}
          </View>
          <TextInput testID="problem-note" accessibilityLabel={t("account.report.more")} value={note} onChangeText={setNote} maxLength={300}
            placeholder={t("account.report.more")} placeholderTextColor={color.muted} style={[field.body, s.input]} />
        </View>
        <View style={s.card}>
          <Text style={s.h2}>{t("account.report.photo")}</Text>
          <Pressable testID="problem-photo" accessibilityRole="button" accessibilityLabel={t("app.report.add_photo")} onPress={addPhoto} style={s.photo}>
            {photo ? <Image source={{ uri: photo.uri }} style={StyleSheet.absoluteFill} resizeMode="cover" /> : null}
            {busy === "photo" ? <Text style={s.muted}>{t("app.report.uploading")}</Text> : photo ? null : <Text style={[type.label, { color: color.peacockDeep }]}>{t("app.report.add_photo")}</Text>}
          </Pressable>
        </View>
        {error ? <Text accessibilityRole="alert" style={[type.small, { color: color.chili }]}>{error}</Text> : null}
      </ScrollView>
      <View style={s.footer}>
        <Button testID="send-report" title={busy === "send" ? t("account.report.sending") : t("account.report.send")} size="lg" block loading={busy === "send"} disabled={!chosen || !reason || busy === "photo"} onPress={send} />
      </View>
      </>
      )}
    </SafeAreaView>
  );
}

/** The API said no (not this person's order, or no such order): "not found", not "can't reach". */
function loadedRefused(error: unknown): boolean {
  return error instanceof ApiError && error.status < 500;
}

const s = textStyles(StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.porcelain, padding: space[5] },
  bar: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: space[5], paddingVertical: space[3] },
  back: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: color.white, borderRadius: radius.card, padding: space[4], gap: space[3] },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  step: { width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  chip: { paddingHorizontal: 16, height: 44, justifyContent: "center", borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
  input: { height: 52, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16 },
  photo: { height: 120, borderRadius: radius.card, borderWidth: 1.5, borderStyle: "dashed", borderColor: color.lineStrong, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  footer: { position: "absolute", left: 0, right: 0, bottom: 0, padding: space[5], backgroundColor: color.white, borderTopWidth: 1, borderTopColor: color.line },
}), {
  h1: ["h1", { color: color.kohl }],
  h2: ["h3", { color: color.kohl }],
  muted: ["small", { color: color.muted }],
  stepText: ["h3", { color: color.kohl }],
});
