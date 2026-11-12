// CustomerPaymentFailed.html: not charged, price still held, try again.
import { Button, color, errorMessage, money, radius, Sheet, space, textFont, Txt } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { paymentStatus, startPayment, waitForPayment, type PayOutcome, type PayStatus } from "../lib/pay";

export default function PaymentFailed() {
  const { orderId, method } = useLocalSearchParams<{ orderId: string; method: "upi" | "card" }>();
  const [status, setStatus] = useState<PayStatus | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<"upi" | "card" | null>(null);

  useEffect(() => {
    void paymentStatus(orderId).then(setStatus);
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
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

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.sheet}>
        <View style={styles.icon}><Icon name="alert" size={28} stroke={color.chili} /></View>
        <Txt variant="h1" accessibilityRole="header" style={{ fontSize: 28 }}>Payment didn&apos;t go through</Txt>
        <Txt style={{ color: color.muted }}>
          {method === "upi" ? "Your UPI app declined the request." : "Your bank declined the payment."}{" "}
          <Text style={[textFont("700"), { color: color.kohl }]}>
            You have not been charged. If money left your account, your bank reverses it automatically, usually by the next working day.
          </Text>
        </Txt>
        <View style={styles.held}>
          <Text style={[textFont("400"), { fontSize: 14 }]}>Your price is still held</Text>
          <Text style={[textFont("800"), { fontSize: 14, fontVariant: ["tabular-nums"] }]}>
            {total} · {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")} left
          </Text>
        </View>
        {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
        {left > 0 && status?.can_retry !== false ? (
          <View style={{ gap: space[2] }}>
            <Button title={method === "upi" ? "Try UPI again" : "Try the card again"} size="lg" block loading={busy} onPress={() => setSheet(method)} />
            <Button title="Pay another way" variant="secondary" block disabled={busy} onPress={() => setSheet(method === "upi" ? "card" : "upi")} />
          </View>
        ) : (
          <Button title="Back to your bag" size="lg" block onPress={() => router.replace("/bag")} />
        )}
        <Text style={[textFont("700"), { color: color.peacock, textAlign: "center", marginTop: space[2] }]}>Chat with support</Text>
      </View>
      <Sheet visible={sheet != null} onClose={() => setSheet(null)} title={sheet === "card" ? "Pay with card" : "Pay with UPI"}
        footer={
          <View style={{ gap: space[2] }}>
            <Button title={`Approve ${total}`} size="lg" block onPress={() => sheet && retry(sheet, "approve")} />
            <Button title="Decline" variant="secondary" block onPress={() => sheet && retry(sheet, "decline")} />
          </View>
        }>
        <Txt variant="small" style={{ color: color.muted }}>Test payments: nothing is charged.</Txt>
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
