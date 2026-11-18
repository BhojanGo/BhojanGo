// CustomerPaymentFailed.html: not charged, price still held, try again.
import {
  Button, color, errorMessage, LoadError, num, radius, SafeAreaView, Sheet, space, textFont, Txt, type, useI18n,
} from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { paymentStatus, payWithStripe, startPayment, waitForPayment, type PayOutcome, type PayStatus } from "../lib/pay";

export default function PaymentFailed() {
  const { money, t } = useI18n();
  const { orderId, method, provider, reason } = useLocalSearchParams<{ orderId: string; method: "upi" | "card"; provider?: string; reason?: string }>();
  const [status, setStatus] = useState<PayStatus | null>(null);
  /** The payment's status didn't load (offline, our servers): Retry, not a "0:00 left" timer. */
  const [failure, setFailure] = useState<unknown>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<"upi" | "card" | null>(null);

  const loadStatus = () => paymentStatus(orderId).then((s) => {
    setStatus(s);
    setFailure(null);
  }, setFailure);
  useEffect(() => {
    void loadStatus();
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  const left = status?.price_held_until ? Math.max(0, Math.floor((new Date(status.price_held_until).getTime() - now) / 1000)) : 0;
  const total = status ? money(status.amount / 100, status.currency) : "";

  async function retry(with_: "upi" | "card", outcome: PayOutcome) {
    setSheet(null);
    setBusy(true);
    setError(null);
    try {
      await startPayment(orderId, with_, outcome);
      const s = await waitForPayment(orderId);
      if (s.payment_status === "succeeded") router.replace(`/order/${orderId}`);
      else setStatus(s);
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body));
    } finally {
      setBusy(false);
    }
  }

  /** Stripe (US): PaymentSheet again, for a new attempt on the same order. */
  async function retryStripe() {
    setBusy(true);
    setError(null);
    try {
      const r = await payWithStripe(orderId, "card");
      if (r.kind === "paid") {
        const s = await waitForPayment(orderId);
        if (s.payment_status === "succeeded") router.replace(`/order/${orderId}`);
        else setStatus(s);
      } else if (r.kind === "failed") setError(r.message);
      else if (r.kind === "unavailable") setError(t("checkout.stripe_update_app"));
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body));
    } finally {
      setBusy(false);
    }
  }
  const stripe = provider === "stripe";

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.sheet}>
        <View style={styles.icon}><Icon name="alert" size={28} stroke={color.chili} /></View>
        <Txt variant="h1" accessibilityRole="header">{t("app.payment_failed.title")}</Txt>
        <Txt style={{ color: color.muted }}>
          {reason === "authentication" ? t("checkout.bank_not_confirmed") : method === "upi" ? t("app.payment_failed.declined_upi") : t("app.payment_failed.declined_card")}{" "}
          <Text style={[textFont("700"), { color: color.kohl }]}>{t("app.payment_failed.not_charged")}</Text>
        </Txt>
        {status ? (
          <View style={styles.held}>
            <Text style={type.small}>{t("app.payment_failed.held")}</Text>
            <Text style={[type.label, num]}>
              {t("app.payment_failed.left", { total, time: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` })}
            </Text>
          </View>
        ) : failure ? <LoadError error={failure} onRetry={loadStatus} style={{ backgroundColor: color.porcelain }} /> : null}
        {error ? <Text accessibilityRole="alert" style={[type.small, { color: color.chili }]}>{error}</Text> : null}
        {!status ? null : left > 0 && status.can_retry !== false ? (
          <View style={{ gap: space[2] }}>
            <Button title={method === "upi" ? t("app.payment_failed.try_upi") : t("app.payment_failed.try_card")} size="lg" block loading={busy}
              onPress={() => (stripe ? void retryStripe() : setSheet(method))} />
            {/* Stripe's sheet already offers every way to pay (cards, Google Pay) */}
            {stripe ? null : (
              <Button title={t("app.payment_failed.another_way")} variant="secondary" block disabled={busy} onPress={() => setSheet(method === "upi" ? "card" : "upi")} />
            )}
          </View>
        ) : (
          <Button title={t("app.payment_failed.back_to_bag")} size="lg" block onPress={() => router.replace("/bag")} />
        )}
      </View>
      <Sheet visible={sheet != null} onClose={() => setSheet(null)} title={sheet === "card" ? t("app.payment_failed.sheet_card") : t("app.payment_failed.sheet_upi")}
        footer={
          <View style={{ gap: space[2] }}>
            <Button title={t("app.payment_failed.approve", { total })} size="lg" block onPress={() => sheet && retry(sheet, "approve")} />
            <Button title={t("app.payment_failed.decline")} variant="secondary" block onPress={() => sheet && retry(sheet, "decline")} />
          </View>
        }>
        <Txt variant="small" style={{ color: color.muted }}>{t("app.payment_failed.test_note")}</Txt>
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.porcelain, justifyContent: "flex-end" },
  sheet: { backgroundColor: color.white, borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet, padding: space[6], gap: space[4] },
  icon: { width: 56, height: 56, borderRadius: radius.pill, backgroundColor: "#FCE8E6", alignItems: "center", justifyContent: "center" },
  held: { flexDirection: "row", justifyContent: "space-between", padding: space[4], borderRadius: radius.card, backgroundColor: color.porcelain },
});
