// CustomerCheckout.html: your bag, the tip, the fair bill (from a quote), pay.
import {
  api, ApiError, Button, cartItems, color, type CoreSchemas, errorMessage, FairBill, FIRST_LOAD_TIMEOUT_MS, LoadError, num, quoteRefusal, type QuoteRefusal, radius, SafeAreaView, Segmented, Sheet, space, textFont, timeoutFetch, Txt, type, unwrap, useBag, useCountry, useI18n,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { paymentProvider, payWithStripe, startPayment, waitForPayment, type PayOutcome, type Provider } from "../lib/pay";
import { useWhere } from "../lib/where";

type Quote = CoreSchemas["QuoteOut"];

// The price quote is a POST that only reads: it gives up on time like a GET (R9).
const quoteFetch = timeoutFetch(FIRST_LOAD_TIMEOUT_MS, undefined, true);

export default function Bag() {
  const bag = useBag();
  const { point, market } = useWhere();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<QuoteRefusal | null>(null);
  /** The quote got no answer (offline, our servers): LoadError and Retry instead of a spinner. */
  const [unreachable, setUnreachable] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  // The city's tip buttons: from the quote, or from a refusal that knows them (a bag
  // under the minimum still tips by the city's tip_presets rule); kept while re-pricing.
  const [presets, setPresets] = useState<CoreSchemas["TipPresetsOut"] | null>(null);
  const [paying, setPaying] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const { t, money } = useI18n();
  const { country } = useCountry(); // the delivery address's country (Markets): currency, payment methods
  const currency = market?.currency ?? country?.currency ?? "";
  const method: "upi" | "card" = country?.payment_methods.includes("upi") ? "upi" : "card";
  // Stripe PaymentSheet or the test sheet: the server decides (its keys for this country).
  const [provider, setProvider] = useState<Provider | null>(null);
  const payCountry = point?.country || country?.code || "";
  useEffect(() => {
    if (!payCountry) return;
    let live = true;
    paymentProvider(payCountry).then((p) => live && setProvider(p), () => live && setProvider("fake"));
    return () => {
      live = false;
    };
  }, [payCountry]);

  // Re-price whenever the bag or the tip changes; the quote is what gets charged.
  const lines = bag.lines;
  useEffect(() => {
    if (!bag.restaurantId || !point || lines.length === 0) return;
    let live = true;
    api.core
      .POST("/api/v1/pricing/quote", {
        fetch: quoteFetch,
        body: {
          restaurant_id: bag.restaurantId, items: cartItems(lines), tip: bag.tip,
          deliver_to: point.addressId ? { address_id: point.addressId } : { lat: point.lat, lng: point.lng },
        },
      })
      .then((r) => {
        if (!live) return;
        const q = unwrap(r);
        setQuote(q);
        setUnreachable(null);
        setPresets(q.tip_presets ?? null);
        setError(null);
        setRefusal(null);
      })
      .catch((e) => {
        if (!live) return;
        if (!(e instanceof ApiError)) {
          setQuote(null);
          setUnreachable(e);
          return;
        }
        setUnreachable(null);
        const body = (e as { body?: unknown }).body;
        const why = quoteRefusal(body);
        setQuote(null);
        setError(errorMessage(body));
        setRefusal(why);
        if (why && "tip_presets" in why) setPresets(why.tip_presets ?? null);
      });
    return () => {
      live = false;
    };
  }, [bag.restaurantId, lines, bag.tip, point, attempt]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (lines.length === 0) {
    return (
      <SafeAreaView style={[styles.screen, { alignItems: "center", justifyContent: "center", gap: space[4] }]}>
        <Txt variant="h2">{t("checkout.empty_title")}</Txt>
        <Button title={t("checkout.find_food")} onPress={() => router.replace("/home")} />
      </SafeAreaView>
    );
  }

  // Tip choices are the city's (its tip_presets rule), as on the website.
  const tips = [0, ...new Set((presets?.amounts ?? []).map(Number).filter((n) => Number.isFinite(n) && n > 0))];
  // Under the minimum: worded in the app's language, the amount in the country's format (no ".00").
  const shownError =
    refusal?.code === "MIN_ORDER" && refusal.zone && refusal.amount
      ? t("checkout.min_order", { zone: refusal.zone, amount: money(refusal.amount, refusal.currency, { whole: true }) })
      : error;
  const held = quote ? Math.max(0, Math.floor((new Date(quote.expires_at).getTime() - now) / 1000)) : 0;

  async function placeOrder(): Promise<string> {
    const order = unwrap(await api.core.POST("/api/v1/orders", {
      params: { header: { "X-Idempotency-Key": quote!.quote_id } },
      body: {
        restaurant_id: bag.restaurantId!, items: cartItems(lines), payment_method: method, quote_token: quote!.token,
        delivery_address: { street: point!.street, city: point!.city, state: point!.state, zip: point!.zip || "000000", country: point!.country || country?.code || "" },
      },
    })) as { id: string };
    return order.id;
  }

  async function settle(orderId: string) {
    const status = await waitForPayment(orderId);
    if (status.payment_status === "succeeded") {
      bag.clear();
      router.replace(`/order/${orderId}`);
    } else {
      router.replace({ pathname: "/payment-failed", params: { orderId, method, provider: provider ?? "fake" } });
    }
  }

  /** Stripe PaymentSheet (US with Stripe keys): cards, Google Pay; 3-D Secure inside the sheet. */
  async function payStripe() {
    if (!quote || !point) return;
    setPaying(true);
    setError(null);
    try {
      const orderId = await placeOrder();
      const r = await payWithStripe(orderId, method);
      if (r.kind === "paid") await settle(orderId);
      else if (r.kind === "failed") router.replace({ pathname: "/payment-failed", params: { orderId, method, provider: "stripe" } });
      else if (r.kind === "unavailable") setError(t("checkout.stripe_update_app"));
      // cancelled: stay on the bag; the order waits with its price held
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body));
    } finally {
      setPaying(false);
    }
  }

  async function pay(outcome: PayOutcome) {
    if (!quote || !point) return;
    setSheet(false);
    setPaying(true);
    setError(null);
    try {
      const orderId = await placeOrder();
      await startPayment(orderId, method, outcome);
      await settle(orderId);
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body));
    } finally {
      setPaying(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.top}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}>
          <Icon name="back" />
        </Pressable>
        <Txt variant="h2" accessibilityRole="header" style={{ flex: 1 }}>{t("kitchen.your_bag")}</Txt>
        {quote ? (
          <View style={styles.held} testID="price-held">
            <Text style={[type.small, num, { color: color.peacock }]}>
              {t("app.bag.held", { time: `${Math.floor(held / 60)}:${String(held % 60).padStart(2, "0")}` })}
            </Text>
          </View>
        ) : null}
      </View>
      <ScrollView testID="bag" contentContainerStyle={{ paddingHorizontal: space[5], paddingVertical: space[2], gap: space[3] }}>
        <View style={styles.card}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={[type.label, { flex: 1 }]} numberOfLines={1}>{point ? (point.label || t("app.home.current_location")) : ""}</Text>
          </View>
          <View style={styles.rule} />
          {lines.map((l) => (
            <View key={l.key} style={styles.line}>
              <Text style={[type.small, { flex: 1 }]}>
                {l.quantity > 1 ? `${l.quantity} × ` : ""}{l.name}
                {l.summary ? <Text style={{ color: color.muted }}> · {l.summary}</Text> : null}
              </Text>
              <Text style={[type.small, num]}>{money(l.unitPrice * l.quantity, currency, { whole: true })}</Text>
            </View>
          ))}
        </View>
        <View style={styles.card}>
          <Text style={type.label}>
            {t("checkout.tip_title")} <Text style={[textFont("400"), { color: color.muted }]}>· {t("checkout.tip_note")}</Text>
          </Text>
          <Segmented
            label={t("checkout.tip_title")}
            value={String(bag.tip)}
            onChange={(v) => bag.setTip(Number(v))}
            options={tips.map((n) => ({ value: String(n), label: n === 0 ? t("checkout.tip_none") : money(n, currency, { whole: true }) }))}
          />
        </View>
        {quote ? <View testID="fair-bill"><FairBill lines={quote.lines} currency={quote.currency} /></View>
          : unreachable ? <LoadError error={unreachable} onRetry={() => setAttempt((a) => a + 1)} />
          : error ? null : <ActivityIndicator color={color.peacock} />}
        {shownError ? <Text style={[type.label, { color: color.chili }]}>{shownError}</Text> : null}
      </ScrollView>
      <View style={styles.footer}>
        <View style={styles.method}>
          <View style={styles.methodTag}><Text style={type.caption}>{t(`checkout.method_${method}`)}</Text></View>
          <Text style={[type.small, { flex: 1 }]}>
            <Text style={textFont("700")}>{t(`checkout.method_${method}`)}</Text>
            <Text style={{ color: color.muted }}> · {t(`checkout.method_${method}_sub`)}</Text>
          </Text>
        </View>
        {point?.browse ? (
          // A city picked on "Change city" is for browsing: the order needs a real address.
          <Button testID="set-location" title={t("location.set")} size="lg" block onPress={() => router.push("/where")} />
        ) : (
          <Button
            testID="pay"
            title={quote ? t("checkout.pay_amount", { amount: money(quote.total, quote.currency) }) : t("checkout.pay")}
            size="lg"
            block
            loading={paying}
            disabled={!quote || held === 0 || provider == null}
            onPress={() => (provider === "stripe" ? void payStripe() : setSheet(true))}
          />
        )}
      </View>
      <Sheet visible={sheet} onClose={() => setSheet(false)} title={t("checkout.test_title")}
        footer={
          <View style={{ gap: space[2] }}>
            <Button testID="pay-approve" title={t("checkout.test_approve", { amount: quote ? money(quote.total, quote.currency) : "" })} size="lg" block onPress={() => pay("approve")} />
            <Button testID="pay-decline" title={t("checkout.test_decline")} variant="secondary" block onPress={() => pay("decline")} />
          </View>
        }>
        <Txt variant="small" style={{ color: color.muted }}>{t("checkout.test_body")}</Txt>
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
