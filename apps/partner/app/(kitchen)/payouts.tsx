// Payouts: the payout account and weekly statements (food sales, commission,
// offers you funded, refunds that were the kitchen's fault).
import { api, ApiError, unwrap } from "@bhojango/mobile-core";
import { useState } from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { cash, useKitchen, useLoad } from "../../lib/data";
import { Btn, color, radius, t, textFont } from "../../lib/ui";

type Statement = { id: string; payee_id: string; amount: number; currency: string; status: string; period_start: string; period_end: string;
  summary: { orders?: number; food?: string; commission?: string; restaurant_funded_offers?: string; refunds?: string } };
type Account = { id: string; payee_id: string; provider: string; status: string };

const STATUS: Record<string, string> = { paid: "Paid", pending: "On its way", no_account: "Waiting for your bank details", failed: "Didn't go through · we'll retry" };

function week(s: Statement) {
  const end = new Date(`${s.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  const f = (d: Date) => d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `${f(new Date(`${s.period_start}T12:00:00`))} – ${f(end)}`;
}

export default function Payouts() {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const data = useLoad(async () => {
    const [st, ac] = await Promise.all([api.core.GET("/api/v1/finance/statements/me"), api.core.GET("/api/v1/finance/payout-accounts/me")]);
    return {
      statements: (unwrap(st) as unknown as Statement[]).filter((x) => x.payee_id === kitchen.id),
      account: (unwrap(ac) as unknown as Account[]).find((x) => x.payee_id === kitchen.id) ?? null,
    };
  }, kitchen.id);

  async function setUp() {
    setBusy(true);
    setMsg(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/finance/payout-accounts", { body: { payee_type: "restaurant", restaurant_id: kitchen.id } })) as { onboarding_url?: string | null };
      if (r.onboarding_url) await Linking.openURL(r.onboarding_url);
      await data.reload();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const a = data.data?.account;
  return (
    <SafeAreaView edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={s.header}><Text accessibilityRole="header" style={t.h1}>Payouts</Text></View>
      <ScrollView contentContainerStyle={{ padding: 24, gap: 16, flexDirection: "row", alignItems: "flex-start" }}>
        <View style={[s.panel, { flex: 1 }]}>
          <Text style={[textFont("800"), { fontSize: 17 }]}>Where we pay you</Text>
          <Text style={t.body}>{a ? (a.status === "active" ? `Paid every Monday through ${a.provider === "razorpay" ? "Razorpay" : a.provider === "stripe" ? "Stripe" : "our payments partner"}.` : "Your bank details aren't confirmed yet.") : "Add your bank so weekly payouts can reach you."}</Text>
          {!a || a.status !== "active" ? <Btn title={a ? "Continue set-up" : "Set up payouts"} kind="primary" busy={busy} onPress={setUp} /> : null}
          {msg ? <Text style={[textFont("600"), { color: color.chili }]}>{msg}</Text> : null}
        </View>
        <View style={[s.panel, { flex: 2 }]}>
          <Text style={[textFont("800"), { fontSize: 17 }]}>Weekly statements</Text>
          {data.data && data.data.statements.length === 0 ? <Text style={t.muted}>Your first statement shows here after the first Monday payout.</Text> : null}
          {data.data?.statements.map((st) => (
            <View key={st.id} style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={[textFont("700"), { fontSize: 15 }]}>{week(st)}</Text>
                <Text style={t.muted}>
                  {[st.summary.orders != null ? `${st.summary.orders} orders` : null,
                    Number(st.summary.restaurant_funded_offers ?? 0) > 0 ? `offers ${cash(st.summary.restaurant_funded_offers, st.currency)}` : null,
                    STATUS[st.status] ?? st.status].filter(Boolean).join(" · ")}
                </Text>
              </View>
              <Text style={[textFont("800"), { fontSize: 16 }]}>{cash(st.amount / 100, st.currency, 2)}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 10 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: color.divider },
});
