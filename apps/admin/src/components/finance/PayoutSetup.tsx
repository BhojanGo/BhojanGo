"use client";

/**
 * A kitchen's or delivery partner's payout set-up (R10): where it stands with the
 * country's payout provider (Stripe Connect Express in the US), what the provider still
 * needs, and a set-up link to copy or send. The link is ours and lasts 7 days; each time
 * it is opened it makes a fresh Stripe page. GET/POST /finance/payees/{kind}/{id}/payout-account.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { adminApi } from "@/lib/api";
import { apiMessage } from "@/lib/ops";
import { count } from "@/lib/count";

export type PayeeKind = "restaurant" | "rider";
export type SetupState = "not_started" | "in_progress" | "action_needed" | "ready";

interface Setup {
  provider: string | null; hosted_onboarding: boolean; state: SetupState;
  account: { provider: string; details_submitted: boolean; payouts_enabled: boolean; requirements_due: string[];
    disabled_reason: string | null; payout_error: string | null; updated_at: string | null } | null;
}

export const SETUP_LABEL: Record<SetupState, string> = {
  not_started: "Not set up", in_progress: "In progress", action_needed: "Action needed", ready: "Ready",
};
const SETUP_STYLE: Record<SetupState, string> = {
  not_started: "bg-line-soft text-muted", in_progress: "bg-[#EAF2FF] text-[#1F4E8C]",
  action_needed: "bg-kesar-tint text-kesar-ink", ready: "bg-peacock-tint text-peacock-dark",
};
// Provider brand names (Markets payout_provider values).
const PROVIDER: Record<string, string> = { stripe_connect: "Stripe Connect", razorpay_route: "Razorpay Route", fake: "Test provider (no money moves)" };

export function SetupPill({ state }: { state: SetupState }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-lg px-2 py-1 text-caption ${SETUP_STYLE[state]}`}>{SETUP_LABEL[state]}</span>;
}

const path = (kind: PayeeKind, id: string) => `/user/finance/payees/${kind}/${id}/payout-account`;

async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Make a set-up link (and maybe send it); copy it when the browser lets us. */
export function useSetupLink(kind: PayeeKind, id: string) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string; link?: string } | null>(null);
  async function make(send: boolean) {
    setBusy(true);
    setMsg(null);
    try {
      const r = (await adminApi.post<Setup & { link: string | null; sent: boolean; expires_in_days: number | null }>(`${path(kind, id)}/link`, { send })).data;
      if (!r.link) {
        setMsg({ ok: true, text: r.state === "ready" ? "Already set up: nothing to send." : "This country's payout provider has no set-up pages; the payee finishes in the app." });
      } else {
        const copied = await copy(r.link);
        const what = send ? "Sent to them (push, email and the app's inbox)" : "Link made";
        setMsg({ ok: true, link: r.link, text: `${what}${copied ? " and copied" : ""}. It works for ${count(r.expires_in_days, "day")}.` });
      }
      await qc.invalidateQueries({ queryKey: ["payout-setup", kind, id] });
      await qc.invalidateQueries({ queryKey: ["payout-run"] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  return { busy, msg, make };
}

function LinkMessage({ msg }: { msg: { ok: boolean; text: string; link?: string } | null }) {
  if (!msg) return null;
  return (
    <div role="status" className="space-y-1">
      <p className={`m-0 text-small ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p>
      {msg.link ? (
        <input readOnly aria-label="Set-up link" value={msg.link} onFocus={(e) => e.currentTarget.select()}
          className="h-9 w-full min-w-[260px] rounded-lg border border-line bg-porcelain px-2 text-small" />
      ) : null}
    </div>
  );
}

/** The panel on a kitchen's or delivery partner's page. */
export function PayoutSetupPanel({ kind, id, name }: { kind: PayeeKind; id: string; name: string }) {
  const [refresh, setRefresh] = useState(false);
  const q = useQuery({
    queryKey: ["payout-setup", kind, id, refresh],
    queryFn: async () => (await adminApi.get<Setup>(path(kind, id), { params: refresh ? { refresh: true } : {} })).data,
    placeholderData: (previous) => previous,
  });
  const link = useSetupLink(kind, id);
  if (q.isError) {
    return (
      <section role="alert" aria-label={`Payouts · ${name}`} className="space-y-2 rounded-2xl bg-white p-6">
        <p className="m-0 text-small">{apiMessage(q.error) === "Something went wrong. Try again." ? "The payout set-up didn't load." : apiMessage(q.error)}</p>
        <button type="button" onClick={() => void q.refetch()} className="h-10 rounded-full border border-line px-4 font-bold text-peacock">Try again</button>
      </section>
    );
  }
  if (!q.data) return <p aria-busy="true" className="rounded-2xl bg-white p-6 text-small text-muted">Loading payout set-up…</p>;
  const d = q.data;
  const provider = d.account?.provider ?? d.provider;
  return (
    <section aria-label={`Payouts · ${name}`} className="space-y-3 rounded-2xl bg-white p-6" data-testid="payout-setup">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="m-0 flex-1 text-h3">Payouts</h2>
        <SetupPill state={d.state} />
      </div>
      <p className="m-0 text-small text-muted">
        {provider ? `Payout provider: ${PROVIDER[provider] ?? provider}.` : "This country has no payout provider yet (Markets → the country → Payouts)."}
        {d.account?.updated_at ? ` Last heard from the provider ${new Date(d.account.updated_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}.` : ""}
      </p>
      {d.account ? (
        <dl className="grid gap-2 rounded-xl bg-porcelain p-4 text-small sm:grid-cols-3">
          <div><dt className="font-bold">Details sent</dt><dd>{d.account.details_submitted ? "Yes" : "Not yet"}</dd></div>
          <div><dt className="font-bold">Payouts enabled</dt><dd>{d.account.payouts_enabled ? "Yes" : "No"}</dd></div>
          <div><dt className="font-bold">Still needed</dt><dd>{d.account.requirements_due.length ? d.account.requirements_due.join(", ") : "Nothing"}</dd></div>
          {d.account.payout_error ? <div className="sm:col-span-3"><dt className="font-bold text-chili">Last bank payout failed</dt><dd>{d.account.payout_error}</dd></div> : null}
          {d.account.disabled_reason ? <div className="sm:col-span-3"><dt className="font-bold">Why it&apos;s on hold</dt><dd>{d.account.disabled_reason}</dd></div> : null}
        </dl>
      ) : <p className="m-0 text-small">They haven&apos;t started. Send them a link, or they can tap Set up payouts in the app.</p>}
      <div className="flex flex-wrap gap-2">
        {d.state !== "ready" && d.hosted_onboarding ? (
          <>
            <button type="button" disabled={link.busy} onClick={() => void link.make(false)} className="h-10 rounded-full bg-peacock px-4 font-bold text-white disabled:opacity-40">Copy set-up link</button>
            <button type="button" disabled={link.busy} onClick={() => void link.make(true)} className="h-10 rounded-full border border-line-strong px-4 font-bold disabled:opacity-40">Send it to them</button>
          </>
        ) : null}
        {d.account && d.state !== "ready" ? (
          <button type="button" disabled={q.isFetching} onClick={() => (refresh ? void q.refetch() : setRefresh(true))}
            className="h-10 rounded-full border border-line-strong px-4 font-bold text-peacock disabled:opacity-40">{q.isFetching ? "Checking…" : "Check with the provider"}</button>
        ) : null}
      </div>
      <LinkMessage msg={link.msg} />
    </section>
  );
}

/** Finance: a statement's "Copy set-up link" for a payee who hasn't finished. */
export function SetupLinkButton({ kind, id }: { kind: PayeeKind; id: string }) {
  const link = useSetupLink(kind, id);
  return (
    <div className="space-y-1">
      <button type="button" disabled={link.busy} onClick={() => void link.make(false)} className="h-8 whitespace-nowrap rounded-full border border-line-strong px-3 text-label disabled:opacity-40">Copy set-up link</button>
      <LinkMessage msg={link.msg} />
    </div>
  );
}
