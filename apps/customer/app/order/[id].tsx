// CustomerTracking.html with the website's tracking (Tracking.tsx + LiveMap):
// where the food is, when it arrives, how far is left, who's bringing it.
// Live from realtime's /ws/track/{order}: a snapshot, then rider assigned,
// location + ETA and status changes (a slow poll as a safety net). The map is
// MapLibre over OpenFreeMap's free tiles (components/LiveMap.tsx).
import { api, color, inZone, LoadError, loadFailure, QuickChat, radius, space, StatusPill, Txt, type, unwrap, useI18n, liveSocket } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { CancelOrder, RefundLine } from "../../components/CancelOrder";
import { LiveMap } from "../../components/LiveMap";
import { distanceLeft, nextStop, riderFirstName, trackHeadline, type Eta, type Order, type Pt } from "../../lib/contract";
import { Icon } from "../../lib/icons";

interface Live { status: string | null; pickup: Pt | null; dropoff: Pt | null; rider: Pt | null; trail: Pt[]; eta: Eta | null; searching: boolean; assigned: boolean; slow: boolean }

const STEPS = [
  { key: "placed", label: "app.track.step_placed", states: ["pending_payment", "placed", "accepted"] },
  { key: "cooking", label: "app.track.step_cooking", states: ["preparing", "almost_ready", "ready"] },
  { key: "picked", label: "app.track.step_picked", states: ["picked_up"] },
  { key: "home", label: "app.track.step_home", states: ["delivered"] },
];
// R33: a pickup order: Placed -> Preparing -> Ready for pickup -> Picked up (no "Home": the customer collects it).
const PICKUP_STEPS = [
  { key: "placed", label: "app.track.step_placed", states: ["pending_payment", "placed", "accepted"] },
  { key: "preparing", label: "account.status.preparing", states: ["preparing", "almost_ready"] },
  { key: "ready", label: "track.s_pickup_ready", states: ["ready"] },
  { key: "collected", label: "app.track.step_picked", states: ["delivered"] },
];

const SHEET = 400; // the sheet's height over the map's bottom

export default function Tracking() {
  const { t, time, number, distance } = useI18n();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { height: screen } = useWindowDimensions();
  // Under the test banner this top inset is 0 (the banner has the status bar); in production it is the status bar.
  const { top: safeTop } = useSafeAreaInsets();
  const floatTop = safeTop + space[3];
  const [order, setOrder] = useState<Order | null>(null);
  /** What the order's load threw: 403/404 is "not found"; anything else (offline, our servers) gets Retry. */
  const [failure, setFailure] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [live, setLive] = useState<Live>({ status: null, pickup: null, dropoff: null, rider: null, trail: [], eta: null, searching: false, assigned: false, slow: false });

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
        .then((r) => {
          if (!alive) return;
          setOrder(unwrap(r) as Order);
          setFailure(null);
        })
        .catch((e: unknown) => alive && setFailure(e));
    void load();
    // Live; reopens with a fresh token when realtime closes it at the token's expiry (R22 S10).
    const stopSocket = liveSocket(`/ws/track/${id}`, (e) => {
      let m: { type: string; payload: Record<string, unknown> };
      try {
        m = JSON.parse(String(e.data)) as typeof m;
      } catch {
        return;
      }
      const p = m.payload ?? {};
      if (m.type === "rider_assigned" || m.type === "status_change") void load();
      setLive((s) => {
        switch (m.type) {
          case "connected": {
            const loc = p.location as { lat: number; lng: number } | null;
            return {
              ...s, status: (p.status as string) ?? s.status, pickup: (p.pickup as Pt) ?? null, dropoff: (p.dropoff as Pt) ?? null,
              rider: loc ? [loc.lat, loc.lng] : null, eta: (p.eta as Eta) ?? null,
              trail: ((p.trail as [number, number, string][]) ?? []).map((x) => [x[0], x[1]] as Pt),
              slow: !!p.searching_slow,
            };
          }
          case "searching_rider":
            return { ...s, searching: true };
          case "partner_search_slow": // R28: no partner after the city's minutes: said honestly, with the later time
            return { ...s, slow: true, eta: (p.eta as Eta) ?? s.eta };
          case "rider_assigned":
            return { ...s, searching: false, assigned: true, slow: false, eta: (p.eta as Eta) ?? s.eta };
          case "location_update": {
            const pt: Pt = [Number(p.lat), Number(p.lng)];
            return { ...s, rider: pt, trail: [...s.trail, pt].slice(-200), eta: (p.eta as Eta) ?? s.eta };
          }
          case "status_change":
            return { ...s, status: (p.status as string) ?? s.status };
          case "eta_update": // realtime recomputes the ETA from the rider's last fix on a status change
            return { ...s, status: (p.status as string) ?? s.status, eta: (p.eta as Eta) ?? s.eta };
          default:
            return s;
        }
      });
    });
    const poll = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(poll);
      stopSocket();
    };
  }, [id, attempt]);

  const back = () => (router.canGoBack() ? router.back() : router.replace("/orders"));

  if (failure && !order && loadFailure(failure) !== "refused") {
    return (
      <View style={[styles.screen, { padding: space[6] }]}>
        <LoadError error={failure} onRetry={() => setAttempt((a) => a + 1)} fill />
      </View>
    );
  }
  if (failure && !order) {
    return (
      <View style={[styles.screen, { alignItems: "center", justifyContent: "center", padding: space[6], gap: space[4] }]}>
        <Txt variant="h2" style={{ textAlign: "center" }}>{t("track.not_found")}</Txt>
        <Pressable accessibilityRole="button" onPress={() => router.replace("/orders")} style={styles.report}>
          <Text style={[type.label, { color: color.peacockDeep, paddingHorizontal: space[5] }]}>{t("track.your_orders")}</Text>
        </Pressable>
      </View>
    );
  }

  const status = order?.status === "delivered" || order?.status === "cancelled" || !live.status ? (order?.status ?? "placed") : live.status;
  const delivered = status === "delivered";
  const cancelled = status === "cancelled";
  const finished = delivered || cancelled;
  const steps = order?.fulfillment === "pickup" ? PICKUP_STEPS : STEPS;
  const stepIndex = Math.max(0, steps.findIndex((st) => st.states.includes(status)));
  const progress = delivered ? 1 : [0.12, 0.42, 0.78, 1][stepIndex] ?? 0.12;
  // R28: a partner who accepted is heading to the kitchen at once, named or not ("Your delivery partner"):
  // never "Finding a delivery partner" after someone took the order (rider_assigned reloads the order).
  const assigned = !!order?.driver_id || !!order?.rider || live.assigned;
  const rider = riderFirstName(order);
  const who = rider ?? (assigned ? t("track.your_rider") : null);
  const kitchen = order?.restaurant_name ?? "";
  const tz = inZone(order?.time_zone); // the order's city clock, never the phone's
  const pickup = live.pickup ?? (order?.pickup_lat != null && order.pickup_lng != null ? [order.pickup_lat, order.pickup_lng] as Pt : null);
  const dropoff = live.dropoff ?? (order?.delivery_lat != null && order.delivery_lng != null ? [order.delivery_lat, order.delivery_lng] as Pt : null);
  const riderAt = finished ? null : live.rider;
  const next = finished ? null : nextStop(status, pickup, dropoff);
  const estimate = live.eta?.arrives_at ?? order?.estimated_delivery_time ?? null;
  const minutes = live.eta ? live.eta.to_customer_minutes : estimate ? Math.max(1, Math.round((Date.parse(estimate) - now) / 60000)) : null;
  // "Around …" is never in the past: a stale estimate moves to now + the minutes left.
  const arrivesAt = estimate && minutes != null ? new Date(Math.max(Date.parse(estimate), now + minutes * 60000)).toISOString() : estimate;
  const left = finished ? null : distanceLeft(live.eta, riderAt, next);
  const leftText = left ? (left.km ? distance(left.value) : t(`app.units.${left.unit}`, { value: number(left.value, 1) })) : null;

  const [headKey, headValues] = trackHeadline(status, who, kitchen);
  const headline = order?.fulfillment === "pickup" && status === "ready" ? t("track.s_pickup_ready")  // R32
    : headKey === "s_picked_up" && !headValues
    ? t("track.s_picked_up", { rider: t("track.your_rider") }) : t(`track.${headKey}`, headValues);
  const stamp = (...states: string[]) => {
    const h = (order?.status_history as { status: string; at: string }[] | undefined)?.find((x) => states.includes(x.status));
    return h ? time(h.at, tz) : "";
  };
  const stamps = steps === PICKUP_STEPS
    ? [stamp("placed"), stamp("accepted", "preparing"), stamp("ready"), stamp("delivered")]
    : [stamp("placed"), stamp("accepted", "preparing"), stamp("picked_up"), stamp("delivered")];
  // The door PIN only once the rider has the food (R27; the API holds it back before that too).
  const pin = order?.pin && status === "picked_up" ? order.pin : null;
  const mapHeight = Math.max(360, screen - SHEET + 40);

  return (
    <View testID="tracking" style={styles.screen}>
      <LiveMap
        pickup={pickup}
        dropoff={dropoff}
        rider={riderAt}
        trail={live.trail}
        leg={finished ? null : status === "picked_up" ? "home" : "kitchen"}
        height={mapHeight}
        coverBottom={40}
        coverTop={floatTop + 44}
        labels={{ map: t("track.map"), kitchen: t("track.map_kitchen", { kitchen }), home: t("track.map_home"), rider: rider ? t("track.map_rider", { rider }) : t("track.your_rider") }}
      />
      <Pressable accessibilityRole="button" accessibilityLabel={t("track.back")} onPress={back} style={[styles.float, { top: floatTop, left: 20 }]}>
        <Icon name="back" />
      </Pressable>
      {delivered ? (
        <Pressable accessibilityRole="button" onPress={() => router.push(`/report/${id}`)} style={[styles.float, { top: floatTop, right: 20, width: undefined, paddingHorizontal: 18 }]}>
          <Text style={type.label}>{t("track.help")}</Text>
        </Pressable>
      ) : null}
      <ScrollView style={styles.sheet} contentContainerStyle={{ padding: space[6], paddingHorizontal: space[5], gap: space[5] }} accessibilityLabel={t("track.status")}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text testID="track-headline" style={[type.label, { color: color.muted }]}>{headline}</Text>
            {!cancelled ? (
              <Text testID="eta" style={[type.display, { color: color.kohl, marginTop: 6 }]}>
                {delivered ? t("track.delivered") : minutes != null ? t("track.minutes", { count: minutes }) : "—"}
              </Text>
            ) : null}
            {!finished && arrivesAt ? (
              <Text style={[type.small, { color: color.muted }]}>{t("track.around", { time: time(arrivesAt, tz) })}</Text>
            ) : null}
          </View>
          <View style={{ alignItems: "flex-end", gap: 2 }}>
            {leftText ? <Text testID="distance-left" style={[type.label, { color: color.kohl }]}>{t("track.away", { left: leftText })}</Text> : null}
            {live.slow && !assigned ? <Text testID="slow-search" style={[type.small, { color: color.chili, maxWidth: 220, textAlign: "right" }]}>{t("track.s_slow_search")}</Text> : null}
            {live.searching && !live.slow && !assigned ? <Text style={[type.small, { color: color.muted }]}>{t("track.s_finding")}</Text> : null}
          </View>
        </View>
        <View testID={steps === PICKUP_STEPS ? "pickup-steps" : "delivery-steps"}
          accessibilityLabel={t("app.track.progress", { step: t(steps[stepIndex]?.label ?? "app.track.step_placed"), n: stepIndex + 1, total: steps.length })}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${progress * 100}%` }]} />
            <View style={[styles.knob, { left: `${progress * 100}%` }]} />
          </View>
          <View style={styles.steps}>
            {steps.map((st, i) => (
              <Text key={st.key} testID={`step-${st.key}`} style={[type.small, { flex: 1, color: i === stepIndex ? color.kohl : color.muted, textAlign: "center" }]}>
                {t(st.label)}{stamps[i] ? `\n${stamps[i]}` : ""}
              </Text>
            ))}
          </View>
        </View>
        {rider ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }} accessibilityLabel={t("track.rider_card", { rider })}>
            <View style={styles.avatar}><Text style={[type.h3, { color: color.peacockDeep }]}>{rider.slice(0, 2).toUpperCase()}</Text></View>
            <View style={{ flex: 1 }}>
              <Text testID="rider-name" style={type.label}>{rider}</Text>
              <Text style={[type.small, { color: color.muted }]}>{t("track.your_rider")}</Text>
            </View>
            {/* No calls and no phone numbers: quick messages while the order is on its way (B2). */}
            {!finished ? <QuickChat orderId={id} /> : null}
          </View>
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <StatusPill status={status} />
            <Txt variant="small" style={{ color: color.muted }}>{kitchen}</Txt>
          </View>
        )}
        {pin ? (
          <View style={styles.pinRow} accessibilityLabel={t("app.track.pin_a11y", { pin: pin.split("").join(" ") })}>
            <Text style={[type.small, { color: color.muted, flex: 1 }]}>{t("track.pin_long")}</Text>
            <Text testID="delivery-pin" style={[type.h2, { letterSpacing: 6, color: color.kohl }]}>{pin}</Text>
          </View>
        ) : null}
        {/* R32: a pickup order: where to collect it, and the code once it's ready */}
        {order?.fulfillment === "pickup" && !cancelled ? (
          <View testID="pickup-card" style={styles.pinRow}>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={[type.small, { color: color.muted }]}>{t("checkout.pickup_at")}</Text>
              <Text style={type.label}>{[order.pickup_address?.street, order.pickup_address?.city].filter(Boolean).join(", ") || kitchen}</Text>
              {order.pickup_address?.lat != null && order.pickup_address?.lng != null ? (
                <Pressable accessibilityRole="link" hitSlop={8} onPress={() => void Linking.openURL(
                  `https://www.google.com/maps/search/?api=1&query=${String(order.pickup_address?.lat)},${String(order.pickup_address?.lng)}`)}>
                  <Text style={[type.label, { color: color.peacock }]}>{t("checkout.open_in_maps")}</Text>
                </Pressable>
              ) : null}
              <Text style={[type.small, { color: order.pickup_locked ? color.chili : color.muted }]}>
                {delivered ? t("track.collected") : order.pickup_locked ? t("track.pickup_locked")
                  : order.pickup_code ? t("track.pickup_code_note") : t("track.pickup_waiting")}
              </Text>
            </View>
            {order.pickup_code && !delivered && !order.pickup_locked ? (
              <View style={{ alignItems: "flex-end" }} accessibilityLabel={`${t("track.pickup_code")} ${order.pickup_code.split("").join(" ")}`}>
                <Text style={[type.caption, { color: color.muted }]}>{t("track.pickup_code")}</Text>
                <Text testID="pickup-code" style={[type.h2, { letterSpacing: 6, color: color.kohl }]}>{order.pickup_code}</Text>
              </View>
            ) : null}
          </View>
        ) : null}
        {/* R8: cancel while the API says the customer may; after it, the refund line */}
        {!finished && order ? (
          <CancelOrder order={order} onDone={setOrder} onRefresh={() => {
            api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
              .then((r) => setOrder(unwrap(r) as Order)).catch(() => undefined);
          }} />
        ) : null}
        {cancelled && order ? <RefundLine order={order} /> : null}
        {delivered ? (
          <Pressable testID="report-problem" accessibilityRole="button" onPress={() => router.push(`/report/${id}`)} style={styles.report}>
            <Text style={[type.label, { color: color.peacockDeep }]}>{t("track.report")}</Text>
          </Pressable>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  report: { minHeight: 48, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.line, alignItems: "center", justifyContent: "center", paddingHorizontal: space[4] },
  pinRow: {
    flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 16,
    backgroundColor: color.peacockMist,
  },
  screen: { flex: 1, backgroundColor: color.mapGround },
  float: {
    position: "absolute", width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center", shadowColor: color.kohl, shadowOpacity: 0.1, shadowRadius: 14, elevation: 4,
  },
  sheet: {
    position: "absolute", left: 0, right: 0, bottom: 0, height: SHEET, backgroundColor: color.white,
    borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet,
    shadowColor: color.kohl, shadowOpacity: 0.08, shadowRadius: 40, elevation: 12,
  },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: color.divider },
  fill: { height: 8, borderRadius: radius.pill, backgroundColor: color.peacock },
  knob: { position: "absolute", top: -6, width: 20, height: 20, marginLeft: -10, borderRadius: radius.pill, backgroundColor: color.kesar, borderWidth: 3, borderColor: color.white },
  steps: { flexDirection: "row", justifyContent: "space-between", marginTop: 10 },
  avatar: { width: 52, height: 52, borderRadius: radius.pill, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" },
});
