"use client";

/**
 * "Documents kitchens need": what the website's "Add your kitchen" page (/partner)
 * tells a kitchen in this country to have ready, each with a one-line reason. Saved
 * as the country's kitchen_documents setting (the API checks it: a key, English text,
 * at most 12). Titles and reasons are per language: English is required, the
 * country's other languages are optional (the website falls back to English).
 * An empty list makes the website say "We'll tell you what's needed for your city".
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiError, can, type CountrySummary, LOCALE_NAMES, marketsApi, useAdminMe } from "@/lib/markets";

type Texts = Record<string, string>;
interface Doc {
  key: string;
  title: Texts;
  why: Texts;
}

function saved(country: CountrySummary): Doc[] {
  const raw = (country.settings as Record<string, unknown>).kitchen_documents;
  return Array.isArray(raw) ? (raw as Doc[]).map((d) => ({ key: d.key, title: { ...d.title }, why: { ...d.why } })) : [];
}

const keyOf = (title: string) => title.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 30);

export function KitchenDocuments({ country }: { country: CountrySummary }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const languages = [...new Set(["en", ...country.locales.map((l) => l.split("-")[0])])];
  const [docs, setDocs] = useState<Doc[]>(() => saved(country));
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const editable = can(me, "markets.edit", country.code);
  const field = "mt-1 block w-full rounded-lg border border-line px-3 py-2 text-small text-kohl disabled:bg-[#FAFBFB]";

  const edit = (i: number, part: "title" | "why", value: string) => {
    setDone(false);
    setDocs(docs.map((d, j) => {
      if (j !== i) return d;
      const next = { ...d, [part]: { ...d[part], [lang]: value } };
      // A new document's key follows its English title until it is saved.
      if (part === "title" && lang === "en" && !saved(country).some((s) => s.key === d.key)) next.key = keyOf(value) || d.key;
      return next;
    }));
  };
  const move = (i: number, by: number) => {
    const next = [...docs];
    const [d] = next.splice(i, 1);
    next.splice(i + by, 0, d!);
    setDocs(next);
    setDone(false);
  };

  async function save() {
    setBusy(true);
    setProblem(null);
    setDone(false);
    try {
      // Drop empty translations; English stays (the API requires it).
      const clean = docs.map((d) => ({
        key: d.key,
        title: Object.fromEntries(Object.entries(d.title).filter(([, v]) => v.trim()).map(([k, v]) => [k, v.trim()])),
        why: Object.fromEntries(Object.entries(d.why).filter(([, v]) => v.trim()).map(([k, v]) => [k, v.trim()])),
      }));
      await marketsApi.updateCountry(country.code, { settings: { kitchen_documents: clean.length ? clean : null } });
      await qc.invalidateQueries({ queryKey: ["markets"] });
      setDone(true);
    } catch (e) {
      setProblem(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Documents restaurants need" className="rounded-2xl border border-line bg-white p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 flex-1 text-h3">Documents restaurants need</h2>
        {languages.length > 1 && (
          <label className="text-small text-muted">
            Language{" "}
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="ml-1 rounded-lg border border-line px-2 py-1 text-small text-kohl">
              {languages.map((l) => (
                <option key={l} value={l}>{LOCALE_NAMES[`${l}-${country.code}`] ?? l}{l === "en" ? " (required)" : ""}</option>
              ))}
            </select>
          </label>
        )}
        {editable && (
          <button type="button" disabled={busy} onClick={() => void save()} className="h-10 rounded-full bg-peacock px-5 text-label text-white disabled:opacity-50">
            Save documents
          </button>
        )}
      </div>
      <p className="mt-1 text-small text-muted">
        Shown on the website&apos;s &ldquo;Add your restaurant&rdquo; page for {country.name}: what to have ready and why, one line each.
        With none, the page says &ldquo;We&apos;ll tell you what&apos;s needed for your city&rdquo;. Other languages fall back to English.
      </p>
      {docs.length === 0 && <p className="mt-3 text-small text-muted">No documents listed yet.</p>}
      <ol className="m-0 mt-4 list-none space-y-3 p-0">
        {docs.map((d, i) => (
          <li key={i} className="grid gap-3 rounded-xl border border-line-soft p-4 md:grid-cols-[1fr_2fr_auto] md:items-end">
            <label className="text-small text-muted">
              Document <span className="font-mono text-caption">{d.key || "new"}</span>
              <input value={d.title[lang] ?? ""} placeholder={lang === "en" ? "e.g. Food licence" : d.title.en} disabled={!editable}
                onChange={(e) => edit(i, "title", e.target.value)} maxLength={80} className={field} />
            </label>
            <label className="text-small text-muted">
              Why we need it
              <input value={d.why[lang] ?? ""} placeholder={lang === "en" ? "One line, e.g. Customers see it on your page." : d.why.en} disabled={!editable}
                onChange={(e) => edit(i, "why", e.target.value)} maxLength={240} className={field} />
            </label>
            {editable && (
              <div className="flex gap-1">
                <button type="button" aria-label={`Move ${d.title.en || "document"} up`} disabled={i === 0} onClick={() => move(i, -1)}
                  className="h-10 w-10 rounded-full border border-line text-muted disabled:opacity-40">↑</button>
                <button type="button" aria-label={`Move ${d.title.en || "document"} down`} disabled={i === docs.length - 1} onClick={() => move(i, 1)}
                  className="h-10 w-10 rounded-full border border-line text-muted disabled:opacity-40">↓</button>
                <button type="button" onClick={() => { setDocs(docs.filter((_, j) => j !== i)); setDone(false); }}
                  className="h-10 rounded-full px-3 text-label text-danger-ink">Remove</button>
              </div>
            )}
          </li>
        ))}
      </ol>
      {editable && docs.length < 12 && (
        <button type="button" onClick={() => { setLang("en"); setDocs([...docs, { key: `doc_${docs.length + 1}`, title: {}, why: {} }]); setDone(false); }}
          className="mt-3 h-10 rounded-full border border-line px-4 text-label text-peacock">
          Add a document
        </button>
      )}
      {done && <p role="status" className="mt-3 text-label text-peacock-dark">Saved. The website picks it up within five minutes.</p>}
      {problem && <p role="alert" className="mt-3 rounded-xl bg-danger-tint p-3 text-small text-danger-ink">{problem}</p>}
    </section>
  );
}
