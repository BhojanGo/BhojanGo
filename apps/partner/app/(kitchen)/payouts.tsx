// Payouts: the payout account and weekly statements (food sales, commission,
// offers you funded, refunds that were the kitchen's fault). On a phone (lib/layout.ts)
// the account sits above the statements.
import { api, ApiError, LoadError, loadErrorText, num, SafeAreaView, type Translate, type, unwrap, useI18n } from "@bhojango/mobile-core";
import { useState } from "react";
import { ActivityIndicator, Linking, ScrollView, StyleSheet, Text, View } from "react-native";

import { useFormat, useKitchen, useLoad } from "../../lib/data";
import { useLayout } from "../../lib/layout";
import { Btn, color, radius, t } from "../../lib/ui";

type Statement = { id: string; payee_id: string; amount: number; currency: string; status: string; period_start: string; period_end: string;
  summary: { orders?: number; food?: string; commission?: string; restaurant_funded_offers?: string; refunds?: string } };
type Account = { id: string; payee_id: string; provider: string; status: string };

const STATUSES = ["paid", "pending", "no_account", "failed"];
const statusLabel = (t: Translate, s: string) => (STATUSES.includes(s) ? t(`partner.payouts.status.${s}`) : s);
// data-ok: payment provider brand names (Markets payment_providers values), not places or currencies.
const PROVIDERS: Record<string, string> = { razorpay: "Razorpay", stripe: "Stripe" };

function week(s: Statement, date: ReturnType<typeof useFormat>["date"]) {
  const end = new Date(`${s.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  return `${date(s.period_start)} – ${date(end)}`;
}

export default function Payouts() {
  const { cash, date } = useFormat();
  const { t: tr } = useI18n();
  const { width, narrow } = useLayout();
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
      setMsg(e instanceof ApiError ? e.message : loadErrorText(e, tr).reason);
    } finally {
      setBusy(false);
    }
  }

  const a = data.data?.account;
  return (
    <SafeAreaView testID="payouts-screen" edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={[s.header, narrow && { height: 64, paddingHorizontal: 16 }]}><Text accessibilityRole="header" style={t.h1}>{tr("partner.payouts.title")}</Text></View>
      {/* R9: until the account and statements load, a spinner (or the error and Retry), never "Set up payouts" for an account we haven't read. */}
      {!data.data ? (
        <View style={{ flex: 1, padding: 24, justifyContent: "center" }}>
          {data.failure ? <LoadError error={data.failure} onRetry={data.reload} /> : <ActivityIndicator accessibilityLabel={tr("common.loading")} color={color.peacock} />}
        </View>
      ) : (
      <ScrollView contentContainerStyle={{ padding: narrow ? 12 : width < 1000 ? 16 : 24, gap: narrow ? 12 : 16, flexDirection: width < 760 ? "column" : "row", alignItems: "stretch" }}>
        <View testID="payout-account" style={[s.panel, { flex: width < 760 ? undefined : 1 }, narrow && { padding: 16 }]}>
          <Text style={type.h3}>{tr("partner.payouts.where")}</Text>
          <Text style={t.body}>
            {a ? (a.status === "active" ? tr("partner.payouts.paid_through", { provider: PROVIDERS[a.provider] ?? tr("partner.payouts.partner") })
              : tr("partner.payouts.unconfirmed")) : tr("partner.payouts.add_bank")}
          </Text>
          {!a || a.status !== "active" ? <Btn title={a ? tr("partner.payouts.continue") : tr("partner.payouts.set_up")} kind="primary" busy={busy} onPress={setUp} /> : null}
          {msg ? <Text style={[type.small, { color: color.chili }]}>{msg}</Text> : null}
        </View>
        <View testID="payout-statements" style={[s.panel, { flex: width < 760 ? undefined : 2 }, narrow && { padding: 16 }]}>
          <Text style={type.h3}>{tr("partner.payouts.statements")}</Text>
          {data.data && data.data.statements.length === 0 ? <Text style={t.muted}>{tr("partner.payouts.none_yet")}</Text> : null}
          {data.data?.statements.map((st) => (
            <View key={st.id} style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={type.label}>{week(st, date)}</Text>
                <Text style={t.muted}>
                  {[st.summary.orders != null ? tr("partner.payouts.orders", { count: st.summary.orders }) : null,
                    Number(st.summary.restaurant_funded_offers ?? 0) > 0 ? tr("partner.payouts.offers", { amount: cash(st.summary.restaurant_funded_offers, st.currency) }) : null,
                    statusLabel(tr, st.status)].filter(Boolean).join(" · ")}
                </Text>
              </View>
              <Text style={[type.label, num, { flexShrink: 0 }]}>{cash(st.amount / 100, st.currency, 2)}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 10 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: color.divider },
});
