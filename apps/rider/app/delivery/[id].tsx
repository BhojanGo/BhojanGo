// The accepted delivery: step 1 pickup, step 2 drop-off (RiderDropoff.html)
// with proof: a photo of the bags at the door, or the customer's PIN.
import { api, ApiError, unwrap } from "@bhojango/mobile-core";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Image, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../../lib/icons";
import { RouteMap } from "../../lib/map";
import { dist, useLive, useOrder } from "../../lib/rider";
import { displayFont, night, radius, space, textFont, ui } from "../../lib/theme";
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

export default function Delivery() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: order, error, reload } = useOrder(id);
  const fixNow = useLive((s) => s.now?.location);
  const refreshLive = useLive((s) => s.refresh);
  const finish = useLive((s) => s.finish);
  const [proof, setProof] = useState<"photo" | "pin">("photo");
  const [photo, setPhoto] = useState<{ uri: string; key: string | null } | null>(null);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const t = setInterval(() => void reload(), 8000);
    return () => clearInterval(t);
  }, [reload]);

  if (!order) {
    return <SafeAreaView style={[ui.screen, styles.center]}>{error ? <Text style={ui.body}>{error}</Text> : <ActivityIndicator color={night.kesar} />}</SafeAreaView>;
  }
  const o = order;
  const pickup: [number, number] | null = o.pickup_lat != null && o.pickup_lng != null ? [o.pickup_lat, o.pickup_lng] : null;
  const drop: [number, number] | null = o.delivery_lat != null && o.delivery_lng != null ? [o.delivery_lat, o.delivery_lng] : null;
  const rider: [number, number] | null = fixNow ? [fixNow.lat, fixNow.lng] : null;
  const unit = order.currency === "USD" ? "mi" : "km";
  const code = "#" + order.id.replace(/-/g, "").slice(0, 6).toUpperCase();
  const picked = order.status === "picked_up";
  const items = (order.items ?? []) as { name?: string; quantity?: number }[];
  const addr = (order.delivery_address ?? {}) as Record<string, string | undefined>;
  const name = (order.customer as { name?: string } | null)?.name ?? "Customer";

  if (order.status === "delivered" || order.status === "cancelled") {
    return (
      <SafeAreaView style={[ui.screen, { padding: space[5], gap: space[4], justifyContent: "center" }]}>
        <Text style={ui.h1}>{order.status === "delivered" ? "Delivered" : "This order was cancelled"}</Text>
        <Text style={ui.muted}>{order.status === "delivered" ? "Nice work. Your pay for it is in this week's earnings." : "You'll be paid for the time you spent on it."}</Text>
        <Pressable accessibilityRole="button" onPress={() => { finish(order.id); void refreshLive(); router.replace("/drive"); }} style={ui.cta}>
          <Text style={ui.ctaText}>Back to driving</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  async function pickedUp() {
    setBusy("pickup");
    setMsg(null);
    try {
      unwrap(await api.core.PUT("/api/v1/orders/{order_id}/status", { params: { path: { order_id: order!.id } }, body: { status: "picked_up" } }));
      await reload();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Couldn't update the order. Try again.");
    } finally {
      setBusy(null);
    }
  }

  async function takePhoto() {
    setMsg(null);
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      setMsg("Allow the camera to take a photo at the door, or use the PIN.");
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
      setMsg((e as Error).message);
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
      setMsg(e instanceof ApiError ? e.message : "Couldn't complete the delivery. Try again.");
      if (proof === "pin") setPin("");
    } finally {
      setBusy(null);
    }
  }

  const canComplete = proof === "pin" ? pin.length === 4 : !!photo?.key;
  const toDrop = km(rider ?? pickup, drop);
  const toPickup = km(rider, pickup);
  const dDrop = toDrop == null ? "" : dist(toDrop, unit);
  return (
    <View style={ui.screen}>
      <RouteMap rider={rider} pickup={picked ? null : pickup} dropoff={drop} height={picked ? 260 : 320} visible={picked ? 200 : 260} done={picked} />
      <SafeAreaView edges={["top"]} style={styles.top}>
        <View style={ui.pill}><Text style={ui.pillText}>{picked ? "Drop-off · step 2 of 2" : "Pickup · step 1 of 2"}</Text></View>
        <Pressable accessibilityRole="button" accessibilityLabel="SOS, get help now" onPress={() => router.push("/sos")} style={styles.sos}>
          <Text style={[textFont("800"), { color: night.sosText, fontSize: 14 }]}>SOS</Text>
        </Pressable>
      </SafeAreaView>

      <View style={[ui.sheet, { top: picked ? 200 : 260 }]}>
        <ScrollView contentContainerStyle={styles.sheetBody} keyboardShouldPersistTaps="handled">
          {picked ? (
            <>
              <View>
                <Text style={[displayFont("600"), styles.name]}>{name}</Text>
                <Text style={[ui.muted, { fontSize: 14, marginTop: 4 }]}>
                  {[addr.street, dDrop, `order ${code}`].filter(Boolean).join(" · ")}
                </Text>
              </View>
              {order.special_instructions ? (
                <View style={styles.note}>
                  <Text style={[textFont("400"), { color: night.needed, fontSize: 14, lineHeight: 21 }]}>
                    <Text style={textFont("800")}>Note. </Text>{order.special_instructions}
                  </Text>
                </View>
              ) : null}
              <Pressable accessibilityRole="button" onPress={() => navigate(drop, name)} style={[ui.outline, { marginTop: 12 }]}>
                <Icon name="navigate" size={20} stroke={night.link} />
                <Text style={[ui.bold, { ...textFont("700") }]}>Navigate</Text>
              </Pressable>

              <Text style={[ui.bold, { fontSize: 15, marginTop: 24 }]}>Proof of delivery</Text>
              <View accessibilityRole="radiogroup" accessibilityLabel="Proof type" style={styles.seg}>
                {(["photo", "pin"] as const).map((k) => (
                  <Pressable key={k} accessibilityRole="radio" accessibilityState={{ checked: proof === k }} onPress={() => { setProof(k); setMsg(null); }}
                    style={[styles.segBtn, proof === k && { backgroundColor: night.line }]}>
                    <Text style={[textFont(proof === k ? "800" : "600"), { fontSize: 14, color: proof === k ? night.text : night.muted }]}>
                      {k === "photo" ? "Photo at door" : "Hand over · PIN"}
                    </Text>
                  </Pressable>
                ))}
              </View>
              {proof === "photo" ? (
                <Pressable accessibilityRole="button" onPress={takePhoto} style={styles.shot}>
                  {photo ? (
                    <Image source={{ uri: photo.uri }} style={StyleSheet.absoluteFill} resizeMode="cover" />
                  ) : null}
                  {busy === "photo" ? <ActivityIndicator color={night.kesar} /> : photo ? null : (
                    <>
                      <Icon name="camera" size={28} stroke={night.link} />
                      <Text style={[ui.bold, textFont("700")]}>Take photo of the bags at the door</Text>
                    </>
                  )}
                </Pressable>
              ) : (
                <View style={{ marginTop: 12, gap: 8 }}>
                  <Text style={ui.muted}>Ask {name.split(" ")[0]} for the 4-digit PIN on their tracking screen.</Text>
                  <TextInput testID="pin" accessibilityLabel="Customer's PIN" value={pin} onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 4))}
                    keyboardType="number-pad" maxLength={4} placeholder="• • • •" placeholderTextColor={night.muted}
                    style={[textFont("800"), styles.pin]} />
                </View>
              )}
            </>
          ) : (
            <>
              <View>
                <Text style={[displayFont("600"), styles.name]}>{order.restaurant_name}</Text>
                <Text style={[ui.muted, { fontSize: 14, marginTop: 4 }]}>
                  {[toPickup != null ? dist(toPickup, unit) : null, `order ${code}`, `${items.reduce((n, i) => n + (i.quantity ?? 1), 0)} items`].filter(Boolean).join(" · ")}
                </Text>
              </View>
              <View style={[styles.note, { backgroundColor: order.status === "ready" ? night.info : night.noteBg }]}>
                <Text style={[textFont("700"), { color: order.status === "ready" ? night.text : night.needed, fontSize: 14 }]}>
                  {order.status === "ready" ? "Ready for pickup. Check the order code on the bag." : "The kitchen is still preparing it. We'll update this when it's ready."}
                </Text>
              </View>
              <Pressable accessibilityRole="button" onPress={() => navigate(pickup, order.restaurant_name)} style={[ui.outline, { marginTop: 12 }]}>
                <Icon name="navigate" size={20} stroke={night.link} />
                <Text style={[ui.bold, textFont("700")]}>Navigate</Text>
              </Pressable>
              <Text style={[ui.bold, { fontSize: 15, marginTop: 24 }]}>In the bag</Text>
              {items.map((it, i) => (
                <View key={i} style={styles.itemRow}>
                  <Text style={[ui.bold, { width: 32 }]}>{it.quantity ?? 1}×</Text>
                  <Text style={[ui.body, { flex: 1 }]}>{it.name}</Text>
                </View>
              ))}
              <Text style={[ui.muted, { marginTop: 8 }]}>Drop-off near {addr.area ?? addr.city ?? "the customer"}; the address shows after pickup.</Text>
            </>
          )}
          {msg ? <Text style={[textFont("600"), { color: night.sosText, fontSize: 14, marginTop: 12 }]}>{msg}</Text> : null}
        </ScrollView>
        <View style={{ padding: 20, paddingTop: 8 }}>
          {picked ? (
            <Pressable accessibilityRole="button" disabled={!canComplete || !!busy} onPress={complete}
              style={[ui.cta, { opacity: canComplete && !busy ? 1 : 0.5 }]}>
              <Text style={ui.ctaText}>{busy === "complete" ? "Completing…" : "Complete delivery"}</Text>
            </Pressable>
          ) : (
            <Pressable accessibilityRole="button" disabled={order.status !== "ready" || !!busy} onPress={pickedUp}
              style={[ui.cta, { opacity: order.status === "ready" && !busy ? 1 : 0.5 }]}>
              <Text style={ui.ctaText}>{busy === "pickup" ? "…" : order.status === "ready" ? "Picked up" : "Waiting for the kitchen"}</Text>
            </Pressable>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
  top: { position: "absolute", left: 20, right: 20, top: 16, flexDirection: "row", justifyContent: "space-between" },
  sos: {
    height: 44, paddingHorizontal: 16, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.sosBorder,
    backgroundColor: "rgba(20, 34, 37, 0.92)", justifyContent: "center",
  },
  sheetBody: { paddingTop: 24, paddingHorizontal: 20, paddingBottom: 8 },
  name: { color: night.text, fontSize: 28, letterSpacing: -0.6, lineHeight: 31 },
  note: { marginTop: 16, padding: 16, borderRadius: 16, backgroundColor: night.noteBg },
  seg: { marginTop: 12, flexDirection: "row", padding: 4, borderRadius: radius.pill, backgroundColor: night.map },
  segBtn: { flex: 1, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  shot: {
    marginTop: 12, height: 112, borderRadius: 16, borderWidth: 1.5, borderStyle: "dashed", borderColor: night.dashed,
    backgroundColor: night.map, alignItems: "center", justifyContent: "center", gap: 8, overflow: "hidden",
  },
  pin: {
    height: 64, borderRadius: 16, borderWidth: 1.5, borderColor: night.lineStrong, backgroundColor: night.map, color: night.text,
    fontSize: 28, letterSpacing: 12, textAlign: "center",
  },
  itemRow: { flexDirection: "row", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: night.raised },
});
