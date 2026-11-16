// Help centre layout and states (F9): page width, the error panel, skeletons.
import Link from "next/link";
import type { ReactNode } from "react";

import { getContext } from "@/lib/prefs";

/** Content at most 1200 px wide with 16 / 32 / 48 px gutters. */
export function PageWidth({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1200px] px-4 md:px-8 lg:px-12 ${className}`}>{children}</div>;
}

/** core_api didn't answer: say so in plain words; the contact form below still works. */
export async function HelpUnavailable() {
  const { t } = await getContext();
  return (
    <div role="alert" className="rounded-card border border-line bg-white p-6">
      <h2 className="text-h3 text-kohl">{t("helpcentre.error_title")}</h2>
      <p className="mt-2 text-body text-muted">{t("helpcentre.error_body")}</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Link href="/help" className="inline-flex h-11 items-center rounded-pill bg-peacock px-5 text-label font-bold text-white">{t("common.retry")}</Link>
        <a href="#contact" className="inline-flex h-11 items-center rounded-pill border-[1.5px] border-line-strong px-5 text-label font-bold text-kohl">{t("helpcentre.contact_us")}</a>
      </div>
    </div>
  );
}

export function HelpSkeleton({ hero = true }: { hero?: boolean }) {
  return (
    <div className="bg-porcelain pb-16" aria-busy="true">
      {hero ? <div className="h-[260px] bg-peacock-deep md:h-[300px]" /> : null}
      <PageWidth className="space-y-6 pt-10">
        <div className="h-7 w-48 animate-pulse rounded-lg bg-line" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="h-[112px] animate-pulse rounded-card bg-white" />)}
        </div>
      </PageWidth>
    </div>
  );
}
