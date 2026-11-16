"use client";
// Help search (F9): results as you type, from Postgres full-text search in
// core_api, in the visitor's country and language. Without JavaScript the form
// still works: it submits to /help?q=..., which the server answers.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { Close, Search } from "@/components/Icons";
import { urls } from "@/lib/client";
import { articleHref, type HelpCard } from "@/lib/help";
import { useLanguage, useT } from "@/lib/i18n";

type State = { q: string; status: "idle" | "loading" | "done" | "error"; results: HelpCard[] };

export function HelpSearch({ initial = "", suggestions = [], big = false }: { initial?: string; suggestions?: HelpCard[]; big?: boolean }) {
  const t = useT();
  const { language, country } = useLanguage();
  const [q, setQ] = useState(initial);
  const [s, setS] = useState<State>({ q: "", status: "idle", results: [] });
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      setS((x) => ({ ...x, q: query, status: "loading" }));
      const qs = new URLSearchParams({ q: query, language, limit: "8" });
      if (country?.code) qs.set("country", country.code);
      fetch(`${urls.core}/api/v1/help/search?${qs}`, { signal: ctrl.signal })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: { results: HelpCard[] }) => setS({ q: query, status: "done", results: d.results }))
        .catch((e: Error) => e.name !== "AbortError" && setS({ q: query, status: "error", results: [] }));
    }, 180);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [q, language, country?.code]);

  const query = q.trim();
  const show = query.length >= 2 && s.status !== "idle" && s.q === query;
  return (
    <div className="w-full">
      <form action="/help" method="get" role="search" onSubmit={(e) => {
        // Enter opens the top result once there is one; until then the list keeps updating.
        e.preventDefault();
        const top = s.q === q.trim() ? s.results[0] : undefined;
        if (top) router.push(articleHref(top));
      }} className="relative">
        <label htmlFor={id} className="sr-only">{t("helpcentre.search_label")}</label>
        <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
        <input
          ref={input}
          id={id}
          name="q"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t(big ? "helpcentre.search_placeholder" : "helpcentre.search_label")}
          autoComplete="off"
          aria-describedby={`${id}-status`}
          className={`block w-full rounded-pill border-[1.5px] border-line-strong bg-white pl-12 pr-12 text-body text-kohl shadow-float outline-none placeholder:text-muted focus:border-peacock focus:ring-2 focus:ring-peacock/25 [&::-webkit-search-cancel-button]:hidden ${big ? "h-14" : "h-12"}`}
        />
        {q ? (
          <button type="button" onClick={() => { setQ(""); input.current?.focus(); }} aria-label={t("helpcentre.search_clear")}
            className="absolute right-1.5 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full text-muted hover:bg-porcelain">
            <Close size={16} />
          </button>
        ) : null}
      </form>
      <p id={`${id}-status`} role="status" aria-live="polite" className="sr-only">
        {show && s.status === "done" ? t("helpcentre.results", { count: s.results.length }) : ""}
      </p>
      {show ? (
        <div className="mt-3 rounded-card border border-line bg-white p-2 text-left shadow-float" data-testid="help-results">
          {s.status === "loading" && s.results.length === 0 ? (
            <ul aria-hidden="true" className="space-y-2 p-2">
              {[0, 1, 2].map((i) => <li key={i} className="h-10 animate-pulse rounded-lg bg-porcelain" />)}
            </ul>
          ) : s.status === "error" ? (
            <p className="p-3 text-small text-muted">{t("helpcentre.search_error")} <a href="#contact" className="font-semibold text-peacock">{t("helpcentre.contact_us")}</a></p>
          ) : s.results.length ? (
            <ul>
              {s.results.map((a) => (
                <li key={a.slug}>
                  <Link href={articleHref(a)} className="block rounded-xl px-3 py-2.5 hover:bg-porcelain focus-visible:bg-porcelain">
                    <span className="block text-label font-semibold text-kohl">{a.title}</span>
                    <span className="mt-0.5 line-clamp-2 block text-small text-muted">{a.summary}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="space-y-3 p-3">
              <p className="text-label font-semibold text-kohl">{t("helpcentre.no_results_title", { query: s.q })}</p>
              <p className="text-small text-muted">{t("helpcentre.no_results_body")}</p>
              {suggestions.length ? (
                <ul className="flex flex-wrap gap-2">
                  {suggestions.slice(0, 4).map((a) => (
                    <li key={a.slug}>
                      <Link href={articleHref(a)} className="inline-flex min-h-[40px] items-center rounded-pill border border-line px-3.5 text-small font-semibold text-peacock hover:bg-peacock-mist">{a.title}</Link>
                    </li>
                  ))}
                </ul>
              ) : null}
              <a href="#contact" className="inline-flex text-small font-bold text-peacock">{t("helpcentre.contact_us")}</a>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
