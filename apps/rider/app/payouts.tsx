// Payouts: where the money goes (payout account) and past weekly statements.
import { api, ApiError, unwrap } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { cash } from "../lib/rider";
import { displayFont, night, space, textFont, ui } from "../lib/theme";

interface Statement {
  id: string; amount: number; currency: string; status: string; period_start: string; period_end: string;
  summary: { deliveries?: number; floor_top_up?: string };
}
interface Account { id: string; provider: string; status: string; country: string }

const STATUS: Record<string, string> = {
  paid: "Paid", pending: "On its way", no_account: "Waiting for your payout account", failed: "Didn't go through · we'll retry",
};

function period(s: Statement) {
  const end = new Date(`${s.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  const a = new Date(`${s.period_start}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `${a} – ${end.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}

export default function Payouts() {
  const [data, setData] = useState<{ statements: Statement[]; accounts: Account[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [st, ac] = await Promise.all([api.core.GET("/api/v1/finance/statements/me"), api.core.GET("/api/v1/finance/payout-accounts/me")]);
    setData({ statements: (unwrap(st) as unknown as Statement[]) ?? [], accounts: (unwrap(ac) as unknown as Account[]) ?? [] });
  }, []);
  useFocusEffect(useCallback(() => {
    load().catch((e: Error) => setMsg(e.message));
  }, [load]));

  async function setUp() {
    setBusy(true);
    setMsg(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/finance/payout-accounts", { body: { payee_type: "rider" } })) as { onboarding_url?: string | null };
      if (r.onboarding_url) await Linking.openURL(r.onboarding_url);
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Couldn't start payout set-up. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const account = data?.accounts[0];
  return (
    <SafeAreaView style={ui.screen}>
      <View style={styles.head}>
        <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={styles.back}><Icon name="back" /></Pressable>
        <Text accessibilityRole="header" style={[displayFont("600"), { color: night.text, fontSize: 22 }]}>Payouts</Text>
      </View>
      {!data ? (
        <View style={styles.center}>{msg ? <Text style={ui.body}>{msg}</Text> : <ActivityIndicator color={night.kesar} />}</View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }}>
          <View style={styles.card}>
            <Icon name="bank" stroke={night.link} />
            <View style={{ flex: 1 }}>
              <Text style={ui.bold}>{account ? (account.status === "active" ? "Payout account ready" : "Finish setting up payouts") : "No payout account yet"}</Text>
              <Text style={ui.muted}>
                {account
                  ? account.status === "active" ? `Paid every Monday through ${account.provider === "razorpay" ? "Razorpay" : account.provider === "stripe" ? "Stripe" : "our payments partner"}.` : "Your bank details aren't confirmed yet."
                  : "Add your bank so your weekly pay can reach you."}
              </Text>
            </View>
          </View>
          {!account || account.status !== "active" ? (
            <Pressable accessibilityRole="button" onPress={setUp} disabled={busy} style={ui.cta}>
              <Text style={ui.ctaText}>{busy ? "Opening…" : account ? "Continue set-up" : "Set up payouts"}</Text>
            </Pressable>
          ) : null}
          {msg ? <Text style={[textFont("600"), { color: night.sosText }]}>{msg}</Text> : null}
          <Text style={[ui.bold, { fontSize: 15, marginTop: space[2] }]}>Past weeks</Text>
          {data.statements.length === 0 ? <Text style={ui.muted}>Your weekly statements show here after your first payout.</Text> : null}
          {data.statements.map((s) => (
            <View key={s.id} style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={[ui.bold, textFont("700")]}>{period(s)}</Text>
                <Text style={[ui.muted, { fontSize: 12 }]}>
                  {s.summary.deliveries ?? 0} deliveries{Number(s.summary.floor_top_up ?? 0) > 0 ? ` · floor top-up ${cash(s.summary.floor_top_up, s.currency)}` : ""} · {STATUS[s.status] ?? s.status}
                </Text>
              </View>
              <Text style={ui.bold}>{cash(s.amount / 100, s.currency)}</Text>
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: space[2], paddingTop: space[2] },
  back: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { flexDirection: "row", gap: 12, alignItems: "center", padding: 16, borderRadius: 16, backgroundColor: night.surface },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: night.raised, gap: 12 },
});

