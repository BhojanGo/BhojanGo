// Payouts: the payout account and weekly statements (food sales, commission,
// offers you funded, refunds that were the kitchen's fault). On a phone (lib/layout.ts)
// the account sits above the statements.
import { api, LoadError, num, payoutCopy, type PayoutCopy, providerName, type PayoutSetup, repayDay, SafeAreaView, STATEMENT_NOTES, STATEMENT_STATUSES, type Translate, type,
  unwrap, useI18n } from "@bhojango/mobile-core";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, AppState, Linking, ScrollView, StyleSheet, Text, View } from "react-native";

import { useFormat, useKitchen, useLoad } from "../../lib/data";
import { useLayout } from "../../lib/layout";
import { Btn, color, radius, t, tone } from "../../lib/ui";

type Statement = { id: string; payee_id: string; amount: number; currency: string; status: string; period_start: string; period_end: string; repay_on?: string | null;
  summary: { orders?: number; food?: string; commission?: string; restaurant_funded_offers?: string; refunds?: string;
    commission_tax?: string; tds?: string } };

const statusLabel = (t: Translate, s: string) => ((STATEMENT_STATUSES as readonly string[]).includes(s) ? t(`partner.payouts.status.${s}`) : s);
// The set-up badge's colours per state (R10).
const BADGE: Record<PayoutCopy["tone"], { bg: string; fg: string }> = {
  neutral: { bg: color.porcelain, fg: color.kohl }, progress: { bg: color.peacockTint, fg: color.peacockDeep },
  warning: { bg: tone.kesarSoft, fg: tone.kesarInk }, good: { bg: color.peacockTint, fg: color.peacockDeep },
};

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
  const [checking, setChecking] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  /** Ask Stripe (through our API) on the next load: back from its pages, or "Check again". */
  const refreshNext = useRef(false);
  /** We sent the kitchen to Stripe's pages; refresh when the app comes back to the front. */
  const away = useRef(false);
  const data = useLoad(async () => {
    const refresh = refreshNext.current;
    refreshNext.current = false;
    const [st, setup] = await Promise.all([
      api.core.GET("/api/v1/finance/statements/me"),
      api.core.GET("/api/v1/finance/payout-accounts/me/setup", { params: { query: { payee_type: "restaurant", restaurant_id: kitchen.id, refresh } } }),
    ]);
    return {
      statements: (unwrap(st) as unknown as Statement[]).filter((x) => x.payee_id === kitchen.id),
      setup: unwrap(setup) as unknown as PayoutSetup,
    };
  }, kitchen.id);
  const { reload } = data;

  async function check() {
    setChecking(true);
    refreshNext.current = true;
    await reload();
    setChecking(false);
  }

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active" && away.current) {
        away.current = false;
        refreshNext.current = true;
        void reload();
      }
    });
    return () => sub.remove();
  }, [reload]);

  /** R16: the commission tax invoice, opened in the browser through a link that works for an hour. */
  async function openInvoice(statementId: string) {
    setMsg(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/finance/statements/{statement_id}/commission-invoice/link",
        { params: { path: { statement_id: statementId } } })) as { url: string };
      await Linking.openURL(r.url);
    } catch {
      setMsg(tr("partner.payouts.tax_invoice_failed"));
    }
  }

  async function setUp() {
    setBusy(true);
    setMsg(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/finance/payout-accounts", { body: { payee_type: "restaurant", restaurant_id: kitchen.id } })) as { onboarding_url?: string | null };
      if (r.onboarding_url) {
        away.current = true;
        await Linking.openURL(r.onboarding_url);
      }
      await reload();
    } catch {
      setMsg(tr("payout_setup.open_failed", { provider: providerName(tr, data.data?.setup.account?.provider ?? data.data?.setup.provider) }));
    } finally {
      setBusy(false);
    }
  }

  const setup = data.data?.setup;
  const copy = setup ? payoutCopy(tr, setup) : null;
  return (
    <SafeAreaView testID="payouts-screen" edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={[s.header, narrow && { height: 64, paddingHorizontal: 16 }]}><Text accessibilityRole="header" style={t.h1}>{tr("partner.payouts.title")}</Text></View>
      {/* R9: until the account and statements load, a spinner (or the error and Retry), never "Set up payouts" for an account we haven't read. */}
      {!data.data || !copy || !setup ? (
        <View style={{ flex: 1, padding: 24, justifyContent: "center" }}>
          {data.failure ? <LoadError error={data.failure} onRetry={data.reload} /> : <ActivityIndicator accessibilityLabel={tr("common.loading")} color={color.peacock} />}
        </View>
      ) : (
      <ScrollView contentContainerStyle={{ padding: narrow ? 12 : width < 1000 ? 16 : 24, gap: narrow ? 12 : 16, flexDirection: width < 760 ? "column" : "row", alignItems: "stretch" }}>
        <View testID="payout-account" style={[s.panel, { flex: width < 760 ? undefined : 1 }, narrow && { padding: 16 }]}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <Text style={[type.h3, { flexShrink: 1 }]}>{tr("partner.payouts.where")}</Text>
            <View testID={`payout-state-${setup.state}`} style={[s.badge, { backgroundColor: BADGE[copy.tone].bg }]}>
              <Text style={[type.caption, { color: BADGE[copy.tone].fg }]}>{copy.badge}</Text>
            </View>
          </View>
          <Text style={t.body}>{copy.body}</Text>
          {copy.action ? <Btn testID="payout-set-up" title={busy ? tr("payout_setup.opening", { provider: providerName(tr, setup.account?.provider ?? setup.provider) }) : copy.action} kind="primary" busy={busy} onPress={setUp} /> : null}
          {copy.comeBack && setup.account ? <Text style={t.muted}>{tr("payout_setup.come_back")}</Text> : null}
          {setup.state !== "ready" && setup.account ? <Btn testID="payout-check" title={tr("payout_setup.check_again")} busy={checking} onPress={() => void check()} /> : null}
          {msg ? <Text accessibilityRole="alert" style={[type.small, { color: tone.reject }]}>{msg}</Text> : null}
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
                    // R16: what the platform took for the government (tax on its commission; TDS)
                    Number(st.summary.commission_tax ?? 0) > 0 ? tr("partner.payouts.commission_tax", { amount: cash(st.summary.commission_tax, st.currency) }) : null,
                    Number(st.summary.tds ?? 0) > 0 ? tr("partner.payouts.tds", { amount: cash(st.summary.tds, st.currency) }) : null,
                    STATEMENT_NOTES.includes(st.status) ? null : statusLabel(tr, st.status)].filter(Boolean).join(" · ")}
                </Text>
                {Number(st.summary.commission_tax ?? 0) > 0 ? (
                  <Btn testID={`tax-invoice-${st.id}`} title={tr("partner.payouts.tax_invoice")} onPress={() => void openInvoice(st.id)} />
                ) : null}
                {STATEMENT_NOTES.includes(st.status) && repayDay(st.repay_on) ? (
                  <Text testID={`payout-note-${st.status}`} style={[t.body, { marginTop: 4 }]}>
                    {tr(`partner.payouts.status.${st.status}`, { amount: cash(st.amount / 100, st.currency), date: date(repayDay(st.repay_on)!) })}
                  </Text>
                ) : null}
              </View>
              <Text style={[type.label, num, { flexShrink: 0 }]}>{cash(st.amount / 100, st.currency)}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  badge: { borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 3 },
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 10 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: color.divider },
});
