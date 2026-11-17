"use client";
// Partners: live kitchens, kitchens applying to join (the five steps, the
// food licence to check, approve or turn down), and delivery partners' documents to
// review. Every list is cut to your scopes; approving needs partners.edit /
// riders.edit for that city or country.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { ago, apiMessage, DOC_LABELS, money, useScope, type Kitchen, type RiderDoc } from "@/lib/ops";

const TABS = [
  { key: "kitchens", label: "Kitchens" },
  { key: "applications", label: "Applications" },
  { key: "riders", label: "Delivery partner documents" },
] as const;

interface Application {
  restaurant_id: string; name: string; status: string; done: number; total: number; current: string | null;
  fssai_number: string | null; fssai_expires_on: string | null; fssai_document: boolean; fssai_document_key: string | null;
  gstin: string | null; payout_account: string | null; commission_percent: string | null;
  steps: { key: string; title: string; done: boolean; detail: string }[];
}

function useCityNames(scope: string) {
  const { data: markets } = useMarkets();
  const { country, region, city } = parseScope(scope);
  return (markets ?? []).filter((c) => country === "ALL" || c.code === country)
    .flatMap((c) => c.regions.filter((r) => !region || r.code === region).flatMap((r) => r.cities.filter((x) => !city || x.code === city)))
    .map((c) => ({ code: c.code, name: c.name }));
}

interface Commission {
  restaurant_id: string; name: string; city: string | null; country: string; tier: string | null; percent: string | null; flat_per_order: string | null;
  rate_source: { rule_id: string; version: number; template: string; name: string | null; scope_level: string; scope_id: string; effective_to: string | null } | null;
  pending_tier_change: { id: string; to: string; from: string | null; requested_by: string; note: string } | null;
}

const LEVEL_SOURCE: Record<string, string> = { restaurant: "this kitchen's own rule", city: "the city's rule", country: "the country's rule", region: "the state's rule" };

/** A kitchen's commission (Pricing & Rules, commissions first): the rate it pays now, which
 * rule sets it and until when, and its tier; a tier change waits for a second admin. */
function KitchenCommission({ kitchen }: { kitchen: Kitchen }) {
  const { data: me } = useAdminMe();
  const { data: markets } = useMarkets();
  const qc = useQueryClient();
  const c = useQuery({ queryKey: ["kitchen-commission", kitchen.id], queryFn: async () => (await adminApi.get<Commission>(`/user/rules/commission/restaurants/${kitchen.id}`)).data });
  const [tier, setTier] = useState("A");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (c.isError) return <p role="alert" className="rounded-2xl bg-white p-6 text-small">The commission didn&apos;t load. <button type="button" onClick={() => void c.refetch()} className="font-bold text-peacock">Try again</button></p>;
  if (!c.data) return <p className="rounded-2xl bg-white p-6 text-small text-muted" aria-busy="true">Loading commission…</p>;
  const d = c.data;
  const scope = d.city ?? d.country;
  const currency = markets?.find((x) => x.code === d.country)?.currency;
  const src = d.rate_source;
  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      setNote("");
      await qc.invalidateQueries({ queryKey: ["kitchen-commission", kitchen.id] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  const pending = d.pending_tier_change;
  return (
    <section className="space-y-3 rounded-2xl bg-white p-6" aria-label={`Commission · ${d.name}`}>
      <h2 className="m-0 text-h2">{d.name}</h2>
      <p className="text-body" data-testid="kitchen-commission">
        Pays <b>{d.percent ?? "no"}%</b> of food{d.flat_per_order && currency ? ` + ${money(d.flat_per_order, currency, 2)} per order` : ""}
        {src ? <> · set by {LEVEL_SOURCE[src.scope_level] ?? src.scope_level}{src.name ? ` “${src.name}”` : ""} (v{src.version})</> : null}
        {src?.effective_to ? <> · until {new Date(src.effective_to).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</> : null}
      </p>
      <p className="text-small">Tier <b data-testid="kitchen-tier">{d.tier ?? "default"}</b>
        {pending ? <> · <span className="text-kesar-ink">change to tier {pending.to} waiting for approval (“{pending.note}”)</span></> : null}</p>
      {pending && can(me, "rules.approve", scope) && pending.requested_by !== me?.user_id ? (
        <div className="flex gap-2">
          <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/commission/tier-changes/${pending.id}/approve`, {}), `Tier changed to ${pending.to}.`)}
            className="h-10 rounded-full bg-peacock px-4 font-bold text-white">Approve tier {pending.to}</button>
          <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/commission/tier-changes/${pending.id}/reject`, {}), "Tier change turned down.")}
            className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili">Turn down</button>
        </div>
      ) : null}
      {!pending && can(me, "rules.edit", scope) ? (
        <div className="flex flex-wrap items-end gap-2 text-small">
          <label className="font-bold">Change tier to
            <select aria-label="New tier" value={tier} onChange={(e) => setTier(e.target.value)} className="mt-1 block h-10 rounded-lg border border-line px-2 font-normal">
              {["A", "B", "C"].filter((t) => t !== d.tier).map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <input aria-label="Why (kept in the audit log)" placeholder="Why (kept in the audit log)" value={note} onChange={(e) => setNote(e.target.value)} className="h-10 flex-1 rounded-full border border-line px-4" />
          <button type="button" disabled={busy || note.trim().length < 3}
            onClick={() => void run(() => adminApi.post(`/user/rules/commission/restaurants/${kitchen.id}/tier`, { tier, note: note.trim() }), "Sent for approval: a second admin approves tier changes.")}
            className="h-10 rounded-full border border-line-strong px-4 font-bold disabled:opacity-40">Ask for tier {tier}</button>
        </div>
      ) : null}
      {msg ? <p role="status" className={`text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
    </section>
  );
}

async function openFile(key: string) {
  const r = await adminApi.get("/user/uploads/view", { params: { key }, responseType: "blob" });
  window.open(URL.createObjectURL(r.data as Blob), "_blank", "noopener");
}

function Kitchens({ scope }: { scope: string }) {
  const cities = useCityNames(scope);
  const [q, setQ] = useState("");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["kitchens", cities.map((c) => c.name).join(",")],
    queryFn: async () => (await Promise.all(cities.map(async (c) =>
      (await adminApi.get<{ items: Kitchen[] }>("/user/restaurants/admin/kitchens", { params: { city: c.name, limit: 100 } })).data.items))).flat(),
    enabled: cities.length > 0,
  });
  const list = (data ?? []).filter((k) => !q || k.name.toLowerCase().includes(q.toLowerCase()));
  const [open, setOpen] = useState<string | null>(null);
  const opened = list.find((k) => k.id === open) ?? null;
  return (
    <section className="space-y-3">
      <input aria-label="Search kitchens" placeholder="Search kitchens" value={q} onChange={(e) => setQ(e.target.value)} className="h-11 w-full max-w-80 rounded-full border border-line-strong bg-white px-4 text-small" />
      {isLoading ? (
        <ul aria-busy="true" className="space-y-2 rounded-2xl bg-white p-4">{[0, 1, 2, 3].map((i) => <li key={i} className="h-10 animate-pulse rounded-lg bg-porcelain" />)}</ul>
      ) : isError ? (
        <div role="alert" className="space-y-2 rounded-2xl bg-white p-6">
          <p className="m-0 font-bold">The kitchens didn&apos;t load.</p>
          <button type="button" onClick={() => void refetch()} className="h-10 rounded-full border border-line px-4 font-bold text-peacock">Try again</button>
        </div>
      ) : !list.length ? (
        <div className="space-y-1 rounded-2xl bg-white p-6">
          <p className="m-0 font-bold">{q ? "No kitchen matches that name." : "No live kitchens here yet."}</p>
          <p className="m-0 text-small text-muted">{q ? "Check the spelling, or clear the search." : "Kitchens show here once their application is approved (see Applications)."}</p>
        </div>
      ) : (
        <div className="table-scroll rounded-2xl">
          <table className="table-stack w-full text-left text-small [--stack-inset:1rem]">
            <thead className="text-caption text-muted"><tr><th className="px-4 py-3">Kitchen</th><th>City</th><th>Cuisine</th><th>Rating</th><th>Food licence</th><th>Open</th></tr></thead>
            <tbody className="divide-y divide-line">
              {list.map((k) => (
                <tr key={k.id} onClick={() => setOpen(k.id)} className={`cursor-pointer ${open === k.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
                  <td className="stack-title px-4 py-3 font-bold"><button type="button" aria-pressed={open === k.id} className="min-h-11 text-left font-bold md:min-h-0">{k.name}</button></td>
                  <td data-label="City">{k.city}</td><td data-label="Cuisine" className="text-muted">{k.cuisine_types.join(", ")}</td>
                  <td data-label="Rating" className="tabular-nums">{k.rating ? `★ ${Number(k.rating).toFixed(1)}` : "—"}</td>
                  <td data-label="Food licence" className="text-muted tabular-nums">{k.fssai_expires_on ? `until ${k.fssai_expires_on}` : "—"}</td>
                  <td data-label="Open" className="md:pr-4">{k.is_open === false ? "Paused" : "Yes"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {opened ? <KitchenCommission key={opened.id} kitchen={opened} /> : null}
    </section>
  );
}

function Applications({ scope }: { scope: string }) {
  const qc = useQueryClient();
  const { data: me } = useAdminMe();
  const cities = useCityNames(scope);
  const pending = useQuery({ queryKey: ["applications"], queryFn: async () => (await adminApi.get<Kitchen[]>("/user/restaurants/admin/pending")).data });
  const mine = (pending.data ?? []).filter((k) => cities.some((c) => c.name === k.city));
  const [open, setOpen] = useState<string | null>(null);
  const app = useQuery({
    queryKey: ["application", open],
    queryFn: async () => (await adminApi.get<Application>(`/user/restaurants/${open}/application`)).data,
    enabled: Boolean(open),
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  async function decide(id: string, ok: boolean) {
    setMsg(null);
    try {
      if (ok) await adminApi.post(`/user/restaurants/${id}/approve`);
      else await adminApi.post(`/user/restaurants/${id}/reject`, null, { params: { reason } });
      setMsg(ok ? "Approved: the kitchen is live and its tablet starts ringing." : "Turned down.");
      setOpen(null);
      await qc.invalidateQueries({ queryKey: ["applications"] });
    } catch (e) {
      setMsg(apiMessage(e));
    }
  }
  const kitchen = mine.find((k) => k.id === open);
  const cityCode = cities.find((c) => c.name === kitchen?.city)?.code ?? "";
  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <section className="rounded-2xl bg-white p-2" aria-label="Kitchens applying">
        <div className="px-3 py-2 text-label">Applying · {mine.length}</div>
        {pending.isLoading ? <p aria-busy="true" className="px-3 pb-3 text-small text-muted">Loading applications…</p> : null}
        {pending.isError ? <p role="alert" className="px-3 pb-3 text-small">The applications didn&apos;t load. <button type="button" onClick={() => void pending.refetch()} className="font-bold text-peacock">Try again</button></p> : null}
        {pending.data && mine.length === 0 ? <p className="px-3 pb-3 text-small text-muted">No kitchens waiting. New applications from the website&apos;s Add your kitchen page show here.</p> : null}
        {mine.map((k) => (
          <button key={k.id} type="button" onClick={() => setOpen(k.id)} className={`block w-full rounded-xl px-3 py-2.5 text-left text-small ${open === k.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
            <b>{k.name}</b><div className="text-muted">{k.city} · {k.cuisine_types.join(", ")} · applied {ago(k.created_at)}</div>
          </button>
        ))}
      </section>
      {open && app.data ? (
        <section className="space-y-4 rounded-2xl bg-white p-6" aria-label={`Application · ${app.data.name}`}>
          <div><h2 className="m-0 text-h2">{app.data.name}</h2><p className="text-small text-muted">{kitchen?.city} · {app.data.done} of {app.data.total} done · commission {app.data.commission_percent}%</p></div>
          <ol className="space-y-2">
            {app.data.steps.map((s, i) => (
              <li key={s.key} className="flex items-center gap-3 text-small">
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-caption ${s.done ? "bg-peacock text-white" : "border-2 border-line-strong text-muted"}`}>{s.done ? "✓" : i + 1}</span>
                <b className="w-44">{s.title}</b><span className="text-muted">{s.detail}</span>
              </li>
            ))}
          </ol>
          <dl className="grid gap-2 rounded-xl bg-porcelain p-4 text-small sm:grid-cols-2">
            <div><dt className="font-bold">FSSAI licence</dt><dd>{app.data.fssai_number ?? "not given"}{app.data.fssai_expires_on ? ` · until ${app.data.fssai_expires_on}` : ""}
              {app.data.fssai_document_key ? <> · <button type="button" className="font-bold text-peacock" onClick={() => void openFile(app.data!.fssai_document_key!)}>View certificate</button></> : null}</dd></div>
            <div><dt className="font-bold">GSTIN</dt><dd>{app.data.gstin ?? "not given"}</dd></div>
            <div><dt className="font-bold">Payout account</dt><dd>{app.data.payout_account ?? "not set up"}</dd></div>
          </dl>
          {can(me, "partners.edit", cityCode) ? (
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" onClick={() => void decide(open, true)} disabled={app.data.done < app.data.total - 1}
                title={app.data.done < app.data.total - 1 ? "Every step before going live must be done" : undefined}
                className="h-11 rounded-full bg-peacock px-5 font-bold text-white disabled:opacity-40">Approve and go live</button>
              <input aria-label="Reason for turning down" placeholder="Reason (kept with the application)" value={reason} onChange={(e) => setReason(e.target.value)} className="h-11 flex-1 rounded-full border border-line px-4 text-small" />
              <button type="button" disabled={reason.trim().length < 3} onClick={() => void decide(open, false)} className="h-11 rounded-full border border-line-strong px-5 font-bold text-chili disabled:opacity-40">Turn down</button>
            </div>
          ) : <p className="text-small text-muted">You can view this application; approving needs partners.edit for {kitchen?.city}.</p>}
          {msg ? <p role="status" className="text-label text-peacock">{msg}</p> : null}
        </section>
      ) : <div className="rounded-2xl bg-white p-6 text-muted">{open && app.isLoading ? "Loading the application…" : open && app.isError ? "The application didn't load. Pick it again to retry." : msg ?? "Pick a kitchen to see its application."}</div>}
    </div>
  );
}

function Riders({ scope }: { scope: string }) {
  const qc = useQueryClient();
  const { data: me } = useAdminMe();
  const { country } = parseScope(scope);
  const docs = useQuery({
    queryKey: ["rider-docs", country],
    queryFn: async () => (await adminApi.get<RiderDoc[]>("/user/riders/documents", { params: country === "ALL" ? {} : { country } })).data,
  });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  async function review(d: RiderDoc, decision: "approve" | "reject") {
    setMsg(null);
    try {
      await adminApi.post(`/user/riders/documents/${d.id}/review`, { decision, note: notes[d.id] || null });
      setMsg(`${DOC_LABELS[d.kind] ?? d.kind} for ${d.rider_name} ${decision === "approve" ? "approved" : "sent back"}.`);
      await qc.invalidateQueries({ queryKey: ["rider-docs"] });
    } catch (e) {
      setMsg(apiMessage(e));
    }
  }
  return (
    <section className="space-y-3">
      <p className="text-small text-muted">Delivery partners work across a country, so their documents are reviewed by country. A delivery partner goes online once their licence, insurance and background check are approved.</p>
      {msg ? <p role="status" className="text-label text-peacock">{msg}</p> : null}
      {docs.isLoading ? <p aria-busy="true" className="rounded-2xl bg-white p-6 text-muted">Loading documents…</p> : null}
      {docs.isError ? (
        <div role="alert" className="space-y-2 rounded-2xl bg-white p-6">
          <p className="m-0 font-bold">The documents didn&apos;t load.</p>
          <button type="button" onClick={() => void docs.refetch()} className="h-10 rounded-full border border-line px-4 font-bold text-peacock">Try again</button>
        </div>
      ) : null}
      {docs.data && docs.data.length === 0 ? <p className="rounded-2xl bg-white p-6 text-muted">Nothing to review. Documents delivery partners send from BhojanGo Delivery show here.</p> : null}
      {(docs.data ?? []).map((d) => (
        <div key={d.id} className="flex flex-wrap items-center gap-3 rounded-2xl bg-white p-4 text-small">
          <div className="min-w-[220px] flex-1"><b>{d.rider_name}</b> <span className="text-muted">· {d.rider_phone} · {d.country}</span>
            <div>{DOC_LABELS[d.kind] ?? d.kind} · sent {ago(d.submitted_at)}</div></div>
          {d.file_key ? <button type="button" className="font-bold text-peacock" onClick={() => void openFile(d.file_key!)}>View</button> : <span className="text-muted">our check</span>}
          {can(me, "riders.edit", d.country) ? (
            <>
              <input aria-label={`Note for ${d.rider_name}`} placeholder="What to fix (if sending back)" value={notes[d.id] ?? ""}
                onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))} className="h-10 w-64 rounded-full border border-line px-3" />
              <button type="button" onClick={() => void review(d, "reject")} disabled={!notes[d.id]} className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili disabled:opacity-40">Send back</button>
              <button type="button" onClick={() => void review(d, "approve")} className="h-10 rounded-full bg-peacock px-4 font-bold text-white">Approve</button>
            </>
          ) : null}
        </div>
      ))}
    </section>
  );
}

function PartnersPage() {
  const scope = useScope();
  const params = useSearchParams();
  const router = useRouter();
  const tab = (params.get("tab") ?? "kitchens") as (typeof TABS)[number]["key"];
  const { country, region, city } = parseScope(scope);
  return (
    <ConsoleShell section="Partners" country={country} region={region} city={city} scopeHref={(s) => `/partners?scope=${s}&tab=${tab}`}>
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="m-0 text-h1">Partners</h1>
        <nav aria-label="Partners" className="ml-auto flex max-w-full overflow-x-auto rounded-full bg-white p-1">
          {TABS.map((t) => (
            <button key={t.key} type="button" onClick={() => router.replace(`/partners?scope=${scope}&tab=${t.key}`)} aria-current={tab === t.key ? "page" : undefined}
              className={`h-9 shrink-0 whitespace-nowrap rounded-full px-4 text-label ${tab === t.key ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>{t.label}</button>
          ))}
        </nav>
      </div>
      {tab === "kitchens" ? <Kitchens scope={scope} /> : null}
      {tab === "applications" ? <Applications scope={scope} /> : null}
      {tab === "riders" ? <Riders scope={scope} /> : null}
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><PartnersPage /></Suspense>;
}
