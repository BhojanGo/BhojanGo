// Payout set-up (R10), shared by BhojanGo Kitchen and BhojanGo Delivery: what the
// Payouts screen says and offers for the payee's account, from
// GET /api/v1/finance/payout-accounts/me/setup. The country's provider comes from
// Markets via the API (stripe_connect, razorpay_route, fake, or null when the
// country has none yet); nothing here knows a country.
//
// Pure logic only (node --test runs it); each app draws it in its own theme.

export type PayoutState = "not_started" | "in_progress" | "action_needed" | "ready";

export interface PayoutAccount {
  id: string; provider: string; state: PayoutState; details_submitted: boolean; payouts_enabled: boolean;
  requirements_due: string[]; disabled_reason: string | null; payout_error: string | null;
}

export interface PayoutSetup {
  provider: string | null; hosted_onboarding: boolean; state: PayoutState; account: PayoutAccount | null;
}

type T = (key: string, vars?: Record<string, string | number>) => string;

// data-ok: payment provider brand names (Markets payout_provider values), not places or currencies.
const BRANDS: Record<string, string> = { stripe_connect: "Stripe", razorpay_route: "Razorpay" };

/** "Stripe", "Razorpay", or "our payments partner" in the language. */
export function providerName(t: T, provider: string | null | undefined): string {
  return (provider && BRANDS[provider]) || t("payout_setup.our_partner");
}

export interface PayoutCopy {
  /** The badge: Not set up / In progress / Action needed / Ready. */
  badge: string;
  tone: "neutral" | "progress" | "warning" | "good";
  body: string;
  /** The button, or null when there is nothing to do (ready, or no provider yet). */
  action: string | null;
  /** Show "When you're done, come back…" (set-up happens on the provider's pages). */
  comeBack: boolean;
}

const TONE: Record<PayoutState, PayoutCopy["tone"]> = { not_started: "neutral", in_progress: "progress", action_needed: "warning", ready: "good" };

/** What the Payouts screen says for this set-up. */
export function payoutCopy(t: T, s: PayoutSetup): PayoutCopy {
  const provider = providerName(t, s.account?.provider ?? s.provider);
  const badge = t(`payout_setup.state.${s.state}`);
  const tone = TONE[s.state];
  if (!s.provider && !s.account) return { badge, tone, body: t("payout_setup.not_available"), action: null, comeBack: false };
  const a = s.account;
  const hosted = s.hosted_onboarding;
  switch (s.state) {
    case "ready":
      return { badge, tone, body: t("payout_setup.body_ready", { provider }), action: null, comeBack: false };
    case "action_needed": {
      const due = a?.requirements_due.length ?? 0;
      const body = a?.payout_error ? t("payout_setup.body_payout_failed", { provider, reason: a.payout_error })
        : due > 0 ? t("payout_setup.body_action_needed", { provider, count: due }) : t("payout_setup.body_action_generic", { provider });
      return { badge, tone, body, action: hosted ? t("payout_setup.fix_with", { provider }) : null, comeBack: hosted };
    }
    case "in_progress": {
      const review = Boolean(a?.details_submitted);
      return { badge, tone, body: t(review ? "payout_setup.body_in_review" : "payout_setup.body_in_progress", { provider }),
        action: hosted && !review ? t("payout_setup.continue_with", { provider }) : null, comeBack: hosted && !review };
    }
    default:
      return { badge, tone, body: t("payout_setup.body_not_started", { provider }),
        action: hosted ? t("payout_setup.set_up_with", { provider }) : t("payout_setup.set_up"), comeBack: hosted };
  }
}

/** Statement statuses each app labels (anything else is shown as sent). */
export const STATEMENT_STATUSES = ["paid", "pending", "no_account", "onboarding", "failed", "reversed"] as const;
