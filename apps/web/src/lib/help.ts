// The Help centre's data (round 8, F9): articles are written and published in
// the admin console (Content → Help), per country and language; core_api picks
// the visitor's version (their country in their language, then English, then
// the articles for every country). Nothing here is typed into a page.

import type { CoreSchemas } from "@bhojango/api-client";

export type HelpHome = CoreSchemas["HelpHome"];
export type HelpTopicPage = CoreSchemas["TopicPage"];
export type HelpArticle = CoreSchemas["Article"];
export type HelpCard = CoreSchemas["ArticleCard"];

/** The topics, in the order the Help centre shows them (their names are in the messages: helpcentre.topics.*). */
export const TOPICS = ["orders", "payments-refunds", "delivery", "account", "kitchen-partners", "delivery-partners"] as const;
export type HelpTopic = (typeof TOPICS)[number];
export const isTopic = (t: string): t is HelpTopic => (TOPICS as readonly string[]).includes(t);

export const articleHref = (a: { topic: string; slug: string }) => `/help/${a.topic}/${a.slug}`;

const CORE = process.env.CORE_API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001";

export type Loaded<T> = { ok: true; data: T } | { ok: false; missing: boolean };

/** A Help read on the server: the data, "missing" (404), or an error (the page says so and offers contact). */
async function load<T>(path: string, where: { country?: string | null; language: string }, extra: Record<string, string> = {}): Promise<Loaded<T>> {
  const qs = new URLSearchParams({ language: where.language, ...extra });
  if (where.country) qs.set("country", where.country);
  try {
    // A minute's cache: an article published in the console shows within a minute.
    const r = await fetch(`${CORE}/api/v1/help${path}?${qs}`, { next: { revalidate: 60 } });
    if (r.status === 404) return { ok: false, missing: true };
    if (!r.ok) return { ok: false, missing: false };
    return { ok: true, data: (await r.json()) as T };
  } catch {
    return { ok: false, missing: false };
  }
}

type Where = { country?: string | null; language: string };

export const helpHome = (w: Where) => load<HelpHome>("", w);
export const helpTopic = (topic: string, w: Where) => load<HelpTopicPage>(`/topics/${encodeURIComponent(topic)}`, w);
export const helpArticle = (slug: string, w: Where) => load<HelpArticle>(`/articles/${encodeURIComponent(slug)}`, w);
export const helpSearch = (q: string, w: Where) => load<CoreSchemas["SearchResults"]>("/search", w, { q });
