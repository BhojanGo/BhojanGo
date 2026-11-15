"use client";
// Paying for an order on the web. /payments/initiate says which checkout to
// open (the gateway follows the order's country): the provider's own page
// (Razorpay Checkout, Stripe Payment Element) with live keys, or the local
// fake one, which "pays" by calling its complete_path. The provider's webhook
// (or Razorpay's verified signature) then places the order; we wait for it.
import { unwrap, type CoreSchemas } from "@bhojango/api-client";

import { api, authed } from "@/lib/client";

export type Initiated = CoreSchemas["PaymentInitiateResponse"];
export type PayType = "card" | "upi" | "net_banking";

export interface PayStatus {
  order_status: string;
  payment_status: string;
  failure_reason: string | null;
  can_retry: boolean;
  price_held_until: string | null;
}

export async function paymentStatus(orderId: string): Promise<PayStatus> {
  return unwrap(await api.core.GET("/api/v1/payments/orders/{order_id}/status", { params: { path: { order_id: orderId } } })) as unknown as PayStatus;
}

/** Wait (bounded) until the payment settles. */
export async function waitForPayment(orderId: string, timeoutMs = 30000): Promise<PayStatus> {
  const end = Date.now() + timeoutMs;
  for (;;) {
    const s = await paymentStatus(orderId);
    if (s.payment_status === "succeeded" || s.payment_status === "failed" || Date.now() > end) return s;
    await new Promise<void>((r) => setTimeout(r, 1000));
  }
}

const loaded = new Map<string, Promise<void>>();
/** Load a provider's script once (allowed by the site's CSP: next.config.mjs). */
export function loadScript(src: string): Promise<void> {
  let p = loaded.get(src);
  if (!p) {
    p = new Promise<void>((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => {
        loaded.delete(src);
        reject(new Error(`could not load ${src}`));
      };
      document.head.appendChild(s);
    });
    loaded.set(src, p);
  }
  return p;
}

/** The local fake gateway: finish the payment as approved or declined. */
export async function completeFake(checkout: Record<string, unknown>, outcome: "succeeded" | "failed"): Promise<void> {
  await authed("POST", String(checkout.complete_path), { outcome });
}

interface RazorpayResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}
type RazorpayCtor = new (o: Record<string, unknown>) => { open: () => void; on: (ev: string, cb: (e: unknown) => void) => void };

/** Razorpay Checkout (UPI, cards, netbanking): resolves once the signature is verified. */
export async function payWithRazorpay(c: Record<string, unknown>, dismissed: string): Promise<void> {
  await loadScript("https://checkout.razorpay.com/v1/checkout.js");
  const Razorpay = (window as unknown as { Razorpay: RazorpayCtor }).Razorpay;
  await new Promise<void>((resolve, reject) => {
    const rz = new Razorpay({
      key: c.key_id,
      order_id: c.order_id,
      amount: c.amount,
      currency: c.currency,
      name: c.name,
      prefill: c.prefill,
      method: c.method,
      theme: { color: "#0B5D66" },
      handler: (r: RazorpayResponse) => {
        authed("POST", "/api/v1/payments/razorpay/verify", r).then(() => resolve(), reject);
      },
      modal: { ondismiss: () => reject(new Error(dismissed)) },
    });
    rz.on("payment.failed", () => undefined); // Razorpay lets the person retry inside its sheet
    rz.open();
  });
}

interface StripeLike {
  elements: (o: { clientSecret: string; appearance?: unknown }) => { create: (kind: string) => { mount: (el: HTMLElement) => void; destroy: () => void } };
  confirmPayment: (o: { elements: unknown; redirect: "if_required"; confirmParams: { return_url: string } }) => Promise<{ error?: { message?: string } }>;
}

/** Stripe Payment Element: mount it into `el`; returns confirm() and a cleanup. */
export async function mountStripe(c: Record<string, unknown>, el: HTMLElement) {
  await loadScript("https://js.stripe.com/v3");
  const stripe = (window as unknown as { Stripe: (pk: string) => StripeLike }).Stripe(String(c.publishable_key));
  const elements = stripe.elements({ clientSecret: String(c.payment_intent_client_secret), appearance: { variables: { colorPrimary: "#0B5D66", borderRadius: "12px" } } });
  const payment = elements.create("payment");
  payment.mount(el);
  return {
    confirm: async (returnUrl: string) => {
      const r = await stripe.confirmPayment({ elements, redirect: "if_required", confirmParams: { return_url: returnUrl } });
      if (r.error) throw new Error(r.error.message ?? "declined");
    },
    destroy: () => payment.destroy(),
  };
}
