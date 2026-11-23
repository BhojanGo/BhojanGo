"use client";
// Content → Legal (R8 F10): the Terms of use and Privacy notice of each country
// (and later the kitchen and delivery partner terms), per language. Every admin
// reads; super admins and country managers (for their country) write drafts and
// publish. Publishing makes the draft the next version, replaces the one before it
// (kept in the history) and signed-in people see "We've updated our policies" once.
// Every change is in the audit log, shown with the document.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { LegalMarkdownPreview as MarkdownPreview } from "@/components/content/LegalMarkdownPreview";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { apiMessage, useScope } from "@/lib/ops";

type Kind = "terms" | "privacy" | "kitchen_partner_terms" | "delivery_partner_terms";
const KINDS: { value: Kind; label: string }[] = [
  { value: "terms", label: "Terms of use" },
  { value: "privacy", label: "Privacy notice" },
  { value: "kitchen_partner_terms", label: "Restaurant partner terms" },
  { value: "delivery_partner_terms", label: "Delivery partner terms" },
];
const kindLabel = (k: string) => KINDS.find((x) => x.value === k)?.label ?? k;
const ACTIONS: Record<string, string> = {
  "legal.draft_created": "Started the draft", "legal.draft_edited": "Edited the draft", "legal.published": "Published",
  "legal.superseded": "Replaced by a newer version", "legal.draft_discarded": "Discarded the draft",
};

interface Doc {
  id: string; kind: Kind; country: string; language: string; version: number | null;
  status: "draft" | "published" | "superseded"; title: string; key_points: string[]; effective_date: string | null;
  summary_of_changes: string | null; created_at: string; updated_at: string; published_at: string | null;
  superseded_at: string | null; can_edit: boolean;
}
interface DocFull extends Doc { body: string; created_by_name: string | null; published_by_name: string | null }
interface Detail { document: DocFull; history: { at: string; action: string; actor: string | null }[] }

const when = (iso: string | null | undefined) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";
const field = "mt-1 block w-full rounded-lg border border-line bg-white px-3 font-normal text-kohl";
const ghost = "h-11 rounded-full border border-line-strong bg-white px-4 text-label font-semibold text-kohl hover:border-peacock";

function Status({ d }: { d: Doc }) {
  const [label, cls] = d.status === "draft" ? ["Draft", "bg-[#FBF4E6] text-[#7A4E0E]"]
    : d.status === "published" ? [`Live · v${d.version}`, "bg-peacock-tint text-peacock-dark"]
      : [`Replaced · v${d.version}`, "bg-porcelain text-muted"];
  return <span className={`inline-flex items-center rounded-lg px-2 py-1 text-caption ${cls}`}>{label}</span>;
}

function NewDraft({ countries, onCreated }: { countries: { code: string; name: string; languages: string[] }[]; onCreated: (id: string) => void }) {
  const [kind, setKind] = useState<Kind>("terms");
  const [country, setCountry] = useState(countries[0]?.code ?? "");
  const [language, setLanguage] = useState("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const langs = countries.find((c) => c.code === country)?.languages ?? ["en"];
  if (!countries.length) return null;
  return (
    <form className="flex flex-wrap items-end gap-3 rounded-2xl bg-white p-5" aria-label="Start a draft" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const r = await adminApi.post<Detail>("/user/admin/legal/documents", { kind, country, language });
        onCreated(r.data.document.id);
      } catch (err) {
        setError(apiMessage(err));
      } finally {
        setBusy(false);
      }
    }}>
      <label className="text-label">Document<select value={kind} onChange={(e) => setKind(e.target.value as Kind)} className={`${field} h-11`}>
        {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}</select></label>
      <label className="text-label">Country<select value={country} onChange={(e) => { setCountry(e.target.value); setLanguage("en"); }} className={`${field} h-11`}>
        {countries.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</select></label>
      <label className="text-label">Language<select value={language} onChange={(e) => setLanguage(e.target.value)} className={`${field} h-11`}>
        {langs.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}</select></label>
      <button type="submit" disabled={busy} className="h-11 rounded-full bg-peacock px-5 text-label font-bold text-white disabled:opacity-60" data-testid="legal-new-draft">
        {busy ? "Starting…" : "Start a draft"}
      </button>
      <p className="w-full text-small text-muted">A new draft starts as a copy of the version that is live now, so you only change what changes.</p>
      {error ? <p role="alert" className="w-full text-label text-chili">{error}</p> : null}
    </form>
  );
}

function Editor({ id, nextVersion, onClose }: { id: string; nextVersion: number; onClose: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["legal-doc", id], queryFn: async () => (await adminApi.get<Detail>(`/user/admin/legal/documents/${id}`)).data });
  const [form, setForm] = useState<{ title: string; effective_date: string; summary: string; points: string; body: string } | null>(null);
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [confirming, setConfirming] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const d = q.data?.document;
  const editing = Boolean(d && d.status === "draft" && d.can_edit);
  const f = form ?? (d ? { title: d.title, effective_date: d.effective_date ?? "", summary: d.summary_of_changes ?? "", points: d.key_points.join("\n"), body: d.body } : null);

  async function run(fn: () => Promise<unknown>, ok: string, after?: () => void) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      setForm(null);
      await Promise.all([qc.invalidateQueries({ queryKey: ["legal-doc", id] }), qc.invalidateQueries({ queryKey: ["legal-docs"] })]);
      after?.();
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }
  const save = () => adminApi.patch(`/user/admin/legal/documents/${id}`, {
    title: f!.title, effective_date: f!.effective_date || null, summary_of_changes: f!.summary.trim() || null,
    key_points: f!.points.split("\n").map((p) => p.trim()).filter(Boolean), body: f!.body,
  });

  if (q.isLoading) return <section className="rounded-2xl bg-white p-6 text-body text-muted" aria-busy="true">Loading the document…</section>;
  if (q.isError || !d || !f) return <section className="rounded-2xl bg-white p-6"><p role="alert" className="text-label text-chili">{apiMessage(q.error)}</p><button type="button" onClick={onClose} className={`${ghost} mt-3`}>Back to all documents</button></section>;

  return (
    <section className="space-y-5 rounded-2xl bg-white p-5 sm:p-6" aria-label="Document" data-testid="legal-editor">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={onClose} className="text-label font-semibold text-peacock">← All documents</button>
        <h2 className="m-0 text-h2">{kindLabel(d.kind)} · {d.country} · {d.language.toUpperCase()}</h2>
        <Status d={d} />
      </div>
      <p className="m-0 text-small text-muted">
        {d.status === "draft" ? `Draft started ${when(d.created_at)}${d.created_by_name ? ` by ${d.created_by_name}` : ""}. Publishing makes it version ${nextVersion}.`
          : `Version ${d.version}, in effect from ${when(d.effective_date)}. Published ${when(d.published_at)}${d.published_by_name ? ` by ${d.published_by_name}` : ""}${d.superseded_at ? `, replaced ${when(d.superseded_at)}` : ""}.`}
        {!d.can_edit ? " You can read this document; a country manager for this country or a super admin can change it." : ""}
        {d.can_edit && d.status !== "draft" ? " Published versions don't change: start a draft to write the next one." : ""}
      </p>

      {editing ? (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void run(save, "Draft saved."); }}>
          <div className="grid gap-4 md:grid-cols-[1fr_200px]">
            <label className="text-label">Title<input required maxLength={200} value={f.title} onChange={(e) => setForm({ ...f, title: e.target.value })} className={`${field} h-11`} /></label>
            <label className="text-label">In effect from<input type="date" value={f.effective_date} onChange={(e) => setForm({ ...f, effective_date: e.target.value })} className={`${field} h-11`} /></label>
          </div>
          <label className="block text-label">What changed (shown in the version history)<input maxLength={500} value={f.summary} onChange={(e) => setForm({ ...f, summary: e.target.value })} className={`${field} h-11`} placeholder="For example: clearer refund times" /></label>
          <label className="block text-label">Key points (one per line, up to 12; shown in a box at the top)
            <textarea rows={6} value={f.points} onChange={(e) => setForm({ ...f, points: e.target.value })} className={`${field} py-2`} data-testid="legal-points" />
          </label>
          <div>
            <div role="tablist" aria-label="Body" className="flex gap-1">
              {(["write", "preview"] as const).map((t) => (
                <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                  className={`h-10 rounded-full px-4 text-label ${tab === t ? "bg-kohl font-bold text-white" : "font-semibold text-kohl hover:bg-porcelain"}`}>
                  {t === "write" ? "Write (Markdown)" : "Preview"}
                </button>
              ))}
            </div>
            {tab === "write" ? (
              <label className="mt-2 block text-label">
                <span className="sr-only">Body in Markdown</span>
                <textarea rows={28} value={f.body} onChange={(e) => setForm({ ...f, body: e.target.value })} className={`${field} py-2 font-mono text-small leading-relaxed`} data-testid="legal-body" />
                <span className="mt-1 block text-small font-normal text-muted">## starts a section (it goes in the table of contents), ### a sub-section; - for a list; **bold**; [text](/privacy) for a link; | a | b | for a table.</span>
              </label>
            ) : <div className="mt-2 max-h-[720px] overflow-y-auto rounded-xl border border-line p-5"><MarkdownPreview source={f.body} /></div>}
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
            <button type="button" disabled={busy} onClick={() => setConfirming(true)} className="h-11 rounded-full bg-peacock px-5 text-label font-bold text-white disabled:opacity-60" data-testid="legal-publish">
              Publish as version {nextVersion}
            </button>
            <button type="submit" disabled={busy} className={ghost} data-testid="legal-save">Save draft</button>
            <button type="button" disabled={busy} className="ml-auto h-11 rounded-full px-4 text-label font-semibold text-chili hover:bg-[#FCEDEC]"
              onClick={() => {
                if (window.confirm("Discard this draft? Its changes are lost; the live version stays as it is.")) {
                  void run(() => adminApi.delete(`/user/admin/legal/documents/${id}`), "Draft discarded.", onClose);
                }
              }}>Discard draft</button>
          </div>
          {confirming ? (
            <div role="alertdialog" aria-labelledby="publish-q" className="rounded-xl border border-kesar bg-[#FBF4E6] p-4">
              <p id="publish-q" className="m-0 text-body font-semibold">Publish version {nextVersion} of {kindLabel(d.kind)} for {d.country} ({d.language.toUpperCase()})?</p>
              <p className="m-0 mt-1 text-small text-muted">It replaces the live version for everyone at once. The replaced version stays in the public version history, and signed-in people are told once that the document changed.</p>
              <div className="mt-3 flex gap-2">
                <button type="button" disabled={busy} className="h-11 rounded-full bg-peacock px-5 text-label font-bold text-white disabled:opacity-60" data-testid="legal-publish-confirm"
                  onClick={() => void run(async () => { await save(); await adminApi.post(`/user/admin/legal/documents/${id}/publish`); }, `Published version ${nextVersion}.`)}>
                  {busy ? "Publishing…" : "Yes, publish"}
                </button>
                <button type="button" onClick={() => setConfirming(false)} className={ghost}>Cancel</button>
              </div>
            </div>
          ) : null}
        </form>
      ) : (
        <div className="space-y-4">
          <h3 className="m-0 text-h3">{d.title}</h3>
          {d.key_points.length ? <ul className="m-0 list-disc space-y-1 rounded-xl bg-porcelain py-3 pl-8 pr-4 text-body">{d.key_points.map((p, i) => <li key={i}>{p}</li>)}</ul> : null}
          <div className="max-h-[720px] overflow-y-auto rounded-xl border border-line p-5"><MarkdownPreview source={d.body} /></div>
        </div>
      )}
      {msg ? <p role="status" className={`m-0 text-label ${msg.ok ? "text-peacock" : "text-chili"}`} data-testid="legal-msg">{msg.text}</p> : null}

      <div>
        <h3 className="m-0 text-h3">Audit log</h3>
        <ol className="m-0 mt-2 space-y-1 p-0 text-small" data-testid="legal-audit">
          {q.data!.history.map((h, i) => (
            <li key={i} className="flex flex-wrap gap-x-2 border-b border-line py-1.5 last:border-0">
              <span className="text-muted">{new Date(h.at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</span>
              <b>{h.actor ?? "System"}</b><span>{ACTIONS[h.action] ?? h.action}</span>
            </li>
          ))}
          {!q.data!.history.length ? <li className="text-muted">No changes recorded (seeded document).</li> : null}
        </ol>
      </div>
    </section>
  );
}

function LegalPage() {
  const scope = useScope();
  const { country, region, city } = parseScope(scope);
  const params = useSearchParams();
  const router = useRouter();
  const docId = params.get("doc");
  const [kind, setKind] = useState<Kind | "">("");
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();
  const list = useQuery({
    queryKey: ["legal-docs", country, kind],
    queryFn: async () => (await adminApi.get<Doc[]>("/user/admin/legal/documents", {
      params: { ...(country !== "ALL" ? { country } : {}), ...(kind ? { kind } : {}) } })).data,
  });
  const docs = useMemo(() => list.data ?? [], [list.data]);
  const editable = useMemo(() => (markets ?? []).filter((c) => can(me, "legal.edit", c.code) && (country === "ALL" || c.code === country))
    .map((c) => ({ code: c.code, name: c.name, languages: [...new Set(["en", ...c.locales.map((l) => l.split("-")[0]!)])] })), [markets, me, country]);
  const open = (id: string | null) => {
    const q = new URLSearchParams(params.toString());
    if (id) q.set("doc", id); else q.delete("doc");
    router.push(`/content/legal?${q.toString()}`);
  };
  const selected = docs.find((d) => d.id === docId);
  const nextVersion = selected
    ? Math.max(0, ...docs.filter((d) => d.kind === selected.kind && d.country === selected.country && d.language === selected.language).map((d) => d.version ?? 0)) + 1
    : 1;
  // One group per document (country, kind, language): drafts first, then versions newest first.
  const groups = useMemo(() => {
    const m = new Map<string, Doc[]>();
    for (const d of docs) {
      const k = `${d.country}·${d.kind}·${d.language}`;
      m.set(k, [...(m.get(k) ?? []), d]);
    }
    return [...m.values()];
  }, [docs]);

  return (
    <ConsoleShell section="Legal" country={country} region={region} city={city} scopeHref={(s) => `/content/legal?scope=${s.split("-")[0]}`}>
      <div>
        <h1 className="m-0 text-h1 tracking-[-0.8px]">Legal</h1>
        <p className="m-0 mt-1 max-w-[760px] text-body text-muted">
          Terms of use and Privacy notice for each country, as the website and apps show them. Publishing a draft makes it the next version; older versions stay readable in the public version history. Outside production every document carries &ldquo;Draft: pending legal review&rdquo;.
        </p>
      </div>
      {docId ? <Editor key={docId} id={docId} nextVersion={nextVersion} onClose={() => open(null)} /> : (
        <>
          <NewDraft countries={editable} onCreated={(id) => open(id)} />
          <section className="min-w-0 space-y-3 rounded-2xl bg-white p-5 sm:p-6" aria-label="Documents">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h2 className="m-0 text-h3">Documents {country !== "ALL" ? `in ${markets?.find((c) => c.code === country)?.name ?? country}` : "in every country"}</h2>
              <label className="text-label">Show<select value={kind} onChange={(e) => setKind(e.target.value as Kind | "")} className={`${field} h-10`}>
                <option value="">Every document</option>{KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}</select></label>
            </div>
            {list.isLoading ? <p className="text-body text-muted" aria-busy="true">Loading documents…</p> : null}
            {list.isError ? <p role="alert" className="text-label text-chili">{apiMessage(list.error)} <button type="button" className="font-semibold underline" onClick={() => void list.refetch()}>Try again</button></p> : null}
            {!list.isLoading && !groups.length ? <p className="text-body text-muted">No documents here yet. {editable.length ? "Start a draft above." : "A country manager for this country can start one."}</p> : null}
            <div className="relative table-scroll">
              <table className="w-full min-w-[640px] text-left text-small" data-testid="legal-list">
                <thead className="text-caption text-muted"><tr><th className="py-2">Document</th><th>Country</th><th>Language</th><th>Status</th><th>In effect from</th><th>Updated</th><th><span className="sr-only">Open</span></th></tr></thead>
                <tbody className="divide-y divide-line">
                  {groups.flat().map((d) => (
                    <tr key={d.id} className={d.status === "superseded" ? "text-muted" : ""}>
                      <td className="py-2.5"><b className={d.status === "superseded" ? "font-semibold" : ""}>{kindLabel(d.kind)}</b>{d.title !== kindLabel(d.kind) ? <div className="text-small text-muted">{d.title}</div> : null}</td>
                      <td>{markets?.find((c) => c.code === d.country)?.name ?? d.country}</td>
                      <td>{d.language.toUpperCase()}</td>
                      <td><Status d={d} /></td>
                      <td>{when(d.effective_date)}</td>
                      <td>{when(d.updated_at)}</td>
                      <td className="text-right">
                        <Link href={`/content/legal?${new URLSearchParams({ ...(scope !== "*" ? { scope } : {}), doc: d.id }).toString()}`}
                          className="inline-flex h-9 items-center rounded-full border border-line-strong px-3 text-label font-semibold text-kohl hover:border-peacock">
                          {d.status === "draft" && d.can_edit ? "Edit" : "Open"}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><LegalPage /></Suspense>;
}
