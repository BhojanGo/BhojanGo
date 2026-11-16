// /help/a/<slug>: a short link to an article (what the articles use to link to
// each other); it goes to the article under its topic, /help/<topic>/<slug>.
import { notFound, redirect } from "next/navigation";

import { HelpUnavailable, PageWidth } from "@/components/help/states";
import { articleHref, helpArticle } from "@/lib/help";
import { getContext } from "@/lib/prefs";

export default async function ShortArticleLink({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const ctx = await getContext();
  const res = await helpArticle(slug, { country: ctx.country?.code, language: ctx.language });
  if (res.ok) redirect(articleHref(res.data));
  if (res.missing) notFound();
  return (
    <PageWidth className="py-10">
      <HelpUnavailable />
    </PageWidth>
  );
}
