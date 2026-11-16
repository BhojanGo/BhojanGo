"use client";
// Content → Help → an article (F9): edit with a live preview, publish, history.
import Link from "next/link";
import { useParams } from "next/navigation";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { HelpEditor } from "@/components/content/HelpEditor";
import { useHelpArticle } from "@/lib/content";

export default function HelpArticlePage() {
  const { id } = useParams<{ id: string }>();
  const a = useHelpArticle(id);
  return (
    <ConsoleShell section="Help" country="ALL" hideScope>
      {a.isLoading ? (
        <div aria-busy="true" className="space-y-4">
          <div className="h-10 w-2/3 animate-pulse rounded-lg bg-white" />
          <div className="h-[420px] animate-pulse rounded-2xl bg-white" />
        </div>
      ) : a.data ? (
        <HelpEditor key={a.data.id} article={a.data} />
      ) : (
        <div role="alert" className="space-y-3 rounded-2xl bg-white p-6">
          <p className="m-0 font-bold">{(a.error as { response?: { status?: number } } | null)?.response?.status === 404 ? "This article doesn't exist, or it isn't in a country you can see." : "The article didn't load."}</p>
          <div className="flex gap-3">
            <button type="button" onClick={() => void a.refetch()} className="h-10 rounded-full border border-line px-4 font-bold text-peacock">Try again</button>
            <Link href="/content/help" className="inline-flex h-10 items-center rounded-full px-4 font-bold text-peacock">All help articles</Link>
          </div>
        </div>
      )}
    </ConsoleShell>
  );
}
