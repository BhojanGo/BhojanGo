// The Help centre (round 8, F9): search at the top (results as you type),
// topics, popular articles, and "Still need help?" at the bottom. Articles are
// managed in the admin console (Content → Help), per country and language.
import type { Metadata } from "next";
import Link from "next/link";

import { HelpContact } from "@/components/help/HelpContact";
import { HelpSearch } from "@/components/help/HelpSearch";
import { ArticleGrid, ArticleList, TopicIcon } from "@/components/help/parts";
import { HelpUnavailable, PageWidth } from "@/components/help/states";
import { helpHome, helpSearch, TOPICS } from "@/lib/help";
import { getContext } from "@/lib/prefs";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("helpcentre.title"), description: t("helpcentre.meta_description") };
}

export default async function Help({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const ctx = await getContext();
  const { t } = ctx;
  const where = { country: ctx.country?.code, language: ctx.language };
  const q = ((await searchParams).q ?? "").trim().slice(0, 200);
  const [home, found] = await Promise.all([helpHome(where), q ? helpSearch(q, where) : Promise.resolve(null)]);
  const popular = home.ok ? home.data.popular : [];
  const counts = new Map(home.ok ? home.data.topics.map((x) => [x.topic, x.count]) : []);

  return (
    <div className="bg-porcelain pb-16">
      <div className="bg-peacock-deep text-white">
        <PageWidth className="py-10 md:py-14">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-caption text-peacock-tint">{t("helpcentre.title")}</p>
            <h1 className="mt-2 text-display">{t("helpcentre.hero_title")}</h1>
            <p className="mx-auto mt-3 max-w-xl text-body-lg text-peacock-tint">{t("helpcentre.hero_body")}</p>
            <div className="mt-6 text-left md:mt-8">
              <HelpSearch initial={q} suggestions={popular} big />
            </div>
          </div>
        </PageWidth>
      </div>

      <PageWidth className="space-y-12 pt-10 md:pt-12">
        {q && found ? (
          <section aria-labelledby="results" className="space-y-4">
            <h2 id="results" className="text-h2 text-kohl">{t("helpcentre.results_for", { query: q })}</h2>
            {found.ok && found.data.results.length ? <ArticleList items={found.data.results} /> : (
              <p className="text-body text-muted">{t("helpcentre.no_results_body")}</p>
            )}
          </section>
        ) : null}

        {!home.ok ? <HelpUnavailable /> : (
          <>
            <section aria-labelledby="topics" className="space-y-5">
              <h2 id="topics" className="text-h2 text-kohl">{t("helpcentre.topics_title")}</h2>
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {TOPICS.map((topic) => (
                  <li key={topic}>
                    <Link href={`/help/${topic}`} data-testid={`topic-${topic}`}
                      className="group flex h-full items-center gap-4 rounded-card border border-line bg-white p-4 sm:items-start sm:p-5 transition-shadow hover:border-peacock hover:shadow-float focus-visible:border-peacock">
                      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-peacock-mist text-peacock">
                        <TopicIcon topic={topic} />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-body-lg font-bold text-kohl group-hover:text-peacock-deep">{t(`helpcentre.topics.${topic}.title`)}</span>
                        <span className="mt-1 hidden text-small text-muted sm:block">{t(`helpcentre.topics.${topic}.body`)}</span>
                        <span className="mt-0.5 block text-small font-semibold text-peacock sm:mt-2">{t("helpcentre.topic_count", { count: counts.get(topic) ?? 0 })}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            {popular.length ? (
              <section aria-labelledby="popular" className="space-y-5">
                <h2 id="popular" className="text-h2 text-kohl">{t("helpcentre.popular_title")}</h2>
                <ArticleGrid items={popular} />
              </section>
            ) : null}
          </>
        )}

        <HelpContact />
      </PageWidth>
    </div>
  );
}
