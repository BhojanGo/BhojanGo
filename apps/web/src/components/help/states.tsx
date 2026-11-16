// Help centre layout and states (F9): page width and the error panel. (No loading.tsx: a
// streamed page can't answer 404 for a missing article; the reads are cached for a minute.)
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
