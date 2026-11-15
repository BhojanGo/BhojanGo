// CustomerCheckout.html: your bag, the tip, the fair bill (from a quote), pay.
import {
  api, Button, cartItems, color, errorMessage, FairBill, radius, Segmented, Sheet, space, textFont, Txt, unwrap, useBag,
  useCountry, useI18n, type CoreSchemas,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { startPayment, waitForPayment, type PayOutcome } from "../lib/pay";
import { useWhere } from "../lib/where";

type Quote = CoreSchemas["QuoteOut"];

export default function Bag() {
  const bag = useBag();
  const { point, market } = useWhere();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const { t, money } = useI18n();
  const { country } = useCountry(); // the delivery address's country (Markets): currency, payment methods
  const currency = market?.currency ?? country?.currency ?? "";
  const method: "upi" | "card" = country?.payment_methods.includes("upi") ? "upi" : "card";

  // Re-price whenever the bag or the tip changes; the quote is what gets charged.
  const lines = bag.lines;
  useEffect(() => {
    if (!bag.restaurantId || !point || lines.length === 0) return;
    let live = true;
    api.core
      .POST("/api/v1/pricing/quote", {
        body: {
          restaurant_id: bag.restaurantId, items: cartItems(lines), tip: bag.tip,
          deliver_to: point.addressId ? { address_id: point.addressId } : { lat: point.lat, lng: point.lng },
        },
      })
      .then((r) => {
        if (!live) return;
        setQuote(unwrap(r));
        setError(null);
      })
      .catch((e) => live && (setQuote(null), setError(errorMessage((e as { body?: unknown }).body))));
    return () => {
      live = false;
    };
  }, [bag.restaurantId, lines, bag.tip, point]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (lines.length === 0) {
    return (
      <SafeAreaView style={[styles.screen, { alignItems: "center", justifyContent: "center", gap: space[4] }]}>
        <Txt variant="h1">Your bag is empty</Txt>
        <Button title="Find something to eat" onPress={() => router.replace("/home")} />
      </SafeAreaView>
    );
  }

  // Tip choices are the city's (the quote's tip_presets), as on the website.
  const tips = [0, ...new Set((quote?.tip_presets?.amounts ?? []).map(Number).filter((n) => Number.isFinite(n) && n > 0))];
  const held = quote ? Math.max(0, Math.floor((new Date(quote.expires_at).getTime() - now) / 1000)) : 0;

  async function pay(outcome: PayOutcome) {
    if (!quote || !point) return;
    setSheet(false);
    setPaying(true);
    setError(null);
    try {
      const order = unwrap(await api.core.POST("/api/v1/orders", {
        params: { header: { "X-Idempotency-Key": quote.quote_id } },
        body: {
          restaurant_id: bag.restaurantId!, items: cartItems(lines), payment_method: method, quote_token: quote.token,
          delivery_address: { street: point.street, city: point.city, state: point.state, zip: point.zip || "000000", country: point.country || country?.code || "" },
        },
      })) as { id: string };
      await startPayment(order.id, method, outcome);
      const status = await waitForPayment(order.id);
      if (status.payment_status === "succeeded") {
        bag.clear();
        router.replace(`/order/${order.id}`);
      } else {
        router.replace({ pathname: "/payment-failed", params: { orderId: order.id, method } });
      }
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body));
    } finally {
      setPaying(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.top}>
        <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.back()} style={styles.back}>
          <Icon name="back" />
        </Pressable>
        <Txt variant="h1" accessibilityRole="header" style={{ flex: 1 }}>Your bag</Txt>
        {quote ? (
          <View style={styles.held}>
            <Text style={[textFont("700"), { fontSize: 12, color: color.peacock }]}>
              Price held {Math.floor(held / 60)}:{String(held % 60).padStart(2, "0")}
            </Text>
          </View>
        ) : null}
      </View>
      <ScrollView contentContainerStyle={{ paddingHorizontal: space[5], paddingVertical: space[2], gap: space[3] }}>
        <View style={styles.card}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={[textFont("800"), { fontSize: 14, flex: 1 }]} numberOfLines={1}>{point?.label ?? ""}</Text>
          </View>
          <View style={styles.rule} />
          {lines.map((l) => (
            <View key={l.key} style={styles.line}>
              <Text style={[textFont("400"), { fontSize: 14, flex: 1 }]}>
                {l.quantity > 1 ? `${l.quantity} × ` : ""}{l.name}
                {l.summary ? <Text style={{ color: color.muted }}> · {l.summary}</Text> : null}
              </Text>
              <Text style={[textFont("400"), { fontSize: 14, fontVariant: ["tabular-nums"] }]}>{money(l.unitPrice * l.quantity, currency, { whole: true })}</Text>
            </View>
          ))}
        </View>
        <View style={styles.card}>
          <Text style={[textFont("800"), { fontSize: 14 }]}>
            {t("checkout.tip_title")} <Text style={[textFont("500"), { color: color.muted }]}>· {t("checkout.tip_note")}</Text>
          </Text>
          <Segmented
            label={t("checkout.tip_title")}
            value={String(bag.tip)}
            onChange={(v) => bag.setTip(Number(v))}
            options={tips.map((n) => ({ value: String(n), label: n === 0 ? t("checkout.tip_none") : money(n, currency, { whole: true }) }))}
          />
        </View>
        {quote ? <FairBill lines={quote.lines} currency={quote.currency} /> : error ? null : <ActivityIndicator color={color.peacock} />}
        {error ? <Text style={[textFont("600"), { color: color.chili, fontSize: 14 }]}>{error}</Text> : null}
      </ScrollView>
      <View style={styles.footer}>
        <View style={styles.method}>
          <View style={styles.methodTag}><Text style={[textFont("800"), { fontSize: 11 }]}>{method === "upi" ? "UPI" : "CARD"}</Text></View>
          <Text style={[textFont("400"), { fontSize: 14, flex: 1 }]}>
            <Text style={textFont("700")}>{method === "upi" ? "UPI" : "Card"}</Text>
            <Text style={{ color: color.muted }}> · {method === "upi" ? "pay in your UPI app" : "Apple Pay, Google Pay or card"}</Text>
          </Text>
        </View>
        <Button
          title={quote ? `Pay ${money(quote.total, quote.currency)}` : "Pay"}
          size="lg"
          block
          loading={paying}
          disabled={!quote || held === 0}
          onPress={() => setSheet(true)}
        />
      </View>
      <Sheet visible={sheet} onClose={() => setSheet(false)} title={method === "upi" ? "Pay with UPI" : "Pay with card"}
        footer={
          <View style={{ gap: space[2] }}>
            <Button title={`Approve ${quote ? money(quote.total, quote.currency) : ""}`} size="lg" block onPress={() => pay("approve")} />
            <Button title="Decline" variant="secondary" block onPress={() => pay("decline")} />
          </View>
        }>
        <Txt variant="small" style={{ color: color.muted }}>
          Test payments: nothing is charged. Approve or decline as your {method === "upi" ? "UPI app" : "bank"} would.
        </Txt>
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.porcelain },
  top: { flexDirection: "row", alignItems: "center", gap: 4, paddingLeft: space[2], paddingRight: space[5], paddingTop: space[3], paddingBottom: space[2] },
  back: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  held: { borderRadius: radius.pill, backgroundColor: color.white, borderWidth: 1, borderColor: "#D5E4E5", paddingHorizontal: 11, paddingVertical: 7 },
  card: { backgroundColor: color.white, borderRadius: radius.card, padding: space[4], gap: 10 },
  rule: { height: 1, backgroundColor: color.divider },
  line: { flexDirection: "row", justifyContent: "space-between", gap: 10 },
  footer: { paddingHorizontal: space[5], paddingTop: space[2], paddingBottom: space[6], gap: space[2] },
  method: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44, paddingHorizontal: 4 },
  methodTag: { height: 28, paddingHorizontal: 8, borderRadius: 8, borderWidth: 1, borderColor: color.lineStrong, backgroundColor: color.white, justifyContent: "center" },
});
