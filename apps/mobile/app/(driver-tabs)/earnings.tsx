import { useState, useEffect } from "react";
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { api } from "@/lib/api";

interface Breakdown {
  gross_earnings: number;
  net_earnings: number;
  floor_guarantee: number;
  floor_topup: number;
  mileage_payout: number;
  waiting_time_payout: number;
  active_payout: number;
  order_bonus: number;
  tips: number;
  deductions: number;
}

interface Shift {
  online: boolean;
  status?: string;
  available_minutes: number;
  active_minutes: number;
  waiting_minutes: number;
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, strong && styles.rowStrong]}>{label}</Text>
      <Text style={[styles.rowValue, strong && styles.rowStrong]}>{value}</Text>
    </View>
  );
}

export default function Earnings() {
  const [earnings, setEarnings] = useState({ today: 0, week: 0, month: 0, deliveries_today: 0 });
  const [shift, setShift] = useState<Shift | null>(null);
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      let deliveriesToday = 0;
      let shiftData: Shift | null = null;
      try {
        const [eRes, sRes] = await Promise.allSettled([
          api.get("/delivery/driver/earnings"),
          api.get("/delivery/drivers/me/shift"),
        ]);
        if (eRes.status === "fulfilled") {
          deliveriesToday = eRes.value.data.deliveries_today ?? 0;
          if (active) setEarnings(eRes.value.data);
        }
        if (sRes.status === "fulfilled") shiftData = sRes.value.data;
        if (active) setShift(shiftData);

        // Live earnings breakdown from the shift's tracked minutes + today's deliveries.
        const est = await api.post("/delivery/drivers/me/earnings/estimate", {
          available_minutes: shiftData?.available_minutes ?? 0,
          active_minutes: shiftData?.active_minutes ?? 0,
          waiting_minutes: shiftData?.waiting_minutes ?? 0,
          num_orders: deliveriesToday,
          miles: 0,
          tips: 0,
          deductions: 0,
        });
        if (active) setBreakdown(est.data);
      } catch {
        // best-effort dashboard; cards fall back to defaults
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const money = (n: number) => `$${n.toFixed(2)}`;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 32 }}>
      <Text style={styles.title}>Earnings</Text>

      <View style={styles.grid}>
        <View style={styles.card}>
          <Text style={styles.label}>Today</Text>
          <Text style={styles.amount}>{money(earnings.today)}</Text>
          <Text style={styles.sub}>{earnings.deliveries_today} deliveries</Text>
        </View>
        <View style={styles.row2}>
          <View style={[styles.card, styles.half]}>
            <Text style={styles.label}>This Week</Text>
            <Text style={styles.amountSm}>{money(earnings.week)}</Text>
          </View>
          <View style={[styles.card, styles.half]}>
            <Text style={styles.label}>This Month</Text>
            <Text style={styles.amountSm}>{money(earnings.month)}</Text>
          </View>
        </View>
      </View>

      {/* Current shift */}
      <View style={styles.card}>
        <View style={styles.shiftHeader}>
          <Text style={styles.sectionTitle}>Current Shift</Text>
          <View style={[styles.badge, shift?.online ? styles.badgeOn : styles.badgeOff]}>
            <Text style={styles.badgeText}>{shift?.online ? "ONLINE" : "OFFLINE"}</Text>
          </View>
        </View>
        <Row label="Available time" value={`${shift?.available_minutes ?? 0} min`} />
        <Row label="Active (on delivery)" value={`${shift?.active_minutes ?? 0} min`} />
        <Row label="Waiting / idle" value={`${shift?.waiting_minutes ?? 0} min`} />
      </View>

      {/* Earnings breakdown (driver earnings protection) */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Earnings Breakdown</Text>
        {loading ? (
          <ActivityIndicator color="#059669" style={{ marginTop: 12 }} />
        ) : breakdown ? (
          <>
            <Row label="Active-time pay" value={money(breakdown.active_payout)} />
            <Row label="Waiting-time pay" value={money(breakdown.waiting_time_payout)} />
            <Row label="Mileage" value={money(breakdown.mileage_payout)} />
            <Row label="Order bonus" value={money(breakdown.order_bonus)} />
            {breakdown.floor_topup > 0 && (
              <Row label={`Guaranteed-floor top-up`} value={money(breakdown.floor_topup)} />
            )}
            <Row label="Tips" value={money(breakdown.tips)} />
            {breakdown.deductions > 0 && (
              <Row label="Deductions" value={`- ${money(breakdown.deductions)}`} />
            )}
            <View style={styles.divider} />
            <Row label="Net earnings" value={money(breakdown.net_earnings)} strong />
            <Text style={styles.note}>
              Minimum guaranteed: {money(breakdown.floor_guarantee)} for your available time.
            </Text>
          </>
        ) : (
          <Text style={styles.sub}>No shift data yet. Go online to start earning.</Text>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB", padding: 20, paddingTop: 60 },
  title: { fontSize: 24, fontWeight: "bold", color: "#111827", marginBottom: 20 },
  grid: { gap: 12, marginBottom: 12 },
  row2: { flexDirection: "row", gap: 12 },
  half: { flex: 1 },
  card: { backgroundColor: "#fff", padding: 20, borderRadius: 12, borderWidth: 1, borderColor: "#E5E7EB", marginBottom: 12 },
  label: { fontSize: 14, color: "#9CA3AF", textTransform: "uppercase", fontWeight: "600" },
  amount: { fontSize: 32, fontWeight: "bold", color: "#059669", marginTop: 8 },
  amountSm: { fontSize: 22, fontWeight: "bold", color: "#059669", marginTop: 6 },
  sub: { fontSize: 14, color: "#6B7280", marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#111827" },
  shiftHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  badgeOn: { backgroundColor: "#D1FAE5" },
  badgeOff: { backgroundColor: "#F3F4F6" },
  badgeText: { fontSize: 11, fontWeight: "700", color: "#065F46" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  rowLabel: { fontSize: 14, color: "#6B7280" },
  rowValue: { fontSize: 14, color: "#111827", fontWeight: "500" },
  rowStrong: { fontWeight: "700", color: "#059669", fontSize: 16 },
  divider: { height: 1, backgroundColor: "#F3F4F6", marginVertical: 8 },
  note: { fontSize: 12, color: "#9CA3AF", marginTop: 8 },
});
