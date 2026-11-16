"use client";
/**
 * The help article editor (round 8, F9): Markdown with a live preview (the
 * website's renderer), save as draft, publish, unpublish, and the history of
 * every version with who made it. A published article keeps showing its live
 * text on the website until you publish your saved changes.
 */
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { MarkdownPreview } from "@/components/content/MarkdownPreview";
import { adminApi } from "@/lib/api";
import {
  countryLabel, HELP_LANGUAGES, HELP_TOPICS, languageLabel, statusWords, useHelpHistory,
  type HelpArticle, type HelpContent, type HelpHistoryEntry,
} from "@/lib/content";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { apiMessage } from "@/lib/ops";

const input = "mt-1 block w-full rounded-lg border border-line bg-white px-3 font-normal text-kohl outline-none focus:border-peacock focus:ring-2 focus:ring-peacock/20 disabled:bg-porcelain";

type Form = HelpContent & { slug: string; country: string; language: string; relatedText: string };

const fromContent = (c: HelpContent, a?: { slug: string; country: string; language: string }): Form => ({
  ...c, slug: a?.slug ?? "", country: a?.country ?? "", language: a?.language ?? "en", relatedText: c.related.join(", "),
});

const toContent = (f: Form): HelpContent => ({
  title: f.title.trim(), summary: f.summary.trim(), body: f.body, topic: f.topic, popular: Number(f.popular) || 0,
  related: f.relatedText.split(",").map((s) => s.trim()).filter(Boolean),
});

const same = (a: HelpContent, b: HelpContent) => JSON.stringify(a) === JSON.stringify(b);

const TOOLS: { label: string; title: string; wrap: [string, string]; line?: boolean }[] = [
  { label: "H2", title: "Heading", wrap: ["## ", ""], line: true },
  { label: "B", title: "Bold", wrap: ["**", "**"] },
  { label: "I", title: "Italic", wrap: ["*", "*"] },
  { label: "• List", title: "Bulleted list", wrap: ["- ", ""], line: true },
  { label: "1. List", title: "Numbered list", wrap: ["1. ", ""], line: true },
  { label: "Link", title: "Link (to a page on the website: /help/a/<slug>)", wrap: ["[", "](/help/a/)"] },
  { label: "Note", title: "A highlighted note", wrap: ["> ", ""], line: true },
];

export function HelpEditor({ article, prefill }: { article: HelpArticle | null; prefill?: Partial<Form> }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();
  const names = Object.fromEntries((markets ?? []).map((c) => [c.code, c.name]));
  const isNew = !article;
  const working = article ? (article.draft ?? article.live) : null;
  const [f, setF] = useState<Form>(() =>
    working ? fromContent(working, article!) : {
      title: "", summary: "", body: "", topic: "orders", popular: 0, related: [], slug: "", country: "", language: "en", relatedText: "", ...prefill,
    });
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [panel, setPanel] = useState<"edit" | "history">("edit");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const body = useRef<HTMLTextAreaElement>(null);

  const editable = isNew ? (me?.permissions["content.edit"] ?? []).length > 0 : article.can_edit;
  const dirty = working ? !same(toContent(f), working) : Boolean(f.title || f.body);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF((x) => ({ ...x, [k]: e.target.value }));

  function tool(t: (typeof TOOLS)[number]) {
    const el = body.current;
    if (!el) return;
    const { selectionStart: a, selectionEnd: b, value } = el;
    const start = t.line ? value.lastIndexOf("\n", a - 1) + 1 : a;
    const chosen = value.slice(start, b);
    const next = value.slice(0, start) + t.wrap[0] + chosen + t.wrap[1] + value.slice(b);
    setF((x) => ({ ...x, body: next }));
    requestAnimationFrame(() => {
      el.focus();
      const cursor = start + t.wrap[0].length + chosen.length;
      el.setSelectionRange(cursor, cursor);
    });
  }

  async function run(label: string, fn: () => Promise<HelpArticle | null>, ok: string) {
    setBusy(label);
    setMsg(null);
    try {
      const a = await fn();
      await qc.invalidateQueries({ queryKey: ["help"] });
      if (a) {
        qc.setQueryData(["help", "article", a.id], a);
        setF(fromContent(a.draft ?? a.live, a));
      }
      setMsg({ ok: true, text: ok });
      return a;
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function save(): Promise<HelpArticle | null> {
    if (isNew) {
      const { data } = await adminApi.post<HelpArticle>("/user/ops/help/articles", {
        ...toContent(f), slug: f.slug.trim(), country: f.country, language: f.language,
      });
      return data;
    }
    if (!dirty) return article;
    return (await adminApi.patch<HelpArticle>(`/user/ops/help/articles/${article.id}`, toContent(f))).data;
  }

  async function onSave() {
    const a = await run("save", save, isNew ? "Saved as a draft. It isn't on the website until you publish it."
      : article.status === "published" ? "Saved. The website still shows the live version until you publish." : "Saved as a draft.");
    if (a && isNew) router.replace(`/content/help/${a.id}`);
  }

  async function onPublish() {
    const a = await run("publish", async () => {
      const saved = await save();
      if (!saved) return null;
      return (await adminApi.post<HelpArticle>(`/user/ops/help/articles/${saved.id}/publish`)).data;
    }, "Published. The website shows it within a minute.");
    if (a && isNew) router.replace(`/content/help/${a.id}`);
  }

  async function onUnpublish() {
    if (!article || !window.confirm("Take this article off the website? It stays here as a draft.")) return;
    await run("unpublish", async () => (await adminApi.post<HelpArticle>(`/user/ops/help/articles/${article.id}/unpublish`)).data,
      "Unpublished. It's a draft now and no longer on the website.");
  }

  const s = article ? statusWords(article) : { text: "New draft", tone: "draft" as const };
  const countries = (markets ?? []).filter((c) => can(me, "content.edit", c.code));
  const canGlobal = can(me, "content.edit", "*");
  const ready = f.title.trim().length >= 3 && (!isNew || (/^[a-z0-9]+(-[a-z0-9]+)*$/.test(f.slug) && f.country && f.language));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link href="/content/help" className="text-small font-semibold text-peacock">← Help articles</Link>
          <h1 className="m-0 mt-1 text-h1">{isNew ? "New help article" : (working?.title ?? "")}</h1>
          {article ? (
            <p className="m-0 mt-1 text-small text-muted">
              {article.slug} · {countryLabel(article.country, names)} · {languageLabel(article.language)} · version {article.version}
              {article.updated_by_name ? ` · last changed by ${article.updated_by_name}` : ""} · {new Date(article.updated_at).toLocaleString()}
            </p>
          ) : null}
        </div>
        <span className={`inline-flex h-7 items-center rounded-full px-3 text-caption ${s.tone === "live" ? "bg-peacock-tint text-peacock-dark" : s.tone === "changes" ? "bg-kesar-tint text-kesar-ink" : "bg-line-soft text-kohl"}`}>{s.text}</span>
      </div>

      {article ? (
        <div role="tablist" aria-label="Article" className="flex gap-1 border-b border-line">
          {(["edit", "history"] as const).map((p) => (
            <button key={p} type="button" role="tab" aria-selected={panel === p} onClick={() => setPanel(p)}
              className={`h-11 border-b-[3px] px-4 text-label ${panel === p ? "border-peacock font-bold text-peacock-dark" : "border-transparent font-semibold text-muted"}`}>
              {p === "edit" ? (article.can_edit ? "Edit" : "Read") : "History"}
            </button>
          ))}
        </div>
      ) : null}

      {panel === "history" && article ? (
        <History id={article.id} onCopy={editable ? (c) => { setF((x) => ({ ...fromContent(c, x), slug: x.slug, country: x.country, language: x.language })); setPanel("edit"); setMsg({ ok: true, text: "Copied that version into the editor. Save or publish to use it." }); } : undefined} />
      ) : (
        <>
          {article && article.status === "published" && article.draft ? (
            <p className="m-0 rounded-xl bg-kesar-tint px-4 py-3 text-small text-kesar-ink">You have saved changes that aren&apos;t on the website yet. Publish to make them live.</p>
          ) : null}
          {!editable ? (
            <p className="m-0 rounded-xl bg-porcelain px-4 py-3 text-small text-muted">
              You can read this article. {article?.country === "*" ? "Articles for every country are edited by the super admin." : "Its country manager edits and publishes it."}
            </p>
          ) : null}

          <section aria-label="Details" className="grid gap-4 rounded-2xl bg-white p-5 md:grid-cols-2 xl:grid-cols-4">
            {isNew ? (
              <>
                <Field id="help-slug" label="Slug (the address)" hint={`/help/${f.topic}/${f.slug || "…"}. The same slug in another language or country is a translation.`}>
                  <input id="help-slug" aria-describedby="help-slug-hint" value={f.slug}
                    onChange={(e) => setF((x) => ({ ...x, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") }))}
                    placeholder="e.g. cancel-an-order" className={`${input} h-10`} />
                </Field>
                <Field id="help-country" label="Country">
                  <select id="help-country" value={f.country} onChange={set("country")} className={`${input} h-10`}>
                    <option value="">Choose…</option>
                    {canGlobal ? <option value="*">Every country (global)</option> : null}
                    {countries.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
                  </select>
                </Field>
                <Field id="help-language" label="Language">
                  <select id="help-language" value={f.language} onChange={set("language")} className={`${input} h-10`}>
                    <option value="">Choose…</option>
                    {HELP_LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                  </select>
                </Field>
              </>
            ) : null}
            <Field id="help-topic" label="Topic">
              <select id="help-topic" value={f.topic} onChange={set("topic")} disabled={!editable} className={`${input} h-10`}>
                {HELP_TOPICS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </Field>
            <Field id="help-title" label="Title" className="md:col-span-2">
              <input id="help-title" value={f.title} onChange={set("title")} maxLength={160} disabled={!editable} className={`${input} h-10`} />
            </Field>
            <Field id="help-popular" label="Popular" hint="0: not on the Help home page; 1, 2…: its place in Popular articles.">
              <input id="help-popular" aria-describedby="help-popular-hint" type="number" min={0} max={99} value={f.popular}
                onChange={set("popular")} disabled={!editable} className={`${input} h-10`} />
            </Field>
            <Field id="help-summary" label="Summary" hint="One sentence, shown in lists and search results." className="md:col-span-2 xl:col-span-3">
              <input id="help-summary" aria-describedby="help-summary-hint" value={f.summary} onChange={set("summary")} maxLength={300}
                disabled={!editable} className={`${input} h-10`} />
            </Field>
            <Field id="help-related" label="Related articles">
              <input id="help-related" value={f.relatedText} onChange={set("relatedText")} disabled={!editable} placeholder="slug-one, slug-two" className={`${input} h-10`} />
            </Field>
          </section>

          <section aria-label="Article text" className="grid gap-4 xl:grid-cols-2">
            <div className="flex gap-1 xl:hidden" role="tablist" aria-label="Write or preview">
              {(["write", "preview"] as const).map((t) => (
                <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                  className={`h-10 rounded-full px-4 text-label ${tab === t ? "bg-kohl font-bold text-white" : "border border-line bg-white font-semibold"}`}>
                  {t === "write" ? "Write" : "Preview"}
                </button>
              ))}
            </div>
            <div className={`${tab === "write" ? "block" : "hidden"} rounded-2xl bg-white p-4 xl:block`}>
              {editable ? (
                <div className="mb-2 flex flex-wrap gap-1" aria-label="Formatting">
                  {TOOLS.map((t) => (
                    <button key={t.label} type="button" title={t.title} aria-label={t.title} onClick={() => tool(t)}
                      className="h-9 min-w-[40px] rounded-lg border border-line px-2.5 text-small font-bold hover:bg-porcelain">{t.label}</button>
                  ))}
                </div>
              ) : null}
              <label className="sr-only" htmlFor="help-body">Article text (Markdown)</label>
              <textarea id="help-body" ref={body} value={f.body} onChange={set("body")} readOnly={!editable} rows={24}
                className={`${input} min-h-[420px] py-3 font-mono leading-relaxed`} data-testid="help-body" />
              <p className="m-0 mt-2 text-small text-muted">
                ## heading · **bold** · *italic* · - list · 1. list · [text](/help/a/slug) · &gt; note. Plain text only: no HTML.
              </p>
            </div>
            <div className={`${tab === "preview" ? "block" : "hidden"} rounded-2xl bg-white p-6 xl:block`}>
              <p className="m-0 mb-4 text-caption text-muted">Preview · as on the website</p>
              <MarkdownPreview title={f.title} summary={f.summary} body={f.body} />
            </div>
          </section>

          {editable ? (
            <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-white/95 px-4 py-3 shadow-float backdrop-blur">
              <button type="button" onClick={onPublish} disabled={!!busy || !ready || (!dirty && article?.status === "published" && !article.draft)}
                className="h-11 rounded-full bg-peacock px-5 font-bold text-white disabled:opacity-40" data-testid="help-publish">
                {busy === "publish" ? "Publishing…" : article?.status === "published" ? "Publish changes" : "Publish"}
              </button>
              <button type="button" onClick={onSave} disabled={!!busy || !ready || (!isNew && !dirty)}
                className="h-11 rounded-full border border-line-strong bg-white px-5 font-bold text-kohl disabled:opacity-40" data-testid="help-save">
                {busy === "save" ? "Saving…" : "Save draft"}
              </button>
              {article?.status === "published" ? (
                <button type="button" onClick={onUnpublish} disabled={!!busy} className="h-11 rounded-full px-4 font-bold text-chili hover:bg-danger-tint">
                  {busy === "unpublish" ? "Unpublishing…" : "Unpublish"}
                </button>
              ) : null}
              {article ? (
                <Link href={`/content/help/new?from=${article.id}`} className="ml-auto text-label font-semibold text-peacock">Add a translation or country version</Link>
              ) : null}
              {dirty && !busy ? <span className="text-small text-muted">Unsaved changes</span> : null}
              {msg ? <p role="status" className={`m-0 w-full text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

/** A label above its control (the label names the control alone; the hint is its description). */
function Field({ id, label, hint, className = "", children }: { id: string; label: string; hint?: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="text-label">{label}</label>
      {children}
      {hint ? <p id={`${id}-hint`} className="m-0 mt-1 text-small text-muted">{hint}</p> : null}
    </div>
  );
}

const ACTION_WORDS: Record<HelpHistoryEntry["action"], string> = {
  created: "Created", edited: "Saved", published: "Published", unpublished: "Unpublished",
};

function History({ id, onCopy }: { id: string; onCopy?: (c: HelpContent) => void }) {
  const h = useHelpHistory(id);
  const [open, setOpen] = useState<number | null>(null);
  if (h.isLoading) return <div aria-busy="true" className="h-40 animate-pulse rounded-2xl bg-white" />;
  if (h.isError) return <p role="alert" className="m-0 rounded-2xl bg-white p-6">The history didn&apos;t load. <button type="button" onClick={() => void h.refetch()} className="font-bold text-peacock">Try again</button></p>;
  const rows = h.data ?? [];
  const shown = rows.find((r, i) => i === open);
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,420px)_1fr]">
      <ol className="m-0 list-none divide-y divide-line overflow-hidden rounded-2xl bg-white p-0" aria-label="Versions">
        {rows.map((r, i) => (
          <li key={`${r.version}-${i}`}>
            <button type="button" onClick={() => setOpen(i)} aria-current={open === i ? "true" : undefined}
              className={`block w-full px-4 py-3 text-left text-small ${open === i ? "bg-peacock-wash" : "hover:bg-porcelain"}`}>
              <span className="flex justify-between gap-2"><b>{ACTION_WORDS[r.action] ?? r.action} · v{r.version}</b><span className="text-muted">{new Date(r.at).toLocaleString()}</span></span>
              <span className="block text-muted">{r.by_name ?? "Unknown"} · {r.content.title}</span>
            </button>
          </li>
        ))}
        {!rows.length ? <li className="p-4 text-small text-muted">No history yet.</li> : null}
      </ol>
      <div className="rounded-2xl bg-white p-6">
        {shown ? (
          <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <p className="m-0 text-caption text-muted">Version {shown.version} · {ACTION_WORDS[shown.action]} by {shown.by_name ?? "Unknown"}</p>
              {onCopy ? <button type="button" onClick={() => onCopy(shown.content)} className="h-9 rounded-full border border-line px-3 text-label font-bold text-peacock">Copy into the editor</button> : null}
            </div>
            <MarkdownPreview title={shown.content.title} summary={shown.content.summary} body={shown.content.body} />
          </>
        ) : <p className="m-0 text-muted">Pick a version to see what the article said then.</p>}
      </div>
    </div>
  );
}
