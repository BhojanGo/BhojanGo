// The order case in Operations → Support (R27): its timeline and what is left to refund.
// Pure (no React, no imports but money), so `node --test` covers it.
//
// R26: #22C450 was cancelled and refunded in full, yet the panel still offered a refund;
// the panel didn't say what had been refunded; and the timeline showed only some steps
// (no paid, almost ready or picked up).
import { money } from "./money.ts";

export interface CaseItem { menu_item_id: string; name: string; quantity: number; total: number }
export interface CaseRefund {
  id: string; amount: number; status: string; kind?: string | null; reason?: string | null; created_at: string;
  lines?: { menu_item_id?: string; code?: string; name?: string; quantity?: number; amount?: string | number }[] | null;
}
/** The order's payment (GET /payments/{order_id}), amounts in minor units. */
export interface CasePayment { amount: number; refunded_amount?: number | null; status: string }

/** Each step's words in the timeline (status_history, in the order it happened). */
export const TIMELINE_LABELS: Record<string, string> = {
  pending_payment: "Ordered", placed: "Paid", accepted: "Accepted", preparing: "Cooking", almost_ready: "Almost ready",
  ready: "Ready", picked_up: "Picked up", delivered: "Delivered", cancelled: "Cancelled",
};

export interface TimelineStep { key: string; label: string; at: string }

/** Every recorded step, oldest first, then each refund (failed ones left out). */
export function timeline(history: { status: string; at: string }[], refunds: CaseRefund[], currency: string): TimelineStep[] {
  const steps = history.map((h, i) => ({ key: `${h.status}-${i}`, label: TIMELINE_LABELS[h.status] ?? h.status, at: h.at }));
  const back = refunds.filter((r) => r.status !== "failed").map((r) => ({
    key: `refund-${r.id}`, label: `Refunded ${money(r.amount / 100, currency, 2)}`, at: r.created_at }));
  return [...steps, ...back].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
}

export type ItemLeft<T extends CaseItem = CaseItem> = T & { refunded: number; refundedAmount: number; left: number };

export interface RefundState<T extends CaseItem = CaseItem> {
  /** Minor units still refundable on the payment (0: nothing). */
  leftMinor: number;
  /** Nothing can be refunded: no captured payment, or all of it given back. */
  closed: boolean;
  /** Why it's closed, for the panel. */
  closedText: string | null;
  items: ItemLeft<T>[];
  deliveryRefunded: boolean;
  /** What was refunded already, one line each ("1 × Butter Croissant refunded $4.51"). */
  done: string[];
}

export function refundState<T extends CaseItem>(items: T[], refunds: CaseRefund[], payment: CasePayment | null, currency: string,
  orderStatus: string): RefundState<T> {
  const given = refunds.filter((r) => r.status !== "failed");
  const qty = new Map<string, number>();
  const amt = new Map<string, number>();
  let deliveryRefunded = false;
  const done: string[] = [];
  for (const r of given) {
    const lines = r.lines ?? [];
    for (const ln of lines) {
      if (ln.menu_item_id) {
        qty.set(ln.menu_item_id, (qty.get(ln.menu_item_id) ?? 0) + Number(ln.quantity ?? 0));
        amt.set(ln.menu_item_id, (amt.get(ln.menu_item_id) ?? 0) + Number(ln.amount ?? 0));
        done.push(`${ln.quantity} × ${ln.name ?? "item"} refunded ${money(Number(ln.amount ?? 0), currency, 2)}`);
      } else if (ln.code === "delivery_fee") {
        deliveryRefunded = true;
        done.push(`Delivery fee refunded ${money(Number(ln.amount ?? 0), currency, 2)}`);
      }
    }
    if (!lines.length) {  // a full refund (cancelled after payment) or an amount (bulk refund): not tied to items
      done.push(`${money(r.amount / 100, currency, 2)} refunded${r.kind === "full" ? " in full" : ""}${r.reason ? ` (${r.reason.replace(/_/g, " ")})` : ""}`);
    }
  }
  const paid = payment && ["succeeded", "partially_refunded", "refunded"].includes(payment.status) ? payment.amount : 0;
  const refundedMinor = Math.max(payment?.refunded_amount ?? 0, given.reduce((n, r) => n + r.amount, 0));
  const leftMinor = Math.max(0, paid - refundedMinor);
  const fullyRefunded = given.some((r) => r.kind === "full") || (paid > 0 && leftMinor === 0);
  const out = items.map((i) => {
    const refunded = Math.min(i.quantity, qty.get(i.menu_item_id) ?? 0);
    return { ...i, refunded, refundedAmount: amt.get(i.menu_item_id) ?? 0, left: fullyRefunded ? 0 : i.quantity - refunded };
  });
  const nothingLeft = !fullyRefunded && paid > 0 && out.every((i) => i.left === 0) && deliveryRefunded;
  const closed = fullyRefunded || !paid || nothingLeft;
  const closedText = fullyRefunded
    ? `${orderStatus === "cancelled" ? "Cancelled and refunded" : "Refunded"} in full: nothing left to refund.`
    : !paid ? "Not paid: nothing to refund."
      : nothingLeft ? "Every item and the delivery fee are refunded: nothing left to refund." : null;
  return { leftMinor, closed, closedText, items: out, deliveryRefunded, done };
}
