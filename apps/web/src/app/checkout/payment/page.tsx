"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

const STRIPE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
const RAZORPAY_KEY_ID = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

let stripePromise: Promise<Stripe | null> | null = null;
function getStripe(): Promise<Stripe | null> {
  if (!stripePromise && STRIPE_PUBLISHABLE_KEY) {
    stripePromise = loadStripe(STRIPE_PUBLISHABLE_KEY);
  }
  return stripePromise ?? Promise.resolve(null);
}

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h1 className="text-xl font-bold text-gray-900 mb-6">{title}</h1>
        {children}
      </div>
    </div>
  );
}

function StripeForm({ orderId }: { orderId: string }) {
  const stripe = useStripe();
  const elements = useElements();
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;
    setSubmitting(true);
    setError("");
    const { error: confirmError, paymentIntent } = await stripe.confirmPayment({
      elements,
      redirect: "if_required",
    });
    if (confirmError) {
      setError(confirmError.message ?? "Payment failed. Please try another method.");
      setSubmitting(false);
      return;
    }
    if (paymentIntent && (paymentIntent.status === "succeeded" || paymentIntent.status === "processing")) {
      router.replace(`/orders/${orderId}?success=true`);
      return;
    }
    setError("Payment could not be completed. Please try again.");
    setSubmitting(false);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <PaymentElement />
      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
      <button
        type="submit"
        disabled={!stripe || submitting}
        className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-lg transition text-sm"
      >
        {submitting ? "Processing…" : "Pay now"}
      </button>
    </form>
  );
}

function RazorpayPayment({
  orderId,
  razorpayOrderId,
  amount,
  currency,
}: {
  orderId: string;
  razorpayOrderId: string;
  amount: number;
  currency: string;
}) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (window.Razorpay) {
      setReady(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => setReady(true);
    script.onerror = () => setError("Could not load the payment gateway. Check your connection.");
    document.body.appendChild(script);
  }, []);

  function openCheckout() {
    if (!window.Razorpay || !RAZORPAY_KEY_ID) {
      setError("Payment gateway is not configured.");
      return;
    }
    const rzp = new window.Razorpay({
      key: RAZORPAY_KEY_ID,
      amount,
      currency,
      order_id: razorpayOrderId,
      name: "BhojanGo",
      description: `Order ${orderId.slice(0, 8).toUpperCase()}`,
      // Server-side webhook is the source of truth; on client success we just navigate.
      handler: () => router.replace(`/orders/${orderId}?success=true`),
      modal: { ondismiss: () => setError("Payment was cancelled. You can retry below.") },
      theme: { color: "#10b981" },
    });
    rzp.open();
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-600">
        You&apos;ll complete your payment securely via Razorpay.
      </p>
      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
      <button
        onClick={openCheckout}
        disabled={!ready}
        className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-lg transition text-sm"
      >
        {ready ? "Pay now" : "Loading…"}
      </button>
    </div>
  );
}

function PaymentInner() {
  const params = useSearchParams();
  const router = useRouter();
  const orderId = params.get("order_id") ?? "";
  const provider = params.get("provider");
  const clientSecret = params.get("client_secret") ?? undefined;
  const razorpayOrderId = params.get("razorpay_order_id") ?? undefined;
  const amount = Number(params.get("amount") ?? 0);
  const currency = params.get("currency") ?? "USD";

  const stripeOptions = useMemo(
    () => (clientSecret ? { clientSecret, appearance: { theme: "stripe" as const } } : undefined),
    [clientSecret]
  );

  if (!orderId || !provider) {
    return (
      <Shell title="Payment">
        <p className="text-sm text-red-600">Missing payment details. Please restart checkout.</p>
        <button
          onClick={() => router.replace("/")}
          className="mt-4 w-full py-2.5 bg-gray-100 rounded-lg text-sm font-medium"
        >
          Back to home
        </button>
      </Shell>
    );
  }

  if (provider === "mock") {
    return (
      <Shell title="Payment simulated">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Simulated payment completed for this SPR-03B order/payment contract.
          </p>
          <p className="text-xs text-gray-500">
            Amount: {currency} {amount}
          </p>
          <button
            onClick={() => router.replace(`/orders/${orderId}?success=true`)}
            className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-700 text-white font-semibold rounded-lg transition text-sm"
          >
            Continue
          </button>
        </div>
      </Shell>
    );
  }

  if (provider === "stripe") {
    if (!STRIPE_PUBLISHABLE_KEY || !stripeOptions) {
      return (
        <Shell title="Payment unavailable">
          <p className="text-sm text-red-600">
            Card payments are not configured (missing NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY).
          </p>
        </Shell>
      );
    }
    return (
      <Shell title="Complete your payment">
        <Elements stripe={getStripe()} options={stripeOptions}>
          <StripeForm orderId={orderId} />
        </Elements>
      </Shell>
    );
  }

  if (provider === "razorpay" && razorpayOrderId) {
    return (
      <Shell title="Complete your payment">
        <RazorpayPayment
          orderId={orderId}
          razorpayOrderId={razorpayOrderId}
          amount={amount}
          currency={currency}
        />
      </Shell>
    );
  }

  return (
    <Shell title="Payment">
      <p className="text-sm text-red-600">Unsupported payment provider.</p>
    </Shell>
  );
}

export default function PaymentPage() {
  return (
    <Suspense fallback={<Shell title="Loading payment…">{null}</Shell>}>
      <PaymentInner />
    </Suspense>
  );
}
