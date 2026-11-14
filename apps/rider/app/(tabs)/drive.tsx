// Drive: the checklist until the rider is approved; then go online, get offers
// (RiderOffer.html, 30 seconds to accept) and carry on to the delivery.
import { api, ApiError, errorMessage, unwrap } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, Vibration, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle, Text as SvgText } from "react-native-svg";

import { Checklist } from "../../lib/checklist";
import { askForBackgroundLocation, askForLocation, hasBackgroundLocation, sendNow, startTracking, stopTracking } from "../../lib/location";
import { RouteMap } from "../../lib/map";
import { CITY_NAMES, cash, dist, useLive, useLiveRider, useOnboarding, useWeek, type Offer } from "../../lib/rider";
import { displayFont, night, radius, space, textFont, ui } from "../../lib/theme";

export default function Drive() {
  const onboarding = useOnboarding();
  const week = useWeek();
  const ready = onboarding.data?.ready ?? false;
  useLiveRider(ready);
  const now = useLive((s) => s.now);
  const refresh = useLive((s) => s.refresh);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [background, setBackground] = useState(true);

  useFocusEffect(useCallback(() => {
    void onboarding.reload();
    void week.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []));

  const status = now?.state.status ?? "offline";
  const finished = useLive((s) => s.finished);
  const busyWith = status === "busy" && !finished.includes(now?.state.order_id ?? "") ? now?.state.order_id : undefined;
  // Open the delivery only while this tab is on screen. After a batch's first drop-off the
  // live state moves on to the next order at once; pushing it then covered the "Delivered"
  // screen before the rider saw it (found on Railway QA, where the API isn't instant).
  // The rider goes on with "Next drop-off", which brings this tab back.
  const [focused, setFocused] = useState(true);
  useFocusEffect(useCallback(() => {
    setFocused(true);
    return () => setFocused(false);
  }, []));
  useEffect(() => {
    if (busyWith && focused) router.push({ pathname: "/delivery/[id]", params: { id: busyWith } });
  }, [busyWith, focused]);
  useEffect(() => {
    // Keep GPS going whenever the server thinks we're online (e.g. after a restart).
    if (status !== "offline") void startTracking();
    void hasBackgroundLocation().then(setBackground);
  }, [status]);

  if (!onboarding.data) {
    return (
      <SafeAreaView style={[ui.screen, styles.center]}>
        {onboarding.error ? <Text style={ui.body}>{onboarding.error}</Text> : <ActivityIndicator color={night.kesar} />}
      </SafeAreaView>
    );
  }
  const w = week.data;
  const city = w?.city ? CITY_NAMES[w.city] ?? w.city : null;
  const floor = w?.summary.hourly_floor && city ? `${city} has a ${cash(w.summary.hourly_floor, w.currency)} per active hour floor` : null;
  if (!ready) return <Checklist onboarding={onboarding.data} floor={floor} onRefresh={() => void onboarding.reload()} />;

  async function goOnline() {
    setBusy(true);
    setError(null);
    try {
      if (!(await askForLocation())) {
        setError("Allow location so we can offer you deliveries nearby.");
        return;
      }
      const fix = await sendNow();
      if (!fix) {
        setError("We can't find your location yet. Try again in a moment.");
        return;
      }
      unwrap(await api.realtime.POST("/api/v1/riders/me/online", { body: fix }));
      await startTracking();
      await sendNow();
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : errorMessage(null, "Couldn't go online. Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function goOffline() {
    setBusy(true);
    setError(null);
    try {
      unwrap(await api.realtime.POST("/api/v1/riders/me/offline"));
      await stopTracking();
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't go offline. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const fix = now?.location ? ([now.location.lat, now.location.lng] as [number, number]) : null;
  const online = status !== "offline";
  const today = w ? cash(w.today.total, w.currency) : "–";
  return (
    <View style={ui.screen}>
      <RouteMap rider={fix} pickup={now?.offer?.pickup} dropoff={now?.offer?.dropoff} height={status === "offered" ? 400 : 560} visible={status === "offered" ? 370 : 520} />
      <SafeAreaView edges={["top"]} style={styles.top}>
        <View style={ui.pill} accessibilityLabel={online ? `Online${city ? ` in ${city}` : ""}` : "Offline"}>
          <View style={[styles.dot, { backgroundColor: online ? night.online : night.muted }]} />
          <Text style={ui.pillText}>{online ? `Online${city ? ` · ${city}` : ""}` : "Offline"}</Text>
        </View>
        <View style={ui.pill}><Text style={[ui.pillText, { fontVariant: ["tabular-nums"] }]}>Today {today}</Text></View>
      </SafeAreaView>
      {status === "offered" && now?.offer ? (
        <OfferSheet key={now.offer.order_id} offer={now.offer} onDone={() => void refresh()} />
      ) : (
        <View style={[ui.sheet, styles.panel]}>
          <Text style={[ui.h1, { fontSize: 26 }]}>{online ? "Looking for deliveries" : "You're offline"}</Text>
          <Text style={ui.muted}>
            {online
              ? "Stay near busy kitchens. Offers show the full pay, distance and time before you accept."
              : "Go online to get delivery offers near you. Your location is shared only while you're online."}
          </Text>
          {online && !background ? (
            <Pressable accessibilityRole="button" onPress={async () => setBackground(await askForBackgroundLocation())} style={styles.bg}>
              <Text style={[ui.body, { fontSize: 14, lineHeight: 20 }]}>
                <Text style={ui.bold}>Keep offers coming with the screen off.</Text> Allow location “all the time”; you can turn it off by going offline.
              </Text>
            </Pressable>
          ) : null}
          {error ? <Text style={[textFont("600"), { color: night.sosText, fontSize: 14 }]}>{error}</Text> : null}
          {online ? (
            <Pressable accessibilityRole="button" onPress={goOffline} disabled={busy} style={ui.outline}>
              <Text style={[ui.bold, { fontSize: 16 }]}>{busy ? "…" : "Go offline"}</Text>
            </Pressable>
          ) : (
            <Pressable accessibilityRole="button" onPress={goOnline} disabled={busy} style={[ui.cta, busy && { opacity: 0.6 }]}>
              <Text style={ui.ctaText}>{busy ? "Going online…" : "Go online"}</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

function OfferSheet({ offer, onDone }: { offer: Offer; onDone: () => void }) {
  const total = offer.expires_in || 30;
  const left = useSecondsLeft(offer.expires_at, total);
  const [busy, setBusy] = useState<"accept" | "pass" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const unit = offer.distance_unit ?? "km";
  const cur = offer.currency ?? (unit === "mi" ? "USD" : "INR");
  const tripKm = (offer.distance_km ?? 0) + (offer.trip_km ?? 0);
  const batch = offer.batch && offer.batch.length > 1 ? offer.batch : null;
  const minutes = batch ? (offer.batch_minutes != null ? Math.round(offer.batch_minutes) : null) : offer.eta?.to_customer_minutes ?? null;
  const pay = Number(offer.rider_pay ?? 0);
  const rate = minutes ? pay / (minutes / 60) : null;
  const bags = offer.bags ?? 1;
  const ready = offer.ready_in_minutes;
  const seen = useRef(offer.order_id);
  useEffect(() => {
    seen.current = offer.order_id;
    Vibration.vibrate([0, 400, 200, 400]);
  }, [offer.order_id]);

  async function act(kind: "accept" | "pass") {
    setBusy(kind);
    setError(null);
    try {
      const path = kind === "accept" ? "/api/v1/offers/{order_id}/accept" : "/api/v1/offers/{order_id}/pass";
      unwrap(await api.realtime.POST(path, { params: { path: { order_id: offer.order_id } } }));
      if (kind === "accept") router.push({ pathname: "/delivery/[id]", params: { id: offer.order_id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "This offer is no longer available.");
    } finally {
      setBusy(null);
      onDone();
    }
  }

  return (
    <View style={[ui.sheet, styles.offer, batch && { height: 540 }]} accessibilityLabel={batch ? `New offer: ${batch.length} deliveries` : "New delivery offer"}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
        <View style={{ flex: 1 }}>
          <Text style={[textFont("700"), { fontSize: 13, letterSpacing: 1.4, color: night.kesar }]}>{batch ? `${batch.length} DELIVERIES · ONE PICKUP` : "NEW DELIVERY"}</Text>
          <Text testID="offer-pay" style={[displayFont("600"), styles.pay]}>{cash(pay, cur)}</Text>
          <Text style={[ui.muted, { fontSize: 14, marginTop: 8 }]}>
            {batch ? "Guaranteed for both" : "Guaranteed"}{Number(offer.tip ?? 0) > 0 ? ` · includes ${cash(offer.tip, cur)} ${batch ? "tips" : "tip"}` : ""}
          </Text>
        </View>
        <Ring left={left} total={total} />
      </View>
      <View style={ui.stats}>
        <View style={ui.stat}><Text style={ui.statValue}>{dist(tripKm, unit)}</Text><Text style={ui.statLabel}>distance</Text></View>
        <View style={[ui.stat, styles.statMid]}><Text style={ui.statValue}>{minutes ? `~${minutes} min` : "–"}</Text><Text style={ui.statLabel}>time</Text></View>
        <View style={ui.stat}><Text style={ui.statValue}>{rate ? `${cash(rate, cur, 0)}/hr` : "–"}</Text><Text style={ui.statLabel}>rate</Text></View>
      </View>
      <View style={{ gap: 14 }}>
        <View style={styles.stop}>
          <View style={[styles.stopDot, { backgroundColor: night.kesar, borderRadius: radius.pill }]} />
          <View style={{ flex: 1 }}>
            <Text style={[ui.bold, { fontSize: 16 }]}>{offer.restaurant_name}</Text>
            <Text style={ui.muted}>
              Pickup{batch ? ` of ${batch.length} orders` : ""} · {dist(offer.distance_km, unit)} · {ready == null ? "being prepared" : ready <= 0 ? "ready now" : `ready in ${ready} min`} · {bags} {bags === 1 ? "bag" : "bags"}
            </Text>
          </View>
        </View>
        {batch ? batch.map((b, i) => (
          <View key={b.order_id} style={styles.stop} testID={`offer-drop-${i + 1}`}>
            <View style={[styles.stopDot, { backgroundColor: night.text, borderRadius: 3 }]} />
            <View style={{ flex: 1 }}>
              <Text style={[ui.bold, { fontSize: 16 }]}>{`Drop-off ${i + 1}${b.batch_rate ? " · batch rate" : ""}`}</Text>
              <Text style={ui.muted}>{[b.drop_area ? `near ${b.drop_area}` : "address after pickup", b.code, b.trip_km != null ? `${dist(b.trip_km, unit)} from the kitchen` : null,
                b.rider_pay != null ? `${cash(b.rider_pay, cur)} pay` : null].filter(Boolean).join(" · ")}</Text>
            </View>
          </View>
        )) : (
        <View style={styles.stop}>
          <View style={[styles.stopDot, { backgroundColor: night.text, borderRadius: 3 }]} />
          <View style={{ flex: 1 }}>
            <Text style={[ui.bold, { fontSize: 16 }]}>{offer.drop_area ? `Near ${offer.drop_area}` : "Drop-off"}</Text>
            <Text style={ui.muted}>Drop-off · {dist(offer.trip_km, unit)} further · address after pickup</Text>
          </View>
        </View>
        )}
      </View>
      {error ? <Text style={[textFont("600"), { color: night.sosText, fontSize: 14 }]}>{error}</Text> : null}
      <View style={{ flexDirection: "row", gap: 10, marginTop: "auto" }}>
        <Pressable accessibilityRole="button" onPress={() => act("pass")} disabled={!!busy} style={styles.pass}>
          <Text style={[ui.bold, { fontSize: 16, ...textFont("700") }]}>{busy === "pass" ? "…" : "Pass"}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => act("accept")} disabled={!!busy || left <= 0} style={[ui.cta, { flex: 1 }]}>
          <Text style={ui.ctaText}>{busy === "accept" ? "Accepting…" : "Accept"}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function useSecondsLeft(expiresAt: string, total: number) {
  const calc = useCallback(() => Math.max(0, Math.min(total, Math.round((Date.parse(expiresAt) - Date.now()) / 1000))), [expiresAt, total]);
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    const t = setInterval(() => setLeft(calc()), 250);
    return () => clearInterval(t);
  }, [calc]);
  return left;
}

function Ring({ left, total }: { left: number; total: number }) {
  const c = 2 * Math.PI * 29;
  return (
    <Svg width={68} height={68} viewBox="0 0 68 68" accessibilityLabel={`${left} seconds left to accept`}>
      <Circle cx={34} cy={34} r={29} fill="none" stroke={night.line} strokeWidth={6} />
      <Circle cx={34} cy={34} r={29} fill="none" stroke={night.kesar} strokeWidth={6} strokeLinecap="round"
        strokeDasharray={`${(c * left) / total} ${c}`} transform="rotate(-90 34 34)" />
      <SvgText x={34} y={40} textAnchor="middle" fontSize={18} fontWeight="800" fill={night.text}>{String(left)}</SvgText>
    </Svg>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
  top: { position: "absolute", left: 16, right: 16, top: 16, flexDirection: "row", justifyContent: "space-between" },
  dot: { width: 9, height: 9, borderRadius: radius.pill },
  panel: { padding: 22, gap: space[3] },
  bg: { padding: 14, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg },
  offer: { height: 470, paddingTop: 26, paddingHorizontal: 22, paddingBottom: 22, gap: 18 },
  pay: { color: night.text, fontSize: 64, letterSpacing: -2.5, lineHeight: 64, marginTop: 8, fontVariant: ["tabular-nums"] },
  statMid: { borderLeftWidth: 1, borderRightWidth: 1, borderColor: night.divider },
  stop: { flexDirection: "row", gap: 14 },
  stopDot: { marginTop: 4, width: 12, height: 12 },
  pass: {
    width: 112, height: 64, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.lineStrong,
    alignItems: "center", justifyContent: "center",
  },
});
