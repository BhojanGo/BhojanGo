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

/**
 * A week's status as both apps and admin Finance show it (R27): the API's `shown_status`, derived in one
 * place (core_api finance/service/statements.py, shown_status). "On its way" only once a transfer exists.
 */
export const STATEMENT_STATUSES = ["paid", "nothing_due", "carried", "on_its_way", "no_account", "onboarding",
  "waiting_approval", "not_paid", "failed", "reversed"] as const;

/** Statuses told as a sentence of their own (R12): what happened, the amount, the date it's paid. */
export const STATEMENT_NOTES: readonly string[] = ["failed", "reversed"];

export interface WeekStatus { status: string; shown_status?: string | null; paid_on?: string | null }

/** The week's status code: the API's `shown_status`; an older API's own status, where "pending" was never "on its way". */
export function weekStatus(s: WeekStatus): string {
  return s.shown_status ?? (s.status === "pending" ? "not_paid" : s.status);
}

/**
 * What a statement row says about its week, from `<prefix>.<code>` ("Waiting for approval", "Waiting for your
 * payout account", "Paid on 17 Nov"); null for the statuses told elsewhere (a note: failed, reversed; carried).
 * `date` formats a local day ("2026-11-16T12:00:00") in the app's language.
 */
export function weekLabel(t: T, prefix: string, s: WeekStatus, date: (d: string) => string): string | null {
  const code = weekStatus(s);
  if (STATEMENT_NOTES.includes(code) || code === "carried") return null;
  const day = repayDay(s.paid_on);
  if (code === "paid" && day) return t(`${prefix}.paid_on`, { date: date(day) });
  return (STATEMENT_STATUSES as readonly string[]).includes(code) ? t(`${prefix}.${code}`) : null;
}

/**
 * The day a returned or failed payment is paid again: the API's `repay_on` (the country's
 * next payout day), as a local noon so no time zone moves it to the day before.
 */
export function repayDay(repayOn: string | null | undefined): string | null {
  return repayOn && /^\d{4}-\d{2}-\d{2}$/.test(repayOn) ? `${repayOn}T12:00:00` : null;
}
