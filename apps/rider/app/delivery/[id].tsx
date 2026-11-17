// The accepted delivery: step 1 pickup, step 2 drop-off (RiderDropoff.html)
// with proof: a photo of the bags at the door, or the customer's PIN.
//
// The server's order is the truth: the kitchen marks it ready, and on QA the demo
// simulator (or the same rider on another phone) may pick it up or deliver it.
// The screen polls the order and the rider's live state, shows whatever step the
// server is at, reloads after a refused action instead of insisting, and says so
// plainly when the order is no longer this rider's.
import { api, ApiError, field, LoadError, num, QuickChat, SafeAreaView, type, unwrap, useI18n } from "@bhojango/mobile-core";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Image, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { Icon } from "../../lib/icons";
import { RouteMap } from "../../lib/map";
import { useFormat, useLive, useOrder } from "../../lib/rider";
import { night, radius, space, textFont, ui } from "../../lib/theme";
import { uploadFile } from "../../lib/upload";

function km(a: [number, number] | null, b: [number, number] | null): number | null {
  if (!a || !b) return null;
  const R = 6371, dLat = ((b[0] - a[0]) * Math.PI) / 180, dLng = ((b[1] - a[1]) * Math.PI) / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos((a[0] * Math.PI) / 180) * Math.cos((b[0] * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h)) * 1.3;
}

function navigate(to: [number, number] | null, label: string) {
  if (!to) return;
  const [lat, lng] = to;
  const url = Platform.OS === "ios" ? `maps:?daddr=${lat},${lng}&q=${encodeURIComponent(label)}` : `google.navigation:q=${lat},${lng}`;
  Linking.openURL(url).catch(() => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`));
}

const POLL_MS = 5000;

export default function Delivery() {
  const { dist, unitFor } = useFormat();
  const { t } = useI18n();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: order, failure, gone, reload } = useOrder(id);
  const fixNow = useLive((s) => s.now?.location);
  const refreshLive = useLive((s) => s.refresh);
  const finish = useLive((s) => s.finish);
  // Task 43: the orders still to drop on this batch (this one first, then the rest).
  const batch = useLive((s) => s.now?.state.batch) ?? [];
  const others = batch.filter((b) => b !== id);
  const [proof, setProof] = useState<"photo" | "pin">("photo");
  const [photo, setPhoto] = useState<{ uri: string; key: string | null } | null>(null);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  // The other bags of a batch: one may still be cooking. Pick up only when all are ready.
  const [othersReady, setOthersReady] = useState(0);
  const othersKey = others.join(",");
  useEffect(() => {
    const check = async () => {
      let n = 0;
      for (const other of others) {
        const o = await api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: other } } }).catch(() => null);
        if (o?.data && ["ready", "picked_up", "delivered", "cancelled"].includes(o.data.status)) n += 1;
      }
      setOthersReady(n);
    };
    void check();
    // The order moves on without this phone (the rider's position comes from the Drive tab's live poll).
    const timer = setInterval(() => { void reload(); void check(); }, POLL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload, othersKey]);

  const backToDriving = () => {
    if (id) finish(id);
    void refreshLive();
    router.replace("/drive");
  };

  if (gone) {
    return (
      <SafeAreaView testID="delivery-gone" style={[ui.screen, { padding: space[5], gap: space[4], justifyContent: "center" }]}>
        <Text style={ui.h1}>{t("rider.delivery.gone_title")}</Text>
        <Text style={ui.muted}>{t("rider.delivery.gone_sub")}</Text>
        <Pressable testID="back-to-driving" accessibilityRole="button" onPress={backToDriving} style={ui.cta}>
          <Text style={ui.ctaText}>{t("rider.delivery.back_to_driving")}</Text>
        </Pressable>
      </SafeAreaView>
    );
  }
  if (!order) {
    return (
      <SafeAreaView style={[ui.screen, styles.center]}>
        {failure ? <LoadError error={failure} onRetry={reload} tone="dark" fill style={{ alignSelf: "stretch" }} />
          : <ActivityIndicator testID="delivery-loading" color={night.kesar} />}
      </SafeAreaView>
    );
  }
  const o = order;
  const pickup: [number, number] | null = o.pickup_lat != null && o.pickup_lng != null ? [o.pickup_lat, o.pickup_lng] : null;
  const drop: [number, number] | null = o.delivery_lat != null && o.delivery_lng != null ? [o.delivery_lat, o.delivery_lng] : null;
  const rider: [number, number] | null = fixNow ? [fixNow.lat, fixNow.lng] : null;
  const unit = unitFor(order.currency); // the order's country's unit (Markets)
  const code = "#" + order.id.replace(/-/g, "").slice(0, 6).toUpperCase();
  const picked = order.status === "picked_up";
  const items = (order.items ?? []) as { name?: string; quantity?: number }[];
  const addr = (order.delivery_address ?? {}) as Record<string, string | undefined>;
  const name = (order.customer as { name?: string } | null)?.name ?? t("rider.delivery.customer");
  const position = batch.length > 1 && batch.includes(order.id) ? t("rider.delivery.order_n", { n: batch.indexOf(order.id) + 1, total: batch.length }) : null;

  if (order.status === "delivered" || order.status === "cancelled") {
    const delivered = order.status === "delivered";
    return (
      <SafeAreaView testID={delivered ? "delivery-delivered" : "delivery-cancelled"}
        style={[ui.screen, { padding: space[5], gap: space[4], justifyContent: "center" }]}>
        <Text style={ui.h1}>{delivered ? t("rider.delivery.delivered") : t("rider.delivery.cancelled_title")}</Text>
        <Text style={ui.muted}>{delivered ? t("rider.delivery.delivered_sub") : t("rider.delivery.cancelled_sub")}</Text>
        <Pressable testID="back-to-driving" accessibilityRole="button" onPress={backToDriving} style={ui.cta}>
          <Text style={ui.ctaText}>{others.length ? t("rider.delivery.next_drop") : t("rider.delivery.back_to_driving")}</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  /** A refused step usually means the order moved on elsewhere: show the server's state. */
  async function refused(e: unknown, fallback: string) {
    setMsg(e instanceof ApiError ? e.message : fallback);
    await reload();
    void refreshLive();
  }

  async function pickedUp() {
    setBusy("pickup");
    setMsg(null);
    try {
      unwrap(await api.core.PUT("/api/v1/orders/{order_id}/status", { params: { path: { order_id: order!.id } }, body: { status: "picked_up" } }));
      // A batch is collected at one counter: the other bags come too.
      for (const other of others) {
        const o = await api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: other } } }).catch(() => null);
        if (o?.data?.status === "ready") {
          await api.core.PUT("/api/v1/orders/{order_id}/status", { params: { path: { order_id: other } }, body: { status: "picked_up" } }).catch(() => null);
        }
      }
      await reload();
    } catch (e) {
      await refused(e, t("rider.delivery.update_failed"));
    } finally {
      setBusy(null);
    }
  }

  async function takePhoto() {
    setMsg(null);
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      setMsg(t("rider.delivery.camera_needed"));
      return;
    }
    const shot = await ImagePicker.launchCameraAsync({ quality: 0.6, allowsEditing: false });
    if (shot.canceled || !shot.assets[0]) return;
    const a = shot.assets[0];
    setPhoto({ uri: a.uri, key: null });
    setBusy("photo");
    try {
      const key = await uploadFile(a.uri, a.mimeType ?? "image/jpeg", "delivery_proof");
      setPhoto({ uri: a.uri, key });
    } catch (e) {
      setPhoto(null);
      setMsg((e as Error).message || t("rider.upload.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function complete() {
    setBusy("complete");
    setMsg(null);
    const body = proof === "pin"
      ? { status: "delivered" as const, proof: { method: "pin" as const, pin } }
      : { status: "delivered" as const, proof: { method: "photo" as const, photo_key: photo?.key ?? "" } };
    try {
      unwrap(await api.core.PUT("/api/v1/orders/{order_id}/status", { params: { path: { order_id: order!.id } }, body }));
      await refreshLive();
      await reload();
    } catch (e) {
      if (proof === "pin") setPin("");
      await refused(e, t("rider.delivery.complete_failed"));
    } finally {
      setBusy(null);
    }
  }

  const canComplete = proof === "pin" ? pin.length === 4 : !!photo?.key;
  const allReady = order.status === "ready" && othersReady === others.length;
  const readyCount = (order.status === "ready" ? 1 : 0) + othersReady;
  const toDrop = km(rider ?? pickup, drop);
  const toPickup = km(rider, pickup);
  const dDrop = toDrop == null ? "" : dist(toDrop, unit);
  const count = items.reduce((n, i) => n + (i.quantity ?? 1), 0);
  return (
    <View testID="delivery-screen" style={ui.screen}>
      <RouteMap rider={rider} pickup={picked ? null : pickup} dropoff={drop} height={picked ? 260 : 320} visible={picked ? 200 : 260} done={picked}
        label={t("rider.map.label")} />
      <SafeAreaView edges={["top"]} style={styles.top}>
        <View testID={picked ? "step-dropoff" : "step-pickup"} style={ui.pill}>
          <Text style={ui.pillText}>{[position, picked ? t("rider.delivery.step_drop") : t("rider.delivery.step_pickup")].filter(Boolean).join(" · ")}</Text>
        </View>
        <Pressable testID="sos-open" accessibilityRole="button" accessibilityLabel={t("rider.delivery.sos_label")} onPress={() => router.push("/sos")} style={styles.sos}>
          <Text style={[type.label, { color: night.sosText }]}>{t("rider.delivery.sos")}</Text>
        </Pressable>
      </SafeAreaView>

      <View style={[ui.sheet, { top: picked ? 200 : 260 }]}>
        <ScrollView contentContainerStyle={styles.sheetBody} keyboardShouldPersistTaps="handled">
          {picked ? (
            <>
              <View>
                <Text testID="delivery-name" style={[type.h1, styles.name]}>{name}</Text>
                <Text style={[ui.muted, { marginTop: 4 }]}>
                  {[addr.street, dDrop, t("rider.delivery.order_code", { code })].filter(Boolean).join(" · ")}
                </Text>
              </View>
              {order.special_instructions ? (
                <View style={styles.note}>
                  <Text style={[type.small, { color: night.needed }]}>
                    <Text style={textFont("700")}>{t("rider.delivery.note")} </Text>{order.special_instructions}
                  </Text>
                </View>
              ) : null}
              <Pressable testID="navigate" accessibilityRole="button" onPress={() => navigate(drop, name)} style={[ui.outline, { marginTop: 12 }]}>
                <Icon name="navigate" size={20} stroke={night.link} />
                <Text style={ui.bold}>{t("rider.delivery.navigate")}</Text>
              </Pressable>
              <ChatButton orderId={order.id} />

              <Text style={[ui.bold, { marginTop: 24 }]}>{t("rider.delivery.proof_title")}</Text>
              <View accessibilityRole="radiogroup" accessibilityLabel={t("rider.delivery.proof_type")} style={styles.seg}>
                {(["photo", "pin"] as const).map((k) => (
                  <Pressable key={k} testID={`proof-${k}`} accessibilityRole="radio" accessibilityState={{ checked: proof === k }} onPress={() => { setProof(k); setMsg(null); }}
                    style={[styles.segBtn, proof === k && { backgroundColor: night.line }]}>
                    <Text style={[type.label, { color: proof === k ? night.text : night.muted }]}>
                      {k === "photo" ? t("rider.delivery.photo_at_door") : t("rider.delivery.pin_handover")}
                    </Text>
                  </Pressable>
                ))}
              </View>
              {proof === "photo" ? (
                <Pressable testID="take-photo" accessibilityRole="button" onPress={takePhoto} style={styles.shot}>
                  {photo ? (
                    <Image source={{ uri: photo.uri }} style={StyleSheet.absoluteFill} resizeMode="cover" />
                  ) : null}
                  {busy === "photo" ? <ActivityIndicator color={night.kesar} /> : photo ? null : (
                    <>
                      <Icon name="camera" size={28} stroke={night.link} />
                      <Text style={ui.bold}>{t("rider.delivery.take_photo")}</Text>
                    </>
                  )}
                </Pressable>
              ) : (
                <View style={{ marginTop: 12, gap: 8 }}>
                  <Text style={ui.muted}>{t("rider.delivery.ask_pin", { name: name.split(" ")[0] ?? name })}</Text>
                  <TextInput testID="pin" accessibilityLabel={t("rider.delivery.pin_label")} value={pin} onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 4))}
                    keyboardType="number-pad" maxLength={4} placeholder="• • • •" placeholderTextColor={night.muted}
                    style={[field.h1, num, styles.pin]} />
                </View>
              )}
            </>
          ) : (
            <>
              <View>
                <Text testID="delivery-name" style={[type.h1, styles.name]}>{order.restaurant_name}</Text>
                <Text style={[ui.muted, { marginTop: 4 }]}>
                  {[toPickup != null ? dist(toPickup, unit) : null, t("rider.delivery.order_code", { code }), t("rider.delivery.items", { count })]
                    .filter(Boolean).join(" · ")}
                </Text>
              </View>
              <View testID={order.status === "ready" ? "kitchen-ready" : "kitchen-preparing"}
                style={[styles.note, { backgroundColor: order.status === "ready" ? night.info : night.noteBg }]}>
                <Text style={[type.label, { color: order.status === "ready" ? night.text : night.needed }]}>
                  {order.status === "ready" ? t("rider.delivery.ready_pickup") : t("rider.delivery.preparing")}
                </Text>
              </View>
              <Pressable testID="navigate" accessibilityRole="button" onPress={() => navigate(pickup, order.restaurant_name)} style={[ui.outline, { marginTop: 12 }]}>
                <Icon name="navigate" size={20} stroke={night.link} />
                <Text style={ui.bold}>{t("rider.delivery.navigate")}</Text>
              </Pressable>
              <ChatButton orderId={order.id} />
              <Text style={[ui.bold, { marginTop: 24 }]}>{t("rider.delivery.in_bag")}</Text>
              {items.map((it, i) => (
                <View key={i} style={styles.itemRow}>
                  <Text style={[ui.bold, { width: 32 }]}>{it.quantity ?? 1}×</Text>
                  <Text style={[ui.body, { flex: 1 }]}>{it.name}</Text>
                </View>
              ))}
              <Text style={[ui.muted, { marginTop: 8 }]}>
                {t("rider.delivery.drop_near", { area: addr.area ?? addr.city ?? t("rider.delivery.the_customer") })}
              </Text>
            </>
          )}
          {msg ? <Text testID="delivery-message" style={[type.label, { color: night.sosText, marginTop: 12 }]}>{msg}</Text> : null}
        </ScrollView>
        <View style={{ padding: 20, paddingTop: 8 }}>
          {picked ? (
            <Pressable testID="complete" accessibilityRole="button" disabled={!canComplete || !!busy} onPress={complete}
              style={[ui.cta, { opacity: canComplete && !busy ? 1 : 0.5 }]}>
              <Text style={ui.ctaText}>{busy === "complete" ? t("rider.delivery.completing") : t("rider.delivery.complete")}</Text>
            </Pressable>
          ) : (
            <Pressable testID="picked-up" accessibilityRole="button" disabled={!allReady || !!busy} onPress={pickedUp}
              style={[ui.cta, { opacity: allReady && !busy ? 1 : 0.5 }]}>
              <Text style={ui.ctaText}>{busy === "pickup" ? "…" : allReady
                ? (others.length ? t("rider.delivery.picked_up_all", { count: others.length + 1 }) : t("rider.delivery.picked_up"))
                : others.length ? t("rider.delivery.waiting_batch", { ready: readyCount, total: others.length + 1 }) : t("rider.delivery.waiting_kitchen")}</Text>
            </Pressable>
          )}
        </View>
      </View>
    </View>
  );
}

/** Quick messages with the customer (B2): presets and short text, no phone numbers. */
function ChatButton({ orderId }: { orderId: string }) {
  const { t } = useI18n();
  return (
    <QuickChat orderId={orderId} tone="dark" render={(open, unread, who) => {
      const label = unread ? t("rider.delivery.message_new", { who, count: unread }) : t("rider.delivery.message", { who });
      return (
        <Pressable testID="chat-open" accessibilityRole="button" onPress={open} style={[ui.outline, { marginTop: 12 }]} accessibilityLabel={label}>
          <Icon name="message" size={20} stroke={night.link} />
          <Text style={ui.bold}>{label}</Text>
        </Pressable>
      );
    }} />
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center", gap: space[3], padding: space[5] },
  top: { position: "absolute", left: 20, right: 20, top: 16, flexDirection: "row", justifyContent: "space-between" },
  sos: {
    height: 44, paddingHorizontal: 16, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.sosBorder,
    backgroundColor: "rgba(20, 34, 37, 0.92)", justifyContent: "center",
  },
  sheetBody: { paddingTop: 24, paddingHorizontal: 20, paddingBottom: 8 },
  name: { color: night.text },
  note: { marginTop: 16, padding: 16, borderRadius: 16, backgroundColor: night.noteBg },
  seg: { marginTop: 12, flexDirection: "row", padding: 4, borderRadius: radius.pill, backgroundColor: night.map },
  segBtn: { flex: 1, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  shot: {
    marginTop: 12, height: 112, borderRadius: 16, borderWidth: 1.5, borderStyle: "dashed", borderColor: night.dashed,
    backgroundColor: night.map, alignItems: "center", justifyContent: "center", gap: 8, overflow: "hidden",
  },
  pin: {
    height: 64, borderRadius: 16, borderWidth: 1.5, borderColor: night.lineStrong, backgroundColor: night.map, color: night.text,
    letterSpacing: 12, textAlign: "center",
  },
  itemRow: { flexDirection: "row", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: night.raised },
});
