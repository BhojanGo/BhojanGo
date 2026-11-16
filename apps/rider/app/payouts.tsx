// Payouts: where the money goes (payout account) and past weekly statements.
import { api, ApiError, num, SafeAreaView, type Translate, type, unwrap, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { useFormat } from "../lib/rider";
import { night, space, ui } from "../lib/theme";

interface Statement {
  id: string; amount: number; currency: string; status: string; period_start: string; period_end: string;
  summary: { deliveries?: number; floor_top_up?: string };
}
interface Account { id: string; provider: string; status: string; country: string }

const STATUSES = ["paid", "pending", "no_account", "failed"];
const statusLabel = (t: Translate, s: string) => (STATUSES.includes(s) ? t(`rider.payouts.status.${s}`) : s);

/** Stripe and Razorpay are names; anything else is "our payments partner". */
// data-ok: payment provider brand names (Markets payment_providers values), not places or currencies.
const PROVIDERS: Record<string, string> = { razorpay: "Razorpay", stripe: "Stripe" };

function period(s: Statement, date: ReturnType<typeof useFormat>["date"]) {
  const end = new Date(`${s.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  return `${date(s.period_start)} – ${date(end)}`;
}

export default function Payouts() {
  const { cash, date } = useFormat();
  const { t } = useI18n();
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
      setMsg(e instanceof ApiError ? e.message : t("rider.payouts.start_failed"));
    } finally {
      setBusy(false);
    }
  }

  const account = data?.accounts[0];
  return (
    <SafeAreaView testID="payouts-screen" style={ui.screen}>
      <View style={styles.head}>
        <Pressable testID="back" accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}><Icon name="back" /></Pressable>
        <Text accessibilityRole="header" style={[type.h2, { color: night.text }]}>{t("rider.payouts.title")}</Text>
      </View>
      {!data ? (
        <View style={styles.center}>{msg ? <Text style={ui.body}>{msg}</Text> : <ActivityIndicator color={night.kesar} />}</View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }}>
          <View style={styles.card}>
            <Icon name="bank" stroke={night.link} />
            <View style={{ flex: 1 }}>
              <Text style={ui.bold}>
                {account ? (account.status === "active" ? t("rider.payouts.ready") : t("rider.payouts.finish")) : t("rider.payouts.none")}
              </Text>
              <Text style={ui.muted}>
                {account
                  ? account.status === "active"
                    ? t("rider.payouts.paid_through", { provider: PROVIDERS[account.provider] ?? t("rider.payouts.partner") })
                    : t("rider.payouts.unconfirmed")
                  : t("rider.payouts.add_bank")}
              </Text>
            </View>
          </View>
          {!account || account.status !== "active" ? (
            <Pressable accessibilityRole="button" onPress={setUp} disabled={busy} style={ui.cta}>
              <Text style={ui.ctaText}>{busy ? t("rider.payouts.opening") : account ? t("rider.payouts.continue") : t("rider.payouts.set_up")}</Text>
            </Pressable>
          ) : null}
          {msg ? <Text style={[type.small, { color: night.sosText }]}>{msg}</Text> : null}
          <Text style={[ui.bold, { marginTop: space[2] }]}>{t("rider.payouts.past_weeks")}</Text>
          {data.statements.length === 0 ? <Text style={ui.muted}>{t("rider.payouts.none_yet")}</Text> : null}
          {data.statements.map((s) => (
            <View key={s.id} style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={ui.bold}>{period(s, date)}</Text>
                <Text style={[ui.muted, num]}>
                  {[t("rider.payouts.deliveries", { count: s.summary.deliveries ?? 0 }),
                    Number(s.summary.floor_top_up ?? 0) > 0 ? t("rider.payouts.top_up", { amount: cash(s.summary.floor_top_up, s.currency) }) : null,
                    statusLabel(t, s.status)].filter(Boolean).join(" · ")}
                </Text>
              </View>
              <Text style={[ui.bold, num]}>{cash(s.amount / 100, s.currency)}</Text>
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

