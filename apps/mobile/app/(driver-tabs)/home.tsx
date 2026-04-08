import { useState, useEffect } from "react";
import { View, Text, FlatList, TouchableOpacity, Switch, StyleSheet } from "react-native";
import * as Location from "expo-location";
import { api } from "@/src/lib/api";

type Order = {
  id: string;
  restaurant_name: string;
  delivery_address: { street: string; city: string };
  total: number;
  currency: string;
  status: string;
};

export default function DriverHome() {
  const [isOnline, setIsOnline] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOnline) return;
    let interval: NodeJS.Timeout;

    const startTracking = async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") return;

      interval = setInterval(async () => {
        const loc = await Location.getCurrentPositionAsync({});
        try {
          await api.post("/delivery/driver/location", {
            latitude: loc.coords.latitude,
            longitude: loc.coords.longitude,
          });
        } catch {}
      }, 10000);

      fetchOrders();
    };

    startTracking();
    return () => clearInterval(interval);
  }, [isOnline]);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const res = await api.get("/order/orders/driver/available");
      setOrders(res.data.orders || []);
    } catch {}
    setLoading(false);
  };

  const acceptOrder = async (orderId: string) => {
    try {
      await api.post(`/delivery/orders/${orderId}/accept`);
      fetchOrders();
    } catch {}
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Driver Dashboard</Text>
        <View style={styles.toggleRow}>
          <Text style={styles.statusText}>{isOnline ? "Online" : "Offline"}</Text>
          <Switch
            value={isOnline}
            onValueChange={setIsOnline}
            trackColor={{ true: "#059669", false: "#D1D5DB" }}
            thumbColor="#fff"
          />
        </View>
      </View>

      {!isOnline ? (
        <View style={styles.offlineMsg}>
          <Text style={styles.offlineText}>Go online to see available orders</Text>
        </View>
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(item) => item.id}
          onRefresh={fetchOrders}
          refreshing={loading}
          ListEmptyComponent={<Text style={styles.emptyText}>No orders available nearby</Text>}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.restaurantName}>{item.restaurant_name}</Text>
              <Text style={styles.address}>{item.delivery_address?.street}, {item.delivery_address?.city}</Text>
              <Text style={styles.total}>{item.currency === "INR" ? "\u20B9" : "$"}{item.total?.toFixed(2)}</Text>
              <TouchableOpacity style={styles.acceptBtn} onPress={() => acceptOrder(item.id)}>
                <Text style={styles.acceptBtnText}>Accept Order</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  header: { padding: 20, paddingTop: 60, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#E5E7EB" },
  title: { fontSize: 24, fontWeight: "bold", color: "#111827" },
  toggleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 12 },
  statusText: { fontSize: 16, color: "#6B7280" },
  offlineMsg: { flex: 1, justifyContent: "center", alignItems: "center" },
  offlineText: { fontSize: 16, color: "#9CA3AF" },
  emptyText: { textAlign: "center", marginTop: 40, color: "#9CA3AF", fontSize: 16 },
  card: { backgroundColor: "#fff", margin: 12, padding: 16, borderRadius: 12, borderWidth: 1, borderColor: "#E5E7EB" },
  restaurantName: { fontSize: 18, fontWeight: "600", color: "#111827" },
  address: { fontSize: 14, color: "#6B7280", marginTop: 4 },
  total: { fontSize: 16, fontWeight: "bold", color: "#059669", marginTop: 8 },
  acceptBtn: { backgroundColor: "#059669", padding: 12, borderRadius: 8, marginTop: 12, alignItems: "center" },
  acceptBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
