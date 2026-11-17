// Paying for an order. GET /payments/provider says which checkout the server
// uses for the order's country:
// * "stripe" (a country whose server has Stripe keys): Stripe PaymentSheet (cards,
//   Google Pay, Apple Pay once configured; 3-D Secure inside the sheet). The order
//   is placed by Stripe's webhook; the app then waits for it.
// * otherwise (no live keys for that country, local): the app's own test
//   sheet, standing in for the provider; the chosen outcome travels as the
//   payment method id.
import { api, unwrap } from "@bhojango/mobile-core";

import { isStripeCheckout, sheetParams } from "./stripeSheet";

export type PayOutcome = "approve" | "decline";
export type Provider = "stripe" | "razorpay" | "fake";

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

/** Which checkout the server opens for this country (decided by its keys, not by the app). */
export async function paymentProvider(country: string): Promise<Provider> {
  const r = unwrap(await api.core.GET("/api/v1/payments/provider", { params: { query: { country } } }));
  return r.provider;
}

type StripeSdk = typeof import("@stripe/stripe-react-native");
let sdk: StripeSdk | null | undefined;
/** The Stripe native module, or null in a build made before it was added (rebuild the APK). */
function stripeSdk(): StripeSdk | null {
  if (sdk === undefined) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      sdk = require("@stripe/stripe-react-native") as StripeSdk;
    } catch {
      sdk = null;
    }
  }
  return sdk;
}

export type SheetResult = { kind: "paid" } | { kind: "cancelled" } | { kind: "failed"; message: string } | { kind: "unavailable" };

/**
 * Stripe PaymentSheet for an order waiting for payment: initiate (the server
 * creates or reuses the PaymentIntent), open the sheet, and report what the
 * customer did. "paid" means Stripe accepted it; the webhook places the order.
 */
export async function payWithStripe(orderId: string, method: "upi" | "card", who: { name?: string; email?: string; phone?: string } = {}): Promise<SheetResult> {
  const stripe = stripeSdk();
  if (!stripe) return { kind: "unavailable" };
  const init = unwrap(await api.core.POST("/api/v1/payments/initiate", { body: { order_id: orderId, payment_method_type: method } }));
  const c = init.checkout as unknown;
  if (!isStripeCheckout(c)) return { kind: "unavailable" };
  await stripe.initStripe({ publishableKey: c.publishable_key, urlScheme: "bhojango" });
  const ready = await stripe.initPaymentSheet(sheetParams(c, who));
  if (ready.error) return { kind: "failed", message: ready.error.message };
  const r = await stripe.presentPaymentSheet();
  if (!r.error) return { kind: "paid" };
  if (r.error.code === "Canceled") return { kind: "cancelled" };
  return { kind: "failed", message: r.error.message };
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
