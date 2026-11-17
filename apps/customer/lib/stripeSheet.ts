// What Stripe PaymentSheet is opened with, from POST /payments/initiate's
// `checkout` (sdk "stripe_payment_sheet"). Pure: no React Native, so node --test
// can check it. Cards, Google Pay (test environment outside production) and
// Apple Pay once a merchant id is configured; 3-D Secure runs inside the sheet.

export interface StripeCheckout {
  sdk: "stripe_payment_sheet";
  publishable_key: string;
  payment_intent_client_secret: string;
  merchant_display_name?: string;
  customer_id?: string;
  customer_ephemeral_key?: string;
  currency?: string;
  apple_pay?: { merchant_country_code?: string };
  google_pay?: { merchant_country_code?: string; test_env?: boolean };
}

/** The app's deep link Stripe returns to after a bank page (app.json "scheme"). */
export const STRIPE_RETURN_URL = "bhojango://stripe-redirect";

export function isStripeCheckout(c: unknown): c is StripeCheckout {
  const x = c as Partial<StripeCheckout> | null;
  return !!x && x.sdk === "stripe_payment_sheet" && !!x.publishable_key && !!x.payment_intent_client_secret;
}

export function sheetParams(c: StripeCheckout, opts: { name?: string; email?: string; phone?: string; applePayMerchant?: string } = {}) {
  const customer = c.customer_id && c.customer_ephemeral_key
    ? { customerId: c.customer_id, customerEphemeralKeySecret: c.customer_ephemeral_key }
    : {};
  const country = c.google_pay?.merchant_country_code ?? c.apple_pay?.merchant_country_code;
  return {
    merchantDisplayName: c.merchant_display_name || "BhojanGo",
    paymentIntentClientSecret: c.payment_intent_client_secret,
    ...customer,
    returnURL: STRIPE_RETURN_URL,
    allowsDelayedPaymentMethods: false,
    defaultBillingDetails: {
      ...(opts.name ? { name: opts.name } : {}),
      ...(opts.email ? { email: opts.email } : {}),
      ...(opts.phone ? { phone: opts.phone } : {}),
    },
    ...(country ? { googlePay: { merchantCountryCode: country, testEnv: c.google_pay?.test_env === true, currencyCode: c.currency } } : {}),
    ...(country && opts.applePayMerchant ? { applePay: { merchantCountryCode: country } } : {}),
    appearance: {
      font: { scale: 1 },
      colors: { primary: "#0B5D66", componentBorder: "#C9D3D4", error: "#8C1D18" },
      shapes: { borderRadius: 12 },
      primaryButton: { shapes: { borderRadius: 999 } },
    },
  };
}
