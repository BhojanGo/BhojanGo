// A Help topic (F9): its articles, search, and contact at the bottom.
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { HelpContact } from "@/components/help/HelpContact";
import { HelpSearch } from "@/components/help/HelpSearch";
import { ArticleList, Breadcrumbs, TopicIcon } from "@/components/help/parts";
import { HelpUnavailable, PageWidth } from "@/components/help/states";
import { helpTopic, isTopic } from "@/lib/help";
import { getContext } from "@/lib/prefs";

type Params = { params: Promise<{ topic: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { topic } = await params;
  const { t } = await getContext();
  if (!isTopic(topic)) return {};
  return { title: `${t(`helpcentre.topics.${topic}.title`)} · ${t("helpcentre.title")}`, description: t(`helpcentre.topics.${topic}.body`) };
}

export default async function HelpTopicPage({ params }: Params) {
  const { topic } = await params;
  if (!isTopic(topic)) notFound();
  const ctx = await getContext();
  const { t } = ctx;
  const page = await helpTopic(topic, { country: ctx.country?.code, language: ctx.language });
  const name = t(`helpcentre.topics.${topic}.title`);

  return (
    <div className="bg-porcelain pb-16">
      <div className="border-b border-line bg-white">
        <PageWidth className="space-y-5 py-6 md:py-8">
          <Breadcrumbs label={t("helpcentre.breadcrumb")} items={[{ href: "/help", text: t("helpcentre.title") }, { text: name }]} />
          <div className="flex flex-wrap items-center justify-between gap-x-10 gap-y-5">
            <div className="flex min-w-0 items-center gap-4">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-peacock-mist text-peacock">
                <TopicIcon topic={topic} size={28} />
              </span>
              <div className="min-w-0">
                <h1 className="text-h1 text-kohl">{name}</h1>
                <p className="mt-1 text-body text-muted">{t(`helpcentre.topics.${topic}.body`)}</p>
              </div>
            </div>
            <div className="w-full lg:w-[420px]">
              <HelpSearch />
            </div>
          </div>
        </PageWidth>
      </div>
      <PageWidth className="space-y-12 pt-8">
        {!page.ok ? <HelpUnavailable /> : page.data.articles.length ? (
          <section aria-label={name}>
            <ArticleList items={page.data.articles} />
          </section>
        ) : (
          <p className="rounded-card bg-white p-6 text-body text-muted">{t("helpcentre.topic_empty")}</p>
        )}
        <HelpContact topic={topic} />
      </PageWidth>
    </div>
  );
}
