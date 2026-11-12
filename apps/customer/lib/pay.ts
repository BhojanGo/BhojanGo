// Paying for an order. Locally the payment provider is the fake one: the app
// shows its own checkout sheet (standing in for Stripe PaymentSheet or
// Razorpay Checkout) and the chosen outcome travels as the payment method id.
// With real keys the provider SDKs take the payload from /payments/initiate.
import { api, unwrap } from "@bhojango/mobile-core";

export type PayOutcome = "approve" | "decline";

export interface PayStatus {
  order_status: string;
  payment_status: string;
  failure_reason: string | null;
  can_retry: boolean;
  price_held_until: string | null;
  amount: number;
  currency: string;
}

export async function startPayment(orderId: string, method: "upi" | "card", outcome: PayOutcome): Promise<void> {
  unwrap(await api.core.POST("/api/v1/payments/initiate", {
    body: { order_id: orderId, payment_method_type: method, payment_method_id: outcome === "decline" ? "fake_decline" : "fake_ok" },
  }));
}

export async function paymentStatus(orderId: string): Promise<PayStatus> {
  return unwrap(await api.core.GET("/api/v1/payments/orders/{order_id}/status", { params: { path: { order_id: orderId } } })) as unknown as PayStatus;
}

/** Wait until the payment settles (the provider's webhook places or fails the order). */
export async function waitForPayment(orderId: string, timeoutMs = 30000): Promise<PayStatus> {
  const end = Date.now() + timeoutMs;
  for (;;) {
    const s = await paymentStatus(orderId);
    if (s.payment_status === "succeeded" || s.payment_status === "failed" || Date.now() > end) return s;
    await new Promise<void>((r) => setTimeout(r, 1000));
  }
}
