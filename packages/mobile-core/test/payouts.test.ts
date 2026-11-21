// node --test: what the Payouts screens say for each payout set-up state (R10).
import assert from "node:assert/strict";
import test from "node:test";

import { payoutCopy, providerName, type PayoutAccount, type PayoutSetup, weekLabel, weekStatus } from "../src/payouts.ts";

// A stand-in translator: the key and its variables, so the test reads which text was chosen.
const t = (key: string, vars?: Record<string, string | number>) =>
  key === "payout_setup.our_partner" ? "our payments partner" : vars ? `${key}(${Object.entries(vars).map(([k, v]) => `${k}=${v}`).join(",")})` : key;

const account = (over: Partial<PayoutAccount> = {}): PayoutAccount => ({
  id: "a", provider: "stripe_connect", state: "in_progress", details_submitted: false, payouts_enabled: false,
  requirements_due: [], disabled_reason: null, payout_error: null, ...over,
});
const stripe = (over: Partial<PayoutSetup>): PayoutSetup => ({ provider: "stripe_connect", hosted_onboarding: true, state: "not_started", account: null, ...over });

test("brand names come from the provider; anything else is our payments partner", () => {
  assert.equal(providerName(t, "stripe_connect"), "Stripe");
  assert.equal(providerName(t, "razorpay_route"), "Razorpay");
  assert.equal(providerName(t, "fake"), "our payments partner");
  assert.equal(providerName(t, null), "our payments partner");
});

test("not started: Set up payouts with Stripe, and come back afterwards", () => {
  const c = payoutCopy(t, stripe({}));
  assert.equal(c.action, "payout_setup.set_up_with(provider=Stripe)");
  assert.equal(c.badge, "payout_setup.state.not_started");
  assert.equal(c.comeBack, true);
  assert.equal(payoutCopy(t, { provider: "fake", hosted_onboarding: false, state: "not_started", account: null }).action, "payout_setup.set_up");
});

test("in progress: continue on Stripe; once submitted, Stripe is checking and there is no button", () => {
  assert.equal(payoutCopy(t, stripe({ state: "in_progress", account: account() })).action, "payout_setup.continue_with(provider=Stripe)");
  const review = payoutCopy(t, stripe({ state: "in_progress", account: account({ details_submitted: true }) }));
  assert.equal(review.action, null);
  assert.equal(review.body, "payout_setup.body_in_review(provider=Stripe)");
});

test("action needed counts what Stripe still needs, or says why the bank payout failed", () => {
  const due = payoutCopy(t, stripe({ state: "action_needed", account: account({ state: "action_needed", details_submitted: true, requirements_due: ["a", "b"] }) }));
  assert.equal(due.body, "payout_setup.body_action_needed(provider=Stripe,count=2)");
  assert.equal(due.action, "payout_setup.fix_with(provider=Stripe)");
  assert.equal(due.tone, "warning");
  const bank = payoutCopy(t, stripe({ state: "action_needed", account: account({ payouts_enabled: true, payout_error: "account closed" }) }));
  assert.equal(bank.body, "payout_setup.body_payout_failed(provider=Stripe,reason=account closed)");
});

test("ready: paid every Monday, nothing to do; a country without a provider says so", () => {
  const ready = payoutCopy(t, stripe({ state: "ready", account: account({ state: "ready", payouts_enabled: true }) }));
  assert.deepEqual([ready.action, ready.tone, ready.body], [null, "good", "payout_setup.body_ready(provider=Stripe)"]);
  const none = payoutCopy(t, { provider: null, hosted_onboarding: false, state: "not_started", account: null });
  assert.deepEqual([none.action, none.body], [null, "payout_setup.not_available"]);
});

// R27: a week's status is the API's shown_status, the same as admin Finance's; never "on its way" without a transfer.
test("a week's status comes from the API's shown_status", () => {
  const day = (d: string) => `day(${d})`;
  const label = (s: { status: string; shown_status?: string | null; paid_on?: string | null }) => weekLabel(t, "rider.payouts.status", s, day);
  // R26: the statement said "pending" and the app showed "On its way" while payouts weren't set up.
  assert.equal(label({ status: "pending", shown_status: "no_account" }), "rider.payouts.status.no_account");
  assert.equal(label({ status: "pending", shown_status: "waiting_approval" }), "rider.payouts.status.waiting_approval");
  assert.equal(label({ status: "paid", shown_status: "paid", paid_on: "2026-11-16" }), "rider.payouts.status.paid_on(date=day(2026-11-16T12:00:00))");
  assert.equal(label({ status: "paid", shown_status: "paid" }), "rider.payouts.status.paid");
  assert.equal(label({ status: "pending", shown_status: "on_its_way" }), "rider.payouts.status.on_its_way");
  // Told as their own note, or by the below-zero lines.
  assert.equal(label({ status: "failed", shown_status: "failed" }), null);
  assert.equal(label({ status: "carried", shown_status: "carried" }), null);
  // An older API without shown_status: "pending" is "not paid yet", not "on its way".
  assert.equal(weekStatus({ status: "pending" }), "not_paid");
  assert.equal(label({ status: "pending" }), "rider.payouts.status.not_paid");
});
