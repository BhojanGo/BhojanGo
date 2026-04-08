import { useState, useEffect } from "react";
import { View, Text, StyleSheet } from "react-native";
import { api } from "@/lib/api";

export default function Earnings() {
  const [earnings, setEarnings] = useState({ today: 0, week: 0, month: 0, deliveries_today: 0 });

  useEffect(() => {
    api.get("/delivery/driver/earnings")
      .then((res) => setEarnings(res.data))
      .catch(() => {});
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Earnings</Text>
      <View style={styles.grid}>
        <View style={styles.card}>
          <Text style={styles.label}>Today</Text>
          <Text style={styles.amount}>${earnings.today.toFixed(2)}</Text>
          <Text style={styles.sub}>{earnings.deliveries_today} deliveries</Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.label}>This Week</Text>
          <Text style={styles.amount}>${earnings.week.toFixed(2)}</Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.label}>This Month</Text>
          <Text style={styles.amount}>${earnings.month.toFixed(2)}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB", padding: 20, paddingTop: 60 },
  title: { fontSize: 24, fontWeight: "bold", color: "#111827", marginBottom: 20 },
  grid: { gap: 12 },
  card: { backgroundColor: "#fff", padding: 20, borderRadius: 12, borderWidth: 1, borderColor: "#E5E7EB" },
  label: { fontSize: 14, color: "#9CA3AF", textTransform: "uppercase", fontWeight: "600" },
  amount: { fontSize: 32, fontWeight: "bold", color: "#059669", marginTop: 8 },
  sub: { fontSize: 14, color: "#6B7280", marginTop: 4 },
});
