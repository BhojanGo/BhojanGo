// Which way the website takes payments (R19), from two build-time values:
// NEXT_PUBLIC_PAYMENTS_PROVIDER (the provider the site was built for) and the
// environment (APP_ENV, inlined for the browser as NEXT_PUBLIC_APP_ENV by next.config.mjs).
//
// - "test": local, CI and QA run the fake provider: a test card can be saved, the
//   fake checkout "pays" (nothing is charged). Unset means fake, outside production.
// - "live": a real provider (stripe, razorpay): cards are entered in the provider's form.
// - "unavailable": production with no provider, or with "fake": fail closed, never the
//   fake card form or the fake checkout; "Payments aren't available in this city yet".

export type PaymentsMode = "test" | "live" | "unavailable";

export function isProductionEnv(appEnv: string | null | undefined): boolean {
  return String(appEnv ?? "").trim().toLowerCase() === "production";
}

export function paymentsMode(provider: string | null | undefined, appEnv: string | null | undefined): PaymentsMode {
  const p = String(provider ?? "").trim().toLowerCase();
  const fake = p === "" || p === "fake";
  if (!fake) return "live";
  return isProductionEnv(appEnv) ? "unavailable" : "test";
}

/** This build's mode (the values are inlined at build time). */
export const PAYMENTS_MODE: PaymentsMode = paymentsMode(process.env.NEXT_PUBLIC_PAYMENTS_PROVIDER, process.env.NEXT_PUBLIC_APP_ENV);

/** Whether the checkout may open the fake gateway the API answered with (never in production). */
export function fakeCheckoutAllowed(appEnv: string | null | undefined = process.env.NEXT_PUBLIC_APP_ENV): boolean {
  return !isProductionEnv(appEnv);
}
