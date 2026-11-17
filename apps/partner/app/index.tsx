// Where the tablet starts: sign in, pick the kitchen, then the board (or the
// application while the kitchen isn't live yet).
import { color, LoadError, SafeAreaView, useI18n, useSession } from "@bhojango/mobile-core";
import { Redirect } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { useKitchen } from "../lib/data";
import { t } from "../lib/ui";

export default function Index() {
  const status = useSession((s) => s.status);
  const role = useSession((s) => s.user?.role);
  const { kitchens, kitchen, failure, none, load } = useKitchen();
  const user = useSession((s) => s.user);
  const { t: tr } = useI18n();
  useEffect(() => {
    if (status === "signed-in" && role !== "customer" && kitchens === null) void load();
  }, [status, role, kitchens, load]);

  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  if (role === "customer") return <Redirect href="/join" />;
  if (kitchen) return <Redirect href={kitchen.status === "active" ? "/orders" : "/apply"} />;
  if (kitchens && kitchens.length > 1) return <Redirect href="/kitchens" />;
  // R9: the kitchens didn't load (offline, our servers): say so and Retry, never a raw error.
  if (failure && !none) {
    return <SafeAreaView style={{ flex: 1, padding: 24 }}><LoadError error={failure} onRetry={load} fill /></SafeAreaView>;
  }
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 12 }}>
      {none ? <Text style={t.body}>{tr("partner.home.no_kitchen", { name: user?.full_name ?? "" })}</Text>
        : <ActivityIndicator color={color.peacock} />}
    </View>
  );
}
