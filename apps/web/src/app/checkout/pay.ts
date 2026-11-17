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

interface StripeElement {
  mount: (el: HTMLElement) => void;
  destroy: () => void;
  on: (ev: "ready" | "change" | "loaderror", cb: (e: { complete?: boolean; error?: { message?: string } }) => void) => void;
}
interface StripeLike {
  elements: (o: { clientSecret: string; appearance?: unknown; locale?: string; fonts?: unknown[] }) => { create: (kind: string, o?: unknown) => StripeElement };
  confirmPayment: (o: { elements: unknown; redirect: "if_required"; confirmParams: { return_url: string } }) => Promise<{ error?: { type?: string; message?: string }; paymentIntent?: { status: string } }>;
}

// Stripe.js translates its own form; these of our languages it has (the rest: the browser's choice).
const STRIPE_LOCALES = new Set(["en", "es"]);

/** A test-mode key (pk_test_...): the page says so and shows Stripe's test card. */
export function isStripeTestKey(c: Record<string, unknown>): boolean {
  return String(c.publishable_key ?? "").startsWith("pk_test_");
}

/** Where Stripe sends the customer back after a bank page (3-D Secure, wallets that redirect). */
export function stripeReturnUrl(origin: string, orderId: string): string {
  return `${origin}/checkout/return?order=${encodeURIComponent(orderId)}`;
}

/**
 * Stripe's Payment Element (cards, Apple Pay, Google Pay; 3-D Secure in Stripe's
 * own pop-up): mount it into `el`. `onComplete` follows whether the form is
 * filled in. confirm() resolves once Stripe accepted the payment (or it is
 * processing); the order is placed by the webhook, so callers then wait for it.
 */
export async function mountStripe(c: Record<string, unknown>, el: HTMLElement, language: string, onComplete: (complete: boolean) => void) {
  if (!c.publishable_key || !c.payment_intent_client_secret) throw new Error("stripe checkout without keys");
  await loadScript("https://js.stripe.com/v3");
  const stripe = (window as unknown as { Stripe: (pk: string) => StripeLike }).Stripe(String(c.publishable_key));
  const elements = stripe.elements({
    clientSecret: String(c.payment_intent_client_secret),
    locale: STRIPE_LOCALES.has(language) ? language : "auto",
    appearance: {
      theme: "stripe",
      variables: {
        colorPrimary: "#0B5D66", colorText: "#111418", colorTextSecondary: "#3D4A4E", colorDanger: "#8C1D18",
        fontFamily: "Inter, system-ui, sans-serif", fontSizeBase: "16px", borderRadius: "12px", spacingUnit: "4px",
      },
      rules: { ".Input": { border: "1.5px solid #C9D3D4", boxShadow: "none" }, ".Input:focus": { border: "1.5px solid #0B5D66" } },
    },
  });
  const payment = elements.create("payment", { layout: { type: "tabs" } });
  await new Promise<void>((resolve, reject) => {
    const slow = setTimeout(() => reject(new Error("payment form timed out")), 20000);
    payment.on("ready", () => {
      clearTimeout(slow);
      resolve();
    });
    payment.on("loaderror", (e) => reject(new Error(e.error?.message ?? "load error")));
    payment.on("change", (e) => onComplete(!!e.complete));
    payment.mount(el);
  });
  return {
    confirm: async (returnUrl: string) => {
      const r = await stripe.confirmPayment({ elements, redirect: "if_required", confirmParams: { return_url: returnUrl } });
      if (r.error) throw new Error(r.error.message ?? "declined");
    },
    destroy: () => payment.destroy(),
  };
}
