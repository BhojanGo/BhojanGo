import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useAuth } from "@/src/store/auth";
import { router } from "expo-router";

export default function DriverProfile() {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.replace("/(auth)/login");
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Profile</Text>
      <View style={styles.card}>
        <Text style={styles.name}>{user?.full_name || "Driver"}</Text>
        <Text style={styles.email}>{user?.email || ""}</Text>
        <Text style={styles.role}>Driver</Text>
      </View>
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Logout</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB", padding: 20, paddingTop: 60 },
  title: { fontSize: 24, fontWeight: "bold", color: "#111827", marginBottom: 20 },
  card: { backgroundColor: "#fff", padding: 20, borderRadius: 12, borderWidth: 1, borderColor: "#E5E7EB" },
  name: { fontSize: 20, fontWeight: "600", color: "#111827" },
  email: { fontSize: 14, color: "#6B7280", marginTop: 4 },
  role: { fontSize: 14, color: "#059669", fontWeight: "600", marginTop: 8 },
  logoutBtn: { backgroundColor: "#EF4444", padding: 16, borderRadius: 12, alignItems: "center", marginTop: 20 },
  logoutText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
