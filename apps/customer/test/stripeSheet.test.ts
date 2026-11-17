// node --test: what Stripe PaymentSheet is opened with (lib/stripeSheet.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { isStripeCheckout, sheetParams, STRIPE_RETURN_URL } from "../lib/stripeSheet.ts";

const CHECKOUT = {
  sdk: "stripe_payment_sheet" as const, publishable_key: "pk_test_x", payment_intent_client_secret: "pi_1_secret_y",
  merchant_display_name: "BhojanGo", customer_id: "cus_1", customer_ephemeral_key: "ek_1", currency: "USD",
  apple_pay: { merchant_country_code: "US" }, google_pay: { merchant_country_code: "US", test_env: true },
};

test("only a complete Stripe payload opens the sheet (the fake and Razorpay don't)", () => {
  assert.equal(isStripeCheckout(CHECKOUT), true);
  assert.equal(isStripeCheckout({ sdk: "fake" }), false);
  assert.equal(isStripeCheckout({ ...CHECKOUT, publishable_key: "" }), false);
  assert.equal(isStripeCheckout(null), false);
});

test("sheet: the intent, the saved customer, Google Pay in the test environment, the return link", () => {
  const p = sheetParams(CHECKOUT, { email: "e@example.com" });
  assert.equal(p.paymentIntentClientSecret, "pi_1_secret_y");
  assert.equal(p.customerId, "cus_1");
  assert.equal(p.customerEphemeralKeySecret, "ek_1");
  assert.deepEqual(p.googlePay, { merchantCountryCode: "US", testEnv: true, currencyCode: "USD" });
  assert.equal(p.applePay, undefined); // no Apple Pay merchant id configured
  assert.equal(p.returnURL, STRIPE_RETURN_URL);
  assert.deepEqual(p.defaultBillingDetails, { email: "e@example.com" });
});

test("production payloads never ask for Google Pay's test environment", () => {
  const p = sheetParams({ ...CHECKOUT, google_pay: { merchant_country_code: "US" } });
  assert.equal(p.googlePay?.testEnv, false);
  const noCustomer = sheetParams({ ...CHECKOUT, customer_id: undefined });
  assert.equal("customerId" in noCustomer, false);
});
