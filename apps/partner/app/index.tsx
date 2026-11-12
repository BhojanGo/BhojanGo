// Where the tablet starts: sign in, pick the kitchen, then the board (or the
// application while the kitchen isn't live yet).
import { color, useSession } from "@bhojango/mobile-core";
import { Redirect } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { useKitchen } from "../lib/data";
import { t } from "../lib/ui";

export default function Index() {
  const status = useSession((s) => s.status);
  const role = useSession((s) => s.user?.role);
  const { kitchens, kitchen, error, load } = useKitchen();
  useEffect(() => {
    if (status === "signed-in" && role !== "customer" && kitchens === null) void load();
  }, [status, role, kitchens, load]);

  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  if (role === "customer") return <Redirect href="/join" />;
  if (kitchen) return <Redirect href={kitchen.status === "active" ? "/orders" : "/apply"} />;
  if (kitchens && kitchens.length > 1) return <Redirect href="/kitchens" />;
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 12 }}>
      {error ? <Text style={t.body}>{error}</Text> : <ActivityIndicator color={color.peacock} />}
    </View>
  );
}
