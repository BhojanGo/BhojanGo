// CustomerTracking.html with the website's tracking (Tracking.tsx + LiveMap):
// where the food is, when it arrives, how far is left, who's bringing it.
// Live from realtime's /ws/track/{order}: a snapshot, then rider assigned,
// location + ETA and status changes (a slow poll as a safety net). The map is
// MapLibre over OpenFreeMap's free tiles (components/LiveMap.tsx).
import { api, color, inZone, QuickChat, radius, space, StatusPill, Txt, type, unwrap, useI18n, wsUrl } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";

import { LiveMap } from "../../components/LiveMap";
import { distanceLeft, nextStop, riderFirstName, type Eta, type Order, type Pt } from "../../lib/contract";
import { Icon } from "../../lib/icons";

interface Live { status: string | null; pickup: Pt | null; dropoff: Pt | null; rider: Pt | null; trail: Pt[]; eta: Eta | null; searching: boolean }

const STEPS = [
  { key: "placed", states: ["pending_payment", "placed", "accepted"] },
  { key: "cooking", states: ["preparing", "almost_ready", "ready"] },
  { key: "picked", states: ["picked_up"] },
  { key: "home", states: ["delivered"] },
];

const SHEET = 400; // the sheet's height over the map's bottom

export default function Tracking() {
  const { t, time, number, distance } = useI18n();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { height: screen } = useWindowDimensions();
  const [order, setOrder] = useState<Order | null>(null);
  const [missing, setMissing] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [live, setLive] = useState<Live>({ status: null, pickup: null, dropoff: null, rider: null, trail: [], eta: null, searching: false });

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
        .then((r) => alive && setOrder(unwrap(r) as Order))
        .catch(() => alive && setMissing(true));
    void load();
    const ws = new WebSocket(wsUrl(`/ws/track/${id}`));
    ws.onmessage = (e) => {
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
            };
          }
          case "searching_rider":
            return { ...s, searching: true };
          case "rider_assigned":
            return { ...s, searching: false, eta: (p.eta as Eta) ?? s.eta };
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
    };
    const poll = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(poll);
      ws.close();
    };
  }, [id]);

  const back = () => (router.canGoBack() ? router.back() : router.replace("/orders"));

  if (missing && !order) {
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
  const stepIndex = Math.max(0, STEPS.findIndex((st) => st.states.includes(status)));
  const progress = delivered ? 1 : [0.12, 0.42, 0.78, 1][stepIndex] ?? 0.12;
  const rider = riderFirstName(order);
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

  const headline =
    cancelled ? t("track.s_cancelled") :
    delivered ? t("track.s_delivered") :
    status === "pending_payment" ? t("track.s_payment") :
    status === "picked_up" ? t("track.s_picked_up", { rider: rider ?? t("track.your_rider") }) :
    status === "ready" ? (rider ? t("track.s_heading", { rider }) : t("track.s_finding")) :
    rider ? t("track.s_heading", { rider }) :
    status === "placed" ? t("track.s_placed", { kitchen }) : t("track.s_cooking", { kitchen });
  const stamp = (...states: string[]) => {
    const h = (order?.status_history as { status: string; at: string }[] | undefined)?.find((x) => states.includes(x.status));
    return h ? time(h.at, tz) : "";
  };
  const stamps = [stamp("placed"), stamp("accepted", "preparing"), stamp("picked_up"), stamp("delivered")];
  const pin = order?.pin && !finished ? order.pin : null;
  const mapHeight = Math.max(360, screen - SHEET + 40);

  return (
    <View testID="tracking" style={styles.screen}>
      <LiveMap
        pickup={pickup}
        dropoff={dropoff}
        rider={riderAt}
        trail={live.trail}
        next={next}
        height={mapHeight}
        coverBottom={40}
        labels={{ map: t("track.map"), kitchen: t("track.map_kitchen", { kitchen }), home: t("track.map_home"), rider: rider ? t("track.map_rider", { rider }) : t("track.your_rider") }}
      />
      <Pressable accessibilityRole="button" accessibilityLabel={t("track.back")} onPress={back} style={[styles.float, { left: 20 }]}>
        <Icon name="back" />
      </Pressable>
      {delivered ? (
        <Pressable accessibilityRole="button" onPress={() => router.push(`/report/${id}`)} style={[styles.float, { right: 20, width: undefined, paddingHorizontal: 18 }]}>
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
            {live.searching && !rider ? <Text style={[type.small, { color: color.muted }]}>{t("track.s_finding")}</Text> : null}
          </View>
        </View>
        <View accessibilityLabel={t("app.track.progress", { step: t(`app.track.step_${STEPS[stepIndex]?.key ?? "placed"}`), n: stepIndex + 1, total: STEPS.length })}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${progress * 100}%` }]} />
            <View style={[styles.knob, { left: `${progress * 100}%` }]} />
          </View>
          <View style={styles.steps}>
            {STEPS.map((st, i) => (
              <Text key={st.key} style={[type.small, { flex: 1, color: i === stepIndex ? color.kohl : color.muted, textAlign: "center" }]}>
                {t(`app.track.step_${st.key}`)}{stamps[i] ? `\n${stamps[i]}` : ""}
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
    position: "absolute", top: 48, width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white,
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
