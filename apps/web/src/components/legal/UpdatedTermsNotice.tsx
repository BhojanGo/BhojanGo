"use client";
// "We've updated our policies: Terms of use, Privacy notice." (R8 F10): once, for a
// signed-in person whose accepted version is older than the one now published.
// Non-blocking: a slim strip under the header, in the page flow (nothing is covered).
// "Got it" records the acceptance of the versions shown and hides it for good.
import { unwrap } from "@bhojango/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, useHydrated, useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";

interface Pending { kind: string; version: number; title: string }
type Kind = "terms" | "privacy" | "kitchen_partner_terms" | "delivery_partner_terms";
const PAGES: Record<string, string> = { terms: "/terms", privacy: "/privacy" };

export function UpdatedTermsNotice() {
  const t = useT();
  const hydrated = useHydrated();
  const access = useSession((s) => s.access);
  // What's pending for which session: signing out (or in as someone else) hides it at once.
  const [state, setState] = useState<{ token: string; items: Pending[] } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!hydrated || !access) return;
    let live = true;
    api.core.GET("/api/v1/me/legal/pending")
      .then((r) => { if (live) setState({ token: access, items: (unwrap(r) as Pending[]) ?? [] }); })
      .catch(() => undefined); // an older API, or offline: no notice
    return () => { live = false; };
  }, [hydrated, access]);

  const pending = hydrated && access && state?.token === access ? state.items : [];
  if (!pending.length) return null;

  async function ok() {
    setBusy(true);
    try {
      await api.core.POST("/api/v1/me/legal/accept", { body: { kinds: pending.map((p) => p.kind as Kind) } });
    } finally {
      setState(null); // dismissed either way; it comes back next visit only if the acceptance didn't save
      setBusy(false);
    }
  }

  return (
    <div role="region" aria-label={t("legal.notice_label")} data-testid="legal-updated-notice"
      className="border-b border-[#B9D6D9] bg-[#EFF6F6] print:hidden">
      <div className="container-page flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
        <p className="min-w-0 flex-[1_1_320px] text-body text-kohl">
          <b>{t("legal.notice_updated")}</b>{" "}
          {pending.map((p, i) => {
            const label = t(`legal.${p.kind}`);
            const href = PAGES[p.kind];
            return (
              <span key={p.kind}>
                {i > 0 ? ", " : ""}
                {href ? <Link href={href} className="font-semibold text-peacock underline underline-offset-2">{label}</Link> : label}
              </span>
            );
          })}
          . <span className="text-muted">{t("legal.notice_agree")}</span>
        </p>
        <button type="button" onClick={() => void ok()} disabled={busy} data-testid="legal-notice-ok"
          className="h-11 shrink-0 rounded-full bg-[#0B5D66] px-5 text-label font-bold text-white hover:bg-[#083F46] disabled:bg-[#8FB3B7]">
          {t("legal.notice_ok")}
        </button>
      </div>
    </div>
  );
}
