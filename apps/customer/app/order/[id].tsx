// CustomerTracking.html: where the food is, when it arrives, who's bringing it.
// Live from realtime's /ws/track/{order}: a snapshot, then rider assigned,
// location + ETA and status changes. The map is drawn (no map provider key).
import { api, color, QuickChat, radius, space, StatusPill, textFont, Txt, unwrap, wsUrl, type CoreSchemas } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Path, Polyline, Rect } from "react-native-svg";

import { Icon } from "../../lib/icons";

type Order = CoreSchemas["OrderResponse"] & { rider?: { id: string; first_name: string } | null };
type Pt = [number, number];
interface Eta { to_pickup_minutes: number; to_customer_minutes: number; arrives_at: string }
interface Live { status: string; pickup: Pt | null; dropoff: Pt | null; rider: Pt | null; trail: Pt[]; eta: Eta | null; searching: boolean }

const STEPS = [
  { key: "placed", label: "Placed", states: ["placed", "accepted"] },
  { key: "cooked", label: "Cooked", states: ["preparing", "almost_ready", "ready"] },
  { key: "picked", label: "Picked up", states: ["picked_up"] },
  { key: "home", label: "Home", states: ["delivered"] },
];

function clock(iso?: string | null): { time: string; ampm: string } {
  if (!iso) return { time: "--:--", ampm: "" };
  const d = new Date(iso);
  const h = d.getHours();
  return { time: `${h % 12 || 12}:${String(d.getMinutes()).padStart(2, "0")}`, ampm: h < 12 ? "am" : "pm" };
}

export default function Tracking() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [live, setLive] = useState<Live>({ status: "placed", pickup: null, dropoff: null, rider: null, trail: [], eta: null, searching: false });

  useEffect(() => {
    let live_ = true;
    const load = () =>
      api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
        .then((r) => live_ && setOrder(unwrap(r) as Order))
        .catch(() => undefined);
    void load();
    const ws = new WebSocket(wsUrl(`/ws/track/${id}`));
    ws.onmessage = (e) => {
      const m = JSON.parse(String(e.data)) as { type: string; payload: Record<string, unknown> };
      const p = m.payload;
      setLive((s) => {
        switch (m.type) {
          case "connected": {
            const loc = p.location as { lat: number; lng: number } | null;
            return {
              ...s, status: String(p.status ?? s.status), pickup: (p.pickup as Pt) ?? null, dropoff: (p.dropoff as Pt) ?? null,
              rider: loc ? [loc.lat, loc.lng] : null, eta: (p.eta as Eta) ?? null,
              trail: ((p.trail as [number, number, string][]) ?? []).map((t) => [t[0], t[1]] as Pt),
            };
          }
          case "searching_rider":
            return { ...s, searching: true };
          case "rider_assigned":
            void load();
            return { ...s, searching: false, eta: (p.eta as Eta) ?? s.eta };
          case "location_update": {
            const pt: Pt = [Number(p.lat), Number(p.lng)];
            return { ...s, rider: pt, trail: [...s.trail, pt].slice(-200), eta: (p.eta as Eta) ?? s.eta };
          }
          case "status_change":
            void load();
            return { ...s, status: String(p.status ?? s.status) };
          default:
            return s;
        }
      });
    };
    return () => {
      live_ = false;
      ws.close();
    };
  }, [id]);

  const status = order?.status === "delivered" || order?.status === "cancelled" ? order.status : live.status;
  const stepIndex = Math.max(0, STEPS.findIndex((st) => st.states.includes(status)));
  const progress = status === "delivered" ? 1 : [0.12, 0.42, 0.78, 1][stepIndex] ?? 0.12;
  const riderName = order?.rider?.first_name;
  const arrives = clock(live.eta?.arrives_at ?? order?.estimated_delivery_time);
  const headline =
    status === "delivered" ? "Delivered. Enjoy your meal." :
    status === "cancelled" ? "This order was cancelled" :
    status === "picked_up" ? `${riderName ?? "Your rider"} is on the way` :
    riderName ? `${riderName} is heading to the kitchen` :
    status === "placed" ? `${order?.restaurant_name ?? "The kitchen"} has your order` : `${order?.restaurant_name ?? "The kitchen"} is cooking`;
  const stamp = (state: string) => {
    const h = (order?.status_history as { status: string; at: string }[] | undefined)?.find((x) => x.status === state);
    return h ? clock(h.at).time : "";
  };

  return (
    <View style={styles.screen}>
      <TrackMap live={live} />
      <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.canGoBack() ? router.back() : router.replace("/orders")} style={[styles.float, { left: 20 }]}>
        <Icon name="back" />
      </Pressable>
      <View style={[styles.float, { right: 20, width: undefined, paddingHorizontal: 18 }]}>
        <Text style={[textFont("700"), { fontSize: 14 }]}>Help</Text>
      </View>
      <View style={styles.sheet} accessibilityLabel="Order status">
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end" }}>
          <View style={{ flex: 1 }}>
            <Text style={[textFont("600"), { fontSize: 14, color: color.muted }]}>{headline}</Text>
            {status !== "cancelled" ? (
              <Text testID="eta" style={[{ fontFamily: "FamiljenGrotesk_600SemiBold", fontSize: 56, letterSpacing: -2, color: color.kohl, marginTop: 6 }]}>
                {arrives.time}<Text style={{ fontSize: 22, letterSpacing: 0 }}> {arrives.ampm}</Text>
              </Text>
            ) : null}
          </View>
          <Text style={[textFont("400"), { textAlign: "right", fontSize: 13, color: color.muted, lineHeight: 20 }]}>
            {live.eta ? `${live.eta.to_customer_minutes} min` : ""}{"\n"}{live.searching ? "finding a rider" : ""}
          </Text>
        </View>
        <View accessibilityLabel={`Progress: ${STEPS[stepIndex]?.label}, ${stepIndex + 1} of ${STEPS.length} steps`}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${progress * 100}%` }]} />
            <View style={[styles.knob, { left: `${progress * 100}%` }]} />
          </View>
          <View style={styles.steps}>
            {STEPS.map((st, i) => (
              <Text key={st.key} style={[textFont(i === stepIndex ? "800" : "600"), { fontSize: 12, color: i === stepIndex ? color.kohl : color.muted }]}>
                {st.label} {i === 0 ? stamp("placed") : i === 1 ? stamp("preparing") : i === 2 ? stamp("picked_up") : ""}
              </Text>
            ))}
          </View>
        </View>
        {riderName ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
            <View style={styles.avatar}><Text style={[textFont("800"), { fontSize: 17, color: color.peacockDeep }]}>{riderName.slice(0, 2).toUpperCase()}</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={[textFont("800"), { fontSize: 16 }]}>{riderName}</Text>
              <Text style={[textFont("400"), { fontSize: 13, color: color.muted }]}>Your rider</Text>
            </View>
            {/* No calls and no phone numbers: quick messages while the order is on its way (B2). */}
            <QuickChat orderId={id} />
          </View>
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <StatusPill status={status} />
            <Txt variant="small" style={{ color: color.muted }}>{order?.restaurant_name}</Txt>
          </View>
        )}
        {order?.pin && status !== "delivered" && status !== "cancelled" ? (
          <View style={styles.pinRow} accessibilityLabel={`Delivery PIN ${order.pin.split("").join(" ")}. Give it to your rider at the door.`}>
            <Text style={[textFont("600"), { fontSize: 13, color: color.muted, flex: 1 }]}>Give your rider this PIN at the door</Text>
            <Text testID="delivery-pin" style={[textFont("800"), { fontSize: 22, letterSpacing: 6, color: color.kohl }]}>{order.pin}</Text>
          </View>
        ) : null}
        {status === "delivered" ? (
          <Pressable testID="report-problem" accessibilityRole="button" onPress={() => router.push(`/report/${id}`)} style={styles.report}>
            <Text style={[textFont("700"), { fontSize: 15, color: color.peacockDeep }]}>Something wrong? Report a problem</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

/** The route drawn over a plain ground: kitchen, home, the rider and their trail. */
function TrackMap({ live }: { live: Live }) {
  const pts = [live.pickup, live.dropoff, live.rider, ...live.trail].filter(Boolean) as Pt[];
  const W = 390, H = 420, pad = 60;
  if (pts.length === 0) return <View style={{ height: H, backgroundColor: color.mapGround }} />;
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  const [minLat, maxLat, minLng, maxLng] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const span = Math.max(maxLat - minLat, maxLng - minLng, 0.004);
  const xy = (p: Pt): [number, number] => [pad + ((p[1] - minLng) / span) * (W - 2 * pad), H - pad - ((p[0] - minLat) / span) * (H - 2 * pad)];
  return (
    <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} accessibilityLabel="Map of your order's route">
      <Rect width={W} height={H} fill={color.mapGround} />
      {[80, 160, 240, 320].map((y) => <Path key={y} d={`M0 ${y} H${W}`} stroke="#DDE4E4" strokeWidth={10} />)}
      {[70, 190, 310].map((x) => <Path key={x} d={`M${x} 0 V${H}`} stroke="#DDE4E4" strokeWidth={10} />)}
      {live.pickup && live.dropoff ? (
        <Path d={`M${xy(live.pickup).join(" ")} L${xy(live.dropoff).join(" ")}`} stroke={color.lineStrong} strokeWidth={4} strokeDasharray="8 8" />
      ) : null}
      {live.trail.length > 1 ? <Polyline points={live.trail.map((p) => xy(p).join(",")).join(" ")} fill="none" stroke={color.peacock} strokeWidth={5} strokeLinecap="round" /> : null}
      {live.pickup ? <Circle cx={xy(live.pickup)[0]} cy={xy(live.pickup)[1]} r={10} fill={color.kohl} /> : null}
      {live.dropoff ? <Circle cx={xy(live.dropoff)[0]} cy={xy(live.dropoff)[1]} r={10} fill={color.peacock} stroke={color.white} strokeWidth={3} /> : null}
      {live.rider ? <Circle cx={xy(live.rider)[0]} cy={xy(live.rider)[1]} r={12} fill={color.kesar} stroke={color.white} strokeWidth={4} /> : null}
    </Svg>
  );
}

const styles = StyleSheet.create({
  report: { height: 48, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.line, alignItems: "center", justifyContent: "center" },
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
    position: "absolute", left: 0, right: 0, bottom: 0, minHeight: 380, backgroundColor: color.white,
    borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet, padding: space[6], paddingHorizontal: space[5], gap: space[6],
    shadowColor: color.kohl, shadowOpacity: 0.08, shadowRadius: 40, elevation: 12,
  },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: color.divider },
  fill: { height: 8, borderRadius: radius.pill, backgroundColor: color.peacock },
  knob: { position: "absolute", top: -6, width: 20, height: 20, marginLeft: -10, borderRadius: radius.pill, backgroundColor: color.kesar, borderWidth: 3, borderColor: color.white },
  steps: { flexDirection: "row", justifyContent: "space-between", marginTop: 10 },
  avatar: { width: 52, height: 52, borderRadius: radius.pill, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" },
});
