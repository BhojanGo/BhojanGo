// Payouts: where the money goes (payout set-up with the country's provider, e.g.
// Stripe Connect: R10) and past weekly statements. Set-up happens on the provider's
// own pages; when the delivery partner comes back to the app we ask again.
import { api, LoadError, num, payoutCopy, type PayoutCopy, type PayoutSetup, providerName, SafeAreaView, STATEMENT_STATUSES, type Translate,
  type, unwrap, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, AppState, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { useFormat } from "../lib/rider";
import { night, space, ui } from "../lib/theme";

interface Statement {
  id: string; amount: number; currency: string; status: string; period_start: string; period_end: string;
  summary: { deliveries?: number; floor_top_up?: string };
}

const statusLabel = (t: Translate, s: string) => ((STATEMENT_STATUSES as readonly string[]).includes(s) ? t(`rider.payouts.status.${s}`) : s);
// The set-up badge per state (R10), on the night theme.
const BADGE: Record<PayoutCopy["tone"], { bg: string; fg: string }> = {
  neutral: { bg: night.raised, fg: night.text }, progress: { bg: night.doneBg, fg: night.text },
  warning: { bg: night.needed, fg: night.onKesar }, good: { bg: night.doneBg, fg: night.online },
};

function period(s: Statement, date: ReturnType<typeof useFormat>["date"]) {
  const end = new Date(`${s.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  return `${date(s.period_start)} – ${date(end)}`;
}

export default function Payouts() {
  const { cash, date } = useFormat();
  const { t } = useI18n();
  const [data, setData] = useState<{ statements: Statement[]; setup: PayoutSetup } | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  /** The first load failed (offline, our servers): LoadError and Retry (R9). */
  const [failure, setFailure] = useState<unknown>(null);
  /** We sent them to the provider's pages: ask again (refresh) when the app comes back. */
  const away = useRef(false);

  const load = useCallback(async (refresh = false) => {
    const [st, setup] = await Promise.all([
      api.core.GET("/api/v1/finance/statements/me"),
      api.core.GET("/api/v1/finance/payout-accounts/me/setup", { params: { query: { payee_type: "rider", refresh } } }),
    ]);
    setData({ statements: (unwrap(st) as unknown as Statement[]) ?? [], setup: unwrap(setup) as unknown as PayoutSetup });
    setFailure(null);
  }, []);
  const firstLoad = useCallback(() => load().catch(setFailure), [load]);
  useFocusEffect(useCallback(() => {
    void firstLoad();
  }, [firstLoad]));
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active" && away.current) {
        away.current = false;
        void load(true).catch(() => undefined);
      }
    });
    return () => sub.remove();
  }, [load]);

  const provider = providerName(t, data?.setup.account?.provider ?? data?.setup.provider);

  async function setUp() {
    setBusy(true);
    setMsg(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/finance/payout-accounts", { body: { payee_type: "rider" } })) as { onboarding_url?: string | null };
      if (r.onboarding_url) {
        away.current = true;
        await Linking.openURL(r.onboarding_url);
      }
      await load();
    } catch {
      setMsg(t("payout_setup.open_failed", { provider }));
    } finally {
      setBusy(false);
    }
  }

  async function check() {
    setChecking(true);
    setMsg(null);
    try {
      await load(true);
    } catch {
      setMsg(t("payout_setup.open_failed", { provider }));
    } finally {
      setChecking(false);
    }
  }

  const setup = data?.setup;
  const copy = setup ? payoutCopy(t, setup) : null;
  return (
    <SafeAreaView testID="payouts-screen" style={ui.screen}>
      <View style={styles.head}>
        <Pressable testID="back" accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}><Icon name="back" /></Pressable>
        <Text accessibilityRole="header" style={[type.h2, { color: night.text }]}>{t("rider.payouts.title")}</Text>
      </View>
      {!data || !setup || !copy ? (
        <View style={styles.center}>
          {failure ? <LoadError error={failure} onRetry={firstLoad} tone="dark" fill style={{ alignSelf: "stretch" }} />
            : <ActivityIndicator accessibilityLabel={t("common.loading")} color={night.kesar} />}
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }}>
          <View testID="payout-account" style={styles.card}>
            <Icon name="bank" stroke={night.link} />
            <View style={{ flex: 1, gap: 6 }}>
              <View testID={`payout-state-${setup.state}`} style={[styles.badge, { backgroundColor: BADGE[copy.tone].bg }]}>
                <Text style={[type.caption, { color: BADGE[copy.tone].fg }]}>{copy.badge}</Text>
              </View>
              <Text style={ui.body}>{copy.body}</Text>
            </View>
          </View>
          {copy.action ? (
            <Pressable testID="payout-set-up" accessibilityRole="button" accessibilityState={{ busy, disabled: busy }} onPress={setUp} disabled={busy} style={ui.cta}>
              {busy ? <ActivityIndicator color={night.onKesar} /> : null}
              <Text numberOfLines={1} style={[ui.ctaText, { flexShrink: 1 }]}>{busy ? t("payout_setup.opening", { provider }) : copy.action}</Text>
            </Pressable>
          ) : null}
          {copy.comeBack && setup.account ? <Text style={ui.muted}>{t("payout_setup.come_back")}</Text> : null}
          {setup.state !== "ready" && setup.account ? (
            <Pressable testID="payout-check" accessibilityRole="button" accessibilityState={{ busy: checking }} onPress={() => void check()}
              disabled={checking} style={ui.outline}>
              {checking ? <ActivityIndicator color={night.text} /> : null}
              <Text style={ui.bold}>{t("payout_setup.check_again")}</Text>
            </Pressable>
          ) : null}
          {msg ? <Text accessibilityRole="alert" style={[type.small, { color: night.sosText }]}>{msg}</Text> : null}
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
  card: { flexDirection: "row", gap: 12, alignItems: "flex-start", padding: 16, borderRadius: 16, backgroundColor: night.surface },
  badge: { alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: night.raised, gap: 12 },
});
