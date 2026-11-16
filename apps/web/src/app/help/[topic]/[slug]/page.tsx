// A Help article (F9): breadcrumbs, the article, "Was this helpful?", related
// articles, the rest of its topic, and contact at the bottom.
import { LANGUAGES } from "@bhojango/i18n";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";

import { HelpContact } from "@/components/help/HelpContact";
import { Helpful } from "@/components/help/Helpful";
import { ArticleBody, ArticleList, Breadcrumbs } from "@/components/help/parts";
import { HelpUnavailable, PageWidth } from "@/components/help/states";
import { date } from "@/lib/format";
import { articleHref, helpArticle, helpTopic, isTopic, type HelpTopic } from "@/lib/help";
import { getContext } from "@/lib/prefs";

type Params = { params: Promise<{ topic: string; slug: string }> };

async function load(slug: string) {
  const ctx = await getContext();
  return { ctx, res: await helpArticle(slug, { country: ctx.country?.code, language: ctx.language }) };
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const { ctx, res } = await load(slug);
  if (!res.ok) return { title: ctx.t("helpcentre.title") };
  return { title: res.data.title, description: res.data.summary };
}

export default async function HelpArticlePage({ params }: Params) {
  const { topic, slug } = await params;
  const { ctx, res } = await load(slug);
  const { t } = ctx;
  if (!res.ok && res.missing) notFound();
  if (res.ok && res.data.topic !== topic) permanentRedirect(articleHref(res.data));
  if (!res.ok || !isTopic(topic)) {
    return (
      <div className="bg-porcelain pb-16">
        <PageWidth className="space-y-10 pt-10">
          <HelpUnavailable />
          <HelpContact />
        </PageWidth>
      </div>
    );
  }
  const a = res.data;
  const others = await helpTopic(topic, { country: ctx.country?.code, language: ctx.language });
  const inTopic = others.ok ? others.data.articles.filter((x) => x.slug !== a.slug) : [];
  const topicName = t(`helpcentre.topics.${topic as HelpTopic}.title`);
  const language = LANGUAGES[ctx.language as keyof typeof LANGUAGES]?.name ?? ctx.language;

  return (
    <div className="bg-porcelain pb-16">
      <PageWidth className="pt-6 md:pt-8">
        <Breadcrumbs label={t("helpcentre.breadcrumb")}
          items={[{ href: "/help", text: t("helpcentre.title") }, { href: `/help/${topic}`, text: topicName }, { text: a.title }]} />
        <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-12">
          <div className="min-w-0 space-y-6">
            <article className="rounded-card bg-white p-5 sm:p-8 lg:p-10" data-testid="help-article">
              <header className="space-y-3 border-b border-line pb-5">
                <h1 className="text-h1 text-kohl">{a.title}</h1>
                {a.summary ? <p className="text-body-lg text-muted">{a.summary}</p> : null}
                <p className="text-small text-muted">{t("helpcentre.updated", { date: date(a.updated_at, ctx.formatLocale, ctx.country?.timezone, { year: "numeric" }) })}</p>
              </header>
              {a.fallback ? (
                <p className="mt-5 rounded-xl bg-porcelain px-4 py-3 text-small text-muted">{t("helpcentre.fallback_note", { language })}</p>
              ) : null}
              <div className="mt-6 max-w-[68ch]">
                <ArticleBody markdown={a.body} />
              </div>
            </article>
            <Helpful articleId={a.id} />
            {a.related.length ? (
              <section aria-labelledby="related" className="space-y-4">
                <h2 id="related" className="text-h3 text-kohl">{t("helpcentre.related_title")}</h2>
                <ArticleList items={a.related} />
              </section>
            ) : null}
          </div>
          <aside aria-labelledby="in-topic" className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            <h2 id="in-topic" className="text-h3 text-kohl">{t("helpcentre.in_topic", { topic: topicName })}</h2>
            {inTopic.length ? <ArticleList items={inTopic} dense /> : null}
            <Link href={`/help/${topic}`} className="inline-flex min-h-[44px] items-center text-label font-bold text-peacock">{t("helpcentre.all_in_topic")}</Link>
          </aside>
        </div>
        <div className="mt-12">
          <HelpContact topic={topic} />
        </div>
      </PageWidth>
    </div>
  );
}
