"use client";
// Content → Help → New article (F9). ?from=<id> starts from another article:
// a translation (same slug, another language) or a country's own version.
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { HelpEditor } from "@/components/content/HelpEditor";
import { useHelpArticle } from "@/lib/content";

function NewArticle() {
  const from = useSearchParams().get("from");
  const src = useHelpArticle(from);
  if (from && src.isLoading) return <div aria-busy="true" className="h-[420px] animate-pulse rounded-2xl bg-white" />;
  const c = src.data ? (src.data.draft ?? src.data.live) : null;
  return (
    <HelpEditor key={from ?? "blank"} article={null} prefill={c && src.data ? {
      ...c, relatedText: c.related.join(", "), slug: src.data.slug, country: src.data.country,
      language: src.data.language === "en" ? "" : "en",
    } : undefined} />
  );
}

export default function Page() {
  return (
    <ConsoleShell section="Help" country="ALL" hideScope>
      <Suspense><NewArticle /></Suspense>
    </ConsoleShell>
  );
}
