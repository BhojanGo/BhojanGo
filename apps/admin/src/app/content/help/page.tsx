"use client";
// Content → Help (round 8, F9): every help article you may see, filtered by
// country, language, topic and status. Country managers write and publish
// their country's; the super admin the ones for every country; support and
// viewers read them (to point people at them).
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import {
  countryLabel, HELP_LANGUAGES, HELP_TOPICS, languageLabel, statusWords, topicLabel, useHelpArticles, type HelpArticle,
} from "@/lib/content";
import { useAdminMe, useMarkets } from "@/lib/markets";

const select = "mt-1 block h-10 w-full rounded-lg border border-line bg-white px-2 text-label font-normal";

export function StatusChip({ a }: { a: Pick<HelpArticle, "status" | "draft"> }) {
  const s = statusWords(a);
  const cls = s.tone === "live" ? "bg-peacock-tint text-peacock-dark" : s.tone === "changes" ? "bg-kesar-tint text-kesar-ink" : "bg-line-soft text-kohl";
  return <span className={`inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-full px-2.5 text-caption ${cls}`}>{s.text}</span>;
}

function Helpful({ a }: { a: HelpArticle }) {
  const n = a.helpful_yes + a.helpful_no;
  if (!n) return <span className="text-muted">No votes</span>;
  return <span className="tabular-nums">{Math.round((a.helpful_yes / n) * 100)}% helpful · {n} vote{n === 1 ? "" : "s"}</span>;
}

function HelpList() {
  const params = useSearchParams();
  const router = useRouter();
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();
  const names = Object.fromEntries((markets ?? []).map((c) => [c.code, c.name]));
  const f = {
    country: params.get("country") ?? "",
    language: params.get("language") ?? "",
    topic: params.get("topic") ?? "",
    status: params.get("status") ?? "",
  };
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const set = (k: keyof typeof f, v: string) => {
    const next = new URLSearchParams(params.toString());
    if (v) next.set(k, v);
    else next.delete(k);
    router.replace(`/content/help${next.toString() ? `?${next}` : ""}`, { scroll: false });
  };
  useEffect(() => {
    const h = setTimeout(() => setQuery(q.trim()), 300);
    return () => clearTimeout(h);
  }, [q]);
  const list = useHelpArticles({ ...f, q: query });
  const mayWrite = (me?.permissions["content.edit"] ?? []).length > 0;
  const filtered = Object.values(f).some(Boolean) || Boolean(query);

  return (
    <ConsoleShell section="Help" country="ALL" hideScope>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="m-0 text-caption text-muted">Content</p>
          <h1 className="m-0 text-h1">Help articles</h1>
          <p className="m-0 mt-1 max-w-2xl text-small text-muted">
            What the website&apos;s Help centre shows. Visitors get their country&apos;s article in their language, then their country&apos;s English one, then the one for every country.
          </p>
        </div>
        {mayWrite ? (
          <Link href="/content/help/new" className="inline-flex h-11 items-center rounded-full bg-peacock px-5 font-bold text-white">New article</Link>
        ) : null}
      </div>

      <section aria-label="Filters" className="grid gap-3 rounded-2xl bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-label lg:col-span-1">Search
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Title or slug"
            className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal" />
        </label>
        <label className="text-label">Country
          <select value={f.country} onChange={(e) => set("country", e.target.value)} className={select}>
            <option value="">All</option>
            <option value="*">Every country (global)</option>
            {(markets ?? []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </label>
        <label className="text-label">Language
          <select value={f.language} onChange={(e) => set("language", e.target.value)} className={select}>
            <option value="">All</option>
            {HELP_LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </label>
        <label className="text-label">Topic
          <select value={f.topic} onChange={(e) => set("topic", e.target.value)} className={select}>
            <option value="">All</option>
            {HELP_TOPICS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </label>
        <label className="text-label">Status
          <select value={f.status} onChange={(e) => set("status", e.target.value)} className={select}>
            <option value="">All</option>
            <option value="published">Published</option>
            <option value="changes">Changes not live yet</option>
            <option value="draft">Draft</option>
          </select>
        </label>
      </section>

      <section aria-label="Articles" className="overflow-hidden rounded-2xl bg-white">
        <div className="flex items-center justify-between border-b border-line px-4 py-3 text-label">
          <span>{list.data ? `${list.data.length} article${list.data.length === 1 ? "" : "s"}` : "Articles"}</span>
          {filtered ? <Link href="/content/help" onClick={() => setQ("")} className="font-semibold text-peacock">Clear filters</Link> : null}
        </div>
        {list.isLoading ? (
          <ul aria-busy="true" className="divide-y divide-line">{[0, 1, 2, 3, 4].map((i) => <li key={i} className="p-4"><div className="h-10 animate-pulse rounded-lg bg-porcelain" /></li>)}</ul>
        ) : list.isError ? (
          <div role="alert" className="space-y-2 p-6">
            <p className="m-0 font-bold">The articles didn&apos;t load.</p>
            <button type="button" onClick={() => void list.refetch()} className="h-10 rounded-full border border-line px-4 font-bold text-peacock">Try again</button>
          </div>
        ) : !list.data?.length ? (
          <div className="space-y-2 p-6">
            <p className="m-0 font-bold">{filtered ? "No articles match these filters." : "No help articles yet."}</p>
            <p className="m-0 text-small text-muted">{filtered ? "Clear a filter, or write a new one." : "Write the first one: the website shows it once you publish it."}</p>
          </div>
        ) : (
          <>
            {/* Wide screens (1280 px and up): a table, scrolling inside the card if it ever needs to */}
            <div className="table-scroll hidden xl:block">
              <table className="w-full text-left text-small [&_td]:px-3 [&_td]:align-top [&_th]:px-3 [&_th]:py-2.5">
                <thead className="text-caption text-muted">
                  <tr><th className="!pl-4">Article</th><th>Topic</th><th>Country</th><th>Language</th><th>Status</th><th>Helpful</th><th className="!pr-4">Updated</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {list.data.map((a) => (
                    <tr key={a.id} className="hover:bg-porcelain">
                      <td className="max-w-[360px] !pl-4 py-3">
                        <Link href={`/content/help/${a.id}`} className="font-bold text-kohl hover:text-peacock">{(a.draft ?? a.live).title}</Link>
                        <span className="block truncate text-muted">{a.slug}{a.live.popular ? ` · popular #${a.live.popular}` : ""}</span>
                      </td>
                      <td className="py-3">{topicLabel((a.draft ?? a.live).topic)}</td>
                      <td className="py-3">{countryLabel(a.country, names)}</td>
                      <td className="py-3">{languageLabel(a.language)}</td>
                      <td className="py-3"><StatusChip a={a} /></td>
                      <td className="whitespace-nowrap py-3"><Helpful a={a} /></td>
                      <td className="!pr-4 py-3 text-muted">
                        <span className="block whitespace-nowrap tabular-nums">{new Date(a.updated_at).toLocaleDateString()}</span>
                        {a.updated_by_name ? <span className="block">{a.updated_by_name}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Phones, tablets and laptops (under 1280 px, e.g. 1366 at 125 %): rows */}
            <ul className="divide-y divide-line xl:hidden">
              {list.data.map((a) => (
                <li key={a.id}>
                  <Link href={`/content/help/${a.id}`} className="block space-y-1 px-4 py-3 hover:bg-porcelain">
                    <span className="flex flex-col items-start gap-1 sm:flex-row sm:justify-between sm:gap-3">
                      <b className="text-label">{(a.draft ?? a.live).title}</b>
                      <StatusChip a={a} />
                    </span>
                    <span className="block text-small text-muted">
                      {topicLabel((a.draft ?? a.live).topic)} · {countryLabel(a.country, names)} · {languageLabel(a.language)}
                    </span>
                    <span className="block text-small text-muted tabular-nums">
                      Updated {new Date(a.updated_at).toLocaleDateString()}{a.updated_by_name ? ` by ${a.updated_by_name}` : ""} · <Helpful a={a} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
      {!mayWrite && me ? (
        <p className="m-0 text-small text-muted">
          You can read help articles. Country managers write and publish their country&apos;s; the super admin writes the ones for every country.
        </p>
      ) : null}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><HelpList /></Suspense>;
}
