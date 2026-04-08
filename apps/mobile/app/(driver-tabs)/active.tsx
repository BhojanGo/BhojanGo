import { useState, useEffect } from "react";
import { View, Text, TouchableOpacity, StyleSheet, Linking, Alert } from "react-native";
import { api } from "@/src/lib/api";

type ActiveDelivery = {
  id: string;
  order_id: string;
  restaurant_name: string;
  restaurant_address: { street: string; city: string; lat: number; lng: number };
  delivery_address: { street: string; city: string; lat: number; lng: number };
  customer_name: string;
  status: string;
  items_count: number;
  total: number;
  currency: string;
};

export default function ActiveDelivery() {
  const [delivery, setDelivery] = useState<ActiveDelivery | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchActive = async () => {
    try {
      const res = await api.get("/order/orders/driver/active");
      setDelivery(res.data || null);
    } catch {
      setDelivery(null);
    }
    setLoading(false);
  };

  useEffect(() => { fetchActive(); }, []);

  const updateStatus = async (newStatus: string) => {
    if (!delivery) return;
    try {
      await api.put(`/order/orders/${delivery.order_id}/status`, { status: newStatus });
      fetchActive();
    } catch (e: any) {
      Alert.alert("Error", "Failed to update status");
    }
  };

  const openMaps = (lat: number, lng: number) => {
    Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`);
  };

  if (loading) return <View style={styles.center}><Text>Loading...</Text></View>;
  if (!delivery) return <View style={styles.center}><Text style={styles.noDelivery}>No active delivery</Text></View>;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Active Delivery</Text>
        <Text style={styles.status}>{delivery.status.replace("_", " ").toUpperCase()}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Restaurant</Text>
        <Text style={styles.value}>{delivery.restaurant_name}</Text>
        <Text style={styles.address}>{delivery.restaurant_address?.street}</Text>
        <TouchableOpacity
          style={styles.navBtn}
          onPress={() => openMaps(delivery.restaurant_address?.lat, delivery.restaurant_address?.lng)}
        >
          <Text style={styles.navBtnText}>Navigate to Restaurant</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Customer</Text>
        <Text style={styles.value}>{delivery.customer_name}</Text>
        <Text style={styles.address}>{delivery.delivery_address?.street}, {delivery.delivery_address?.city}</Text>
        <TouchableOpacity
          style={styles.navBtn}
          onPress={() => openMaps(delivery.delivery_address?.lat, delivery.delivery_address?.lng)}
        >
          <Text style={styles.navBtnText}>Navigate to Customer</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.actions}>
        {delivery.status === "ready_for_pickup" && (
          <TouchableOpacity style={styles.actionBtn} onPress={() => updateStatus("picked_up")}>
            <Text style={styles.actionBtnText}>Confirm Pickup</Text>
          </TouchableOpacity>
        )}
        {delivery.status === "picked_up" && (
          <TouchableOpacity style={styles.actionBtn} onPress={() => updateStatus("delivered")}>
            <Text style={styles.actionBtnText}>Confirm Delivery</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  noDelivery: { fontSize: 16, color: "#9CA3AF" },
  header: { padding: 20, paddingTop: 60, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#E5E7EB", flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontSize: 22, fontWeight: "bold", color: "#111827" },
  status: { fontSize: 14, fontWeight: "600", color: "#059669", backgroundColor: "#ECFDF5", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  card: { backgroundColor: "#fff", margin: 12, padding: 16, borderRadius: 12, borderWidth: 1, borderColor: "#E5E7EB" },
  label: { fontSize: 12, color: "#9CA3AF", textTransform: "uppercase", fontWeight: "600" },
  value: { fontSize: 18, fontWeight: "600", color: "#111827", marginTop: 4 },
  address: { fontSize: 14, color: "#6B7280", marginTop: 4 },
  navBtn: { backgroundColor: "#EFF6FF", padding: 12, borderRadius: 8, marginTop: 12, alignItems: "center" },
  navBtnText: { color: "#2563EB", fontSize: 14, fontWeight: "600" },
  actions: { padding: 12 },
  actionBtn: { backgroundColor: "#059669", padding: 16, borderRadius: 12, alignItems: "center", marginTop: 8 },
  actionBtnText: { color: "#fff", fontSize: 18, fontWeight: "bold" },
});
