// Cancelling an order (R8, as the website's tracking page): shown only while
// GET /orders/{id} says the customer may (customer_cancel: the API's rule, not
// worked out here). One confirmation that says what happens to the money, then
// the cancelled state and the refund line. If the kitchen started cooking while
// the screen was open, the API answers 409 and the screen says so plainly.
import { api, ApiError, Button, color, inZone, radius, space, Txt, type, unwrap, useI18n } from "@bhojango/mobile-core";
import { useState } from "react";
import { Text, View } from "react-native";

import type { Order } from "../lib/contract";

type T = ReturnType<typeof useI18n>["t"];

function payLabel(t: T, method: string): string {
  const key = `account.pay.${method}`;
  return t(key) === key ? method : t(key);
}

export function CancelOrder({ order, onDone, onRefresh }: { order: Order; onDone: (o: Order) => void; onRefresh: () => void }) {
  const { t, bill, time } = useI18n();
  const c = order.customer_cancel;
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  if (!c) return problem ? <Text accessibilityLiveRegion="polite" style={[type.small, { color: color.chili }]}>{problem}</Text> : null;
  const refund = Number(c.refund);

  async function cancel() {
    setBusy(true);
    setProblem(null);
    try {
      const r = await api.core.POST("/api/v1/orders/{order_id}/cancel", { params: { path: { order_id: order.id } }, body: { reason: "customer_cancelled" } });
      onDone(unwrap(r) as Order);
    } catch (e) {
      const late = e instanceof ApiError && e.status === 409;
      setProblem(late ? t("track.cancel_too_late") : t("track.cancel_failed"));
      setAsking(false);
      if (late) onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="cancel-order" style={{ gap: space[3], padding: space[4], borderRadius: radius.card, borderWidth: 1, borderColor: color.line }}>
      {!asking ? (
        <>
          <Txt variant="small" style={{ color: color.muted }}>
            {c.until ? t("track.cancel_until", { time: time(c.until, inZone(order.time_zone)) }) : t("track.cancel_before_accept")}
          </Txt>
          <Button testID="cancel-open" title={t("track.cancel")} variant="secondary" onPress={() => setAsking(true)} />
        </>
      ) : (
        <View accessibilityRole="alert" style={{ gap: space[3] }}>
          <Txt variant="h3" accessibilityRole="header">{t("track.cancel_title")}</Txt>
          <Txt style={{ color: color.muted }}>
            {refund > 0 ? t("track.cancel_refund", { amount: bill(refund, order.currency), method: payLabel(t, c.refund_to) }) : t("track.cancel_nothing")}
          </Txt>
          <Button testID="cancel-confirm" title={busy ? t("track.cancelling") : t("track.cancel_yes")} variant="danger" loading={busy} onPress={() => void cancel()} />
          <Button testID="cancel-keep" title={t("track.cancel_keep")} variant="secondary" disabled={busy} onPress={() => setAsking(false)} />
        </View>
      )}
      {problem ? <Text accessibilityLiveRegion="polite" style={[type.small, { color: color.chili }]}>{problem}</Text> : null}
    </View>
  );
}

/** A cancelled order: what came back and where (nothing when nothing was charged). */
export function RefundLine({ order }: { order: Order }) {
  const { t, bill } = useI18n();
  const paid = (order.status_history as { status: string }[] | undefined)?.some((h) => h.status === "placed");
  if (!order.refunded && !paid) return null;
  const text = order.refunded
    ? t("track.refunded", { amount: bill(order.refunded, order.currency), method: payLabel(t, order.payment_method) })
    : t("track.refund_pending", { amount: bill(order.total, order.currency), method: payLabel(t, order.payment_method) });
  return (
    <View testID="refund-line" style={{ padding: space[4], borderRadius: radius.card, backgroundColor: color.peacockMist }}>
      <Txt style={{ color: color.peacockDeep }}>{text}</Txt>
    </View>
  );
}
