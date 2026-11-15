// Drive: the checklist until the rider is approved; then go online, get offers
// (RiderOffer.html, 30 seconds to accept) and carry on to the delivery.
//
// The server's state wins: an order can move on elsewhere (the kitchen, the demo
// simulator on QA, the same rider on another phone), so this tab follows
// /riders/me (WebSocket + a poll) and shares this phone's GPS only when the
// rider went online here (lib/location.ts trackingHere).
import { api, ApiError, num, type, unwrap, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, Vibration, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle, Text as SvgText } from "react-native-svg";

import { Checklist } from "../../lib/checklist";
import { askForBackgroundLocation, askForLocation, hasBackgroundLocation, sendNow, setTrackingNotice, startTracking, stopTracking,
  trackingHere } from "../../lib/location";
import { RouteMap } from "../../lib/map";
import { useFormat, useLive, useLiveRider, useOnboarding, useWeek, type Offer } from "../../lib/rider";
import { night, radius, space, ui } from "../../lib/theme";

export default function Drive() {
  const { cash, cityName } = useFormat();
  const { t } = useI18n();
  setTrackingNotice(t("rider.drive.notice_title"), t("rider.drive.notice_body"));
  const onboarding = useOnboarding();
  const week = useWeek();
  const ready = onboarding.data?.ready ?? false;
  useLiveRider(ready);
  const now = useLive((s) => s.now);
  const refresh = useLive((s) => s.refresh);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [background, setBackground] = useState(true);
  /** Does this phone share its GPS? null until known. */
  const [here, setHere] = useState<boolean | null>(null);

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
  // Each order opens by itself once: a rider who goes back (to check earnings, or the
  // demo rider on QA whose order the simulator drives) stays here and reopens it from
  // the "On a delivery" card instead of being pushed back to it on every visit.
  const [focused, setFocused] = useState(true);
  const opened = useRef<string | null>(null);
  useFocusEffect(useCallback(() => {
    setFocused(true);
    return () => setFocused(false);
  }, []));
  useEffect(() => {
    if (busyWith && focused && opened.current !== busyWith) {
      opened.current = busyWith;
      router.push({ pathname: "/delivery/[id]", params: { id: busyWith } });
    }
  }, [busyWith, focused]);
  useEffect(() => {
    // Keep GPS going while the server thinks we're online (e.g. after a restart), but only
    // on the phone that went online: on a second phone, or as the demo rider whose GPS the
    // simulator sends, this phone's position would fight the other source.
    let live = true;
    void (async () => {
      const mine = await trackingHere();
      if (status !== "offline" && mine) await startTracking();
      if (live) setHere(mine);
      const bg = await hasBackgroundLocation();
      if (live) setBackground(bg);
    })();
    return () => {
      live = false;
    };
  }, [status]);

  if (!onboarding.data) {
    return (
      <SafeAreaView style={[ui.screen, styles.center]}>
        {onboarding.error ? <Text style={ui.body}>{onboarding.error}</Text> : <ActivityIndicator testID="drive-loading" color={night.kesar} />}
      </SafeAreaView>
    );
  }
  const w = week.data;
  const city = cityName(w?.city);
  const floor = w?.summary.hourly_floor && city ? t("rider.drive.floor", { city, amount: cash(w.summary.hourly_floor, w.currency) }) : null;
  if (!ready) return <Checklist onboarding={onboarding.data} floor={floor} onRefresh={() => void onboarding.reload()} />;

  async function goOnline() {
    setBusy(true);
    setError(null);
    try {
      if (!(await askForLocation())) {
        setError(t("rider.drive.location_needed"));
        return;
      }
      const fix = await sendNow();
      if (!fix) {
        setError(t("rider.drive.no_fix"));
        return;
      }
      unwrap(await api.realtime.POST("/api/v1/riders/me/online", { body: fix }));
      await startTracking();
      setHere(true);
      await sendNow();
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("rider.drive.online_failed"));
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
      setHere(false);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("rider.drive.offline_failed"));
    } finally {
      setBusy(false);
    }
  }

  /** Online elsewhere (another phone, or the demo simulator): share this phone's GPS from now on. */
  async function shareFromThisPhone() {
    setError(null);
    if (!(await askForLocation())) {
      setError(t("rider.drive.location_needed"));
      return;
    }
    await startTracking();
    setHere(true);
    await sendNow();
    await refresh();
  }

  const openDelivery = () => {
    if (busyWith) router.push({ pathname: "/delivery/[id]", params: { id: busyWith } });
  };

  const fix = now?.location ? ([now.location.lat, now.location.lng] as [number, number]) : null;
  const online = status !== "offline";
  const today = w ? cash(w.today.total, w.currency) : "–";
  const statusText = online ? (city ? t("rider.drive.online_in", { city }) : t("rider.drive.online")) : t("rider.drive.offline");
  return (
    <View style={ui.screen}>
      <RouteMap rider={fix} pickup={now?.offer?.pickup} dropoff={now?.offer?.dropoff} height={status === "offered" ? 400 : 560}
        visible={status === "offered" ? 370 : 520} label={t("rider.map.label")} />
      <SafeAreaView edges={["top"]} style={styles.top}>
        <View testID={online ? "status-online" : "status-offline"} style={ui.pill} accessibilityLabel={statusText}>
          <View style={[styles.dot, { backgroundColor: online ? night.online : night.muted }]} />
          <Text style={ui.pillText}>{statusText}</Text>
        </View>
        <View testID="today-total" style={ui.pill}>
          <Text style={[ui.pillText, { fontVariant: ["tabular-nums"] }]}>{t("rider.drive.today", { amount: today })}</Text>
        </View>
      </SafeAreaView>
      {status === "offered" && now?.offer ? (
        <OfferSheet key={now.offer.order_id} offer={now.offer} onDone={() => void refresh()} onAccepted={(id) => { opened.current = id; }} />
      ) : (
        <View testID="drive-panel" style={[ui.sheet, styles.panel]}>
          <Text testID="drive-title" style={ui.h2}>
            {busyWith ? t("rider.drive.busy_title") : online ? t("rider.drive.looking_title") : t("rider.drive.offline_title")}
          </Text>
          <Text style={ui.muted}>{busyWith ? t("rider.drive.busy_sub") : online ? t("rider.drive.looking_sub") : t("rider.drive.offline_sub")}</Text>
          {busyWith ? (
            <Pressable testID="open-delivery" accessibilityRole="button" onPress={openDelivery} style={ui.cta}>
              <Text style={ui.ctaText}>{t("rider.drive.open_delivery")}</Text>
            </Pressable>
          ) : null}
          {online && here === false ? (
            <Pressable testID="use-this-phone" accessibilityRole="button" onPress={shareFromThisPhone} style={styles.bg}>
              <Text style={ui.note}>
                <Text style={ui.bold}>{t("rider.drive.elsewhere_title")}</Text> {t("rider.drive.elsewhere_sub")}
              </Text>
            </Pressable>
          ) : null}
          {online && here && !background ? (
            <Pressable accessibilityRole="button" onPress={async () => setBackground(await askForBackgroundLocation())} style={styles.bg}>
              <Text style={ui.note}>
                <Text style={ui.bold}>{t("rider.drive.background_title")}</Text> {t("rider.drive.background_sub")}
              </Text>
            </Pressable>
          ) : null}
          {error ? <Text style={[type.label, { color: night.sosText }]}>{error}</Text> : null}
          {busyWith ? null : online ? (
            <Pressable testID="go-offline" accessibilityRole="button" onPress={goOffline} disabled={busy} style={ui.outline}>
              <Text style={ui.bold}>{busy ? "…" : t("rider.drive.go_offline")}</Text>
            </Pressable>
          ) : (
            <Pressable testID="go-online" accessibilityRole="button" onPress={goOnline} disabled={busy} style={[ui.cta, busy && { opacity: 0.6 }]}>
              <Text style={ui.ctaText}>{busy ? t("rider.drive.going_online") : t("rider.drive.go_online")}</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

function OfferSheet({ offer, onDone, onAccepted }: { offer: Offer; onDone: () => void; onAccepted: (orderId: string) => void }) {
  const { cash, dist, unitFor } = useFormat();
  const { t } = useI18n();
  const total = offer.expires_in || 30;
  const left = useSecondsLeft(offer.expires_at, total);
  const [busy, setBusy] = useState<"accept" | "pass" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cur = offer.currency ?? null; // null: the current country's currency
  const unit = offer.distance_unit ?? unitFor(cur);
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
      if (kind === "accept") {
        onAccepted(offer.order_id);
        router.push({ pathname: "/delivery/[id]", params: { id: offer.order_id } });
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("rider.offer.gone"));
    } finally {
      setBusy(null);
      onDone();
    }
  }

  const tip = Number(offer.tip ?? 0) > 0 ? t(batch ? "rider.offer.includes_tips" : "rider.offer.includes_tip", { amount: cash(offer.tip, cur) }) : null;
  return (
    <View testID="offer-sheet" style={[ui.sheet, styles.offer, batch && { height: 540 }]}
      accessibilityLabel={batch ? t("rider.offer.label_batch", { count: batch.length }) : t("rider.offer.label_single")}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
        <View style={{ flex: 1 }}>
          <Text style={[type.label, { letterSpacing: 1.4, color: night.kesar }]}>
            {batch ? t("rider.offer.batch_title", { count: batch.length }) : t("rider.offer.new_delivery")}
          </Text>
          <Text testID="offer-pay" style={[type.display, num, styles.pay]}>{cash(pay, cur)}</Text>
          <Text style={[ui.muted, { marginTop: 8 }]}>
            {[batch ? t("rider.offer.guaranteed_all") : t("rider.offer.guaranteed"), tip].filter(Boolean).join(" · ")}
          </Text>
        </View>
        <Ring left={left} total={total} />
      </View>
      <View style={ui.stats}>
        <View style={ui.stat}><Text style={ui.statValue}>{dist(tripKm, unit)}</Text><Text style={ui.statLabel}>{t("rider.offer.distance")}</Text></View>
        <View style={[ui.stat, styles.statMid]}>
          <Text style={ui.statValue}>{minutes ? t("rider.offer.minutes", { min: minutes }) : "–"}</Text>
          <Text style={ui.statLabel}>{t("rider.offer.time")}</Text>
        </View>
        <View style={ui.stat}>
          <Text style={ui.statValue}>{rate ? t("rider.offer.per_hour", { amount: cash(rate, cur, 0) }) : "–"}</Text>
          <Text style={ui.statLabel}>{t("rider.offer.rate")}</Text>
        </View>
      </View>
      <View style={{ gap: 14 }}>
        <View style={styles.stop}>
          <View style={[styles.stopDot, { backgroundColor: night.kesar, borderRadius: radius.pill }]} />
          <View style={{ flex: 1 }}>
            <Text style={ui.bold}>{offer.restaurant_name}</Text>
            <Text style={ui.muted}>
              {[batch ? t("rider.offer.pickup_of", { count: batch.length }) : t("rider.offer.pickup"), dist(offer.distance_km, unit),
                ready == null ? t("rider.offer.being_prepared") : ready <= 0 ? t("rider.offer.ready_now") : t("rider.offer.ready_in", { min: ready }),
                t("rider.offer.bags", { count: bags })].join(" · ")}
            </Text>
          </View>
        </View>
        {batch ? batch.map((b, i) => (
          <View key={b.order_id} style={styles.stop} testID={`offer-drop-${i + 1}`}>
            <View style={[styles.stopDot, { backgroundColor: night.text, borderRadius: 3 }]} />
            <View style={{ flex: 1 }}>
              <Text style={ui.bold}>
                {[t("rider.offer.drop_n", { n: i + 1 }), b.batch_rate ? t("rider.offer.batch_rate") : null].filter(Boolean).join(" · ")}
              </Text>
              <Text style={ui.muted}>{[b.drop_area ? t("rider.offer.near", { area: b.drop_area }) : t("rider.offer.address_after"), b.code,
                b.trip_km != null ? t("rider.offer.from_kitchen", { distance: dist(b.trip_km, unit) }) : null,
                b.rider_pay != null ? t("rider.offer.pay", { amount: cash(b.rider_pay, cur) }) : null].filter(Boolean).join(" · ")}</Text>
            </View>
          </View>
        )) : (
        <View style={styles.stop}>
          <View style={[styles.stopDot, { backgroundColor: night.text, borderRadius: 3 }]} />
          <View style={{ flex: 1 }}>
            <Text style={ui.bold}>{offer.drop_area ? t("rider.offer.near_title", { area: offer.drop_area }) : t("rider.offer.dropoff")}</Text>
            <Text style={ui.muted}>
              {[t("rider.offer.dropoff"), t("rider.offer.further", { distance: dist(offer.trip_km, unit) }), t("rider.offer.address_after")].join(" · ")}
            </Text>
          </View>
        </View>
        )}
      </View>
      {error ? <Text style={[type.label, { color: night.sosText }]}>{error}</Text> : null}
      <View style={{ flexDirection: "row", gap: 10, marginTop: "auto" }}>
        <Pressable testID="offer-pass" accessibilityRole="button" onPress={() => act("pass")} disabled={!!busy} style={styles.pass}>
          <Text style={ui.bold}>{busy === "pass" ? "…" : t("rider.offer.pass")}</Text>
        </Pressable>
        <Pressable testID="offer-accept" accessibilityRole="button" onPress={() => act("accept")} disabled={!!busy || left <= 0} style={[ui.cta, { flex: 1 }]}>
          <Text style={ui.ctaText}>{busy === "accept" ? t("rider.offer.accepting") : t("rider.offer.accept")}</Text>
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
  const { t } = useI18n();
  const c = 2 * Math.PI * 29;
  return (
    <Svg width={68} height={68} viewBox="0 0 68 68" accessibilityLabel={t("rider.offer.seconds_left", { count: left })}>
      <Circle cx={34} cy={34} r={29} fill="none" stroke={night.line} strokeWidth={6} />
      <Circle cx={34} cy={34} r={29} fill="none" stroke={night.kesar} strokeWidth={6} strokeLinecap="round"
        strokeDasharray={`${(c * left) / total} ${c}`} transform="rotate(-90 34 34)" />
      <SvgText x={34} y={40} textAnchor="middle" fontSize={type.h3.fontSize} fontFamily={type.h3.fontFamily} fill={night.text}>{String(left)}</SvgText>
    </Svg>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center", gap: space[3] },
  top: { position: "absolute", left: 16, right: 16, top: 16, flexDirection: "row", justifyContent: "space-between" },
  dot: { width: 9, height: 9, borderRadius: radius.pill },
  panel: { padding: 22, gap: space[3] },
  bg: { padding: 14, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg },
  offer: { height: 470, paddingTop: 26, paddingHorizontal: 22, paddingBottom: 22, gap: 18 },
  pay: { color: night.text, marginTop: 8 },
  statMid: { borderLeftWidth: 1, borderRightWidth: 1, borderColor: night.divider },
  stop: { flexDirection: "row", gap: 14 },
  stopDot: { marginTop: 4, width: 12, height: 12 },
  pass: {
    width: 112, height: 64, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.lineStrong,
    alignItems: "center", justifyContent: "center",
  },
});
