"use client";
// Partners: live kitchens, kitchens applying to join (the five steps, the
// FSSAI licence to check, approve or turn down), and riders' documents to
// review. Every list is cut to your scopes; approving needs partners.edit /
// riders.edit for that city or country.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { ago, apiMessage, DOC_LABELS, useScope, type Kitchen, type RiderDoc } from "@/lib/ops";

const TABS = [
  { key: "kitchens", label: "Kitchens" },
  { key: "applications", label: "Applications" },
  { key: "riders", label: "Rider documents" },
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

const LEVEL_SOURCE: Record<string, string> = { restaurant: "this restaurant's own rule", city: "the city's rule", country: "the country's rule", region: "the state's rule" };

/** A kitchen's commission (Pricing & Rules, commissions first): the rate it pays now, which
 * rule sets it and until when, and its tier; a tier change waits for a second admin. */
function KitchenCommission({ kitchen }: { kitchen: Kitchen }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const c = useQuery({ queryKey: ["kitchen-commission", kitchen.id], queryFn: async () => (await adminApi.get<Commission>(`/user/rules/commission/restaurants/${kitchen.id}`)).data });
  const [tier, setTier] = useState("A");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!c.data) return <p className="text-sm text-muted">Loading commission…</p>;
  const d = c.data;
  const scope = d.city ?? d.country;
  const cur = d.country === "US" ? "$" : "₹";
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
      <h2 className="m-0 font-display text-2xl font-semibold">{d.name}</h2>
      <p className="text-[15px]" data-testid="kitchen-commission">
        Pays <b>{d.percent ?? "no"}%</b> of food{d.flat_per_order ? ` + ${cur}${Number(d.flat_per_order).toFixed(2)} per order` : ""}
        {src ? <> · set by {LEVEL_SOURCE[src.scope_level] ?? src.scope_level}{src.name ? ` “${src.name}”` : ""} (v{src.version})</> : null}
        {src?.effective_to ? <> · until {new Date(src.effective_to).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</> : null}
      </p>
      <p className="text-sm">Tier <b data-testid="kitchen-tier">{d.tier ?? "default"}</b>
        {pending ? <> · <span className="text-kesar-ink">change to tier {pending.to} waiting for approval (“{pending.note}”)</span></> : null}</p>
      {pending && can(me, "rules.approve", scope) && pending.requested_by !== me?.user_id ? (
        <div className="flex gap-2">
          <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/commission/tier-changes/${pending.id}/approve`, {}), `Tier changed to ${pending.to}.`)}
            className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">Approve tier {pending.to}</button>
          <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/commission/tier-changes/${pending.id}/reject`, {}), "Tier change turned down.")}
            className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili">Turn down</button>
        </div>
      ) : null}
      {!pending && can(me, "rules.edit", scope) ? (
        <div className="flex flex-wrap items-end gap-2 text-sm">
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
      {msg ? <p role="status" className={`text-sm font-semibold ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
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
  const { data, isLoading } = useQuery({
    queryKey: ["kitchens", cities.map((c) => c.name).join(",")],
    queryFn: async () => (await Promise.all(cities.map(async (c) =>
      (await adminApi.get<{ items: Kitchen[] }>("/user/restaurants", { params: { city: c.name, limit: 100 } })).data.items))).flat(),
    enabled: cities.length > 0,
  });
  const list = (data ?? []).filter((k) => !q || k.name.toLowerCase().includes(q.toLowerCase()));
  const [open, setOpen] = useState<string | null>(null);
  const opened = list.find((k) => k.id === open) ?? null;
  return (
    <section className="space-y-3">
      <input aria-label="Search kitchens" placeholder="Search kitchens" value={q} onChange={(e) => setQ(e.target.value)} className="h-11 w-80 rounded-full border border-line-strong bg-white px-4 text-sm" />
      {isLoading ? <p className="text-muted">Loading…</p> : null}
      <div className="overflow-x-auto rounded-2xl bg-white">
        <table className="w-full text-left text-sm">
          <thead className="text-[12px] uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">Kitchen</th><th>City</th><th>Cuisine</th><th>Rating</th><th>FSSAI</th><th>Open</th></tr></thead>
          <tbody className="divide-y divide-line">
            {list.map((k) => (
              <tr key={k.id} onClick={() => setOpen(k.id)} className={`cursor-pointer ${open === k.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}><td className="px-4 py-3 font-bold"><button type="button" className="font-bold">{k.name}</button></td><td>{k.city}</td><td className="text-muted">{k.cuisine_types.join(", ")}</td>
                <td>{k.rating ? `★ ${Number(k.rating).toFixed(1)}` : "—"}</td>
                <td className="text-muted">{k.country === "IN" ? (k.fssai_expires_on ? `until ${k.fssai_expires_on}` : "missing") : "n/a"}</td>
                <td>{k.is_open === false ? "Paused" : "Yes"}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
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
        <div className="px-3 py-2 text-sm font-extrabold">Applying · {mine.length}</div>
        {mine.length === 0 ? <p className="px-3 pb-3 text-sm text-muted">No kitchens waiting.</p> : null}
        {mine.map((k) => (
          <button key={k.id} type="button" onClick={() => setOpen(k.id)} className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${open === k.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
            <b>{k.name}</b><div className="text-muted">{k.city} · {k.cuisine_types.join(", ")} · applied {ago(k.created_at)}</div>
          </button>
        ))}
      </section>
      {open && app.data ? (
        <section className="space-y-4 rounded-2xl bg-white p-6" aria-label={`Application · ${app.data.name}`}>
          <div><h2 className="m-0 font-display text-2xl font-semibold">{app.data.name}</h2><p className="text-sm text-muted">{kitchen?.city} · {app.data.done} of {app.data.total} done · commission {app.data.commission_percent}%</p></div>
          <ol className="space-y-2">
            {app.data.steps.map((s, i) => (
              <li key={s.key} className="flex items-center gap-3 text-sm">
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-extrabold ${s.done ? "bg-peacock text-white" : "border-2 border-line-strong text-muted"}`}>{s.done ? "✓" : i + 1}</span>
                <b className="w-44">{s.title}</b><span className="text-muted">{s.detail}</span>
              </li>
            ))}
          </ol>
          <dl className="grid gap-2 rounded-xl bg-porcelain p-4 text-sm sm:grid-cols-2">
            <div><dt className="font-bold">FSSAI licence</dt><dd>{app.data.fssai_number ?? "not given"}{app.data.fssai_expires_on ? ` · until ${app.data.fssai_expires_on}` : ""}
              {app.data.fssai_document_key ? <> · <button type="button" className="font-bold text-peacock" onClick={() => void openFile(app.data!.fssai_document_key!)}>View certificate</button></> : null}</dd></div>
            <div><dt className="font-bold">GSTIN</dt><dd>{app.data.gstin ?? "not given"}</dd></div>
            <div><dt className="font-bold">Payout account</dt><dd>{app.data.payout_account ?? "not set up"}</dd></div>
          </dl>
          {can(me, "partners.edit", cityCode) ? (
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" onClick={() => void decide(open, true)} disabled={app.data.done < app.data.total - 1}
                title={app.data.done < app.data.total - 1 ? "Every step before going live must be done" : undefined}
                className="h-11 rounded-full bg-peacock px-5 font-extrabold text-white disabled:opacity-40">Approve and go live</button>
              <input aria-label="Reason for turning down" placeholder="Reason (kept with the application)" value={reason} onChange={(e) => setReason(e.target.value)} className="h-11 flex-1 rounded-full border border-line px-4 text-sm" />
              <button type="button" disabled={reason.trim().length < 3} onClick={() => void decide(open, false)} className="h-11 rounded-full border border-line-strong px-5 font-bold text-chili disabled:opacity-40">Turn down</button>
            </div>
          ) : <p className="text-sm text-muted">You can view this application; approving needs partners.edit for {kitchen?.city}.</p>}
          {msg ? <p role="status" className="text-sm font-semibold text-peacock">{msg}</p> : null}
        </section>
      ) : <div className="rounded-2xl bg-white p-6 text-muted">{msg ?? "Pick a kitchen to see its application."}</div>}
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
      <p className="text-sm text-muted">Riders work across a country, so their documents are reviewed by country. A rider goes online once their licence, insurance and background check are approved.</p>
      {msg ? <p role="status" className="text-sm font-semibold text-peacock">{msg}</p> : null}
      {(docs.data ?? []).length === 0 ? <p className="rounded-2xl bg-white p-6 text-muted">Nothing to review.</p> : null}
      {(docs.data ?? []).map((d) => (
        <div key={d.id} className="flex flex-wrap items-center gap-3 rounded-2xl bg-white p-4 text-sm">
          <div className="min-w-[220px] flex-1"><b>{d.rider_name}</b> <span className="text-muted">· {d.rider_phone} · {d.country}</span>
            <div>{DOC_LABELS[d.kind] ?? d.kind} · sent {ago(d.submitted_at)}</div></div>
          {d.file_key ? <button type="button" className="font-bold text-peacock" onClick={() => void openFile(d.file_key!)}>View</button> : <span className="text-muted">our check</span>}
          {can(me, "riders.edit", d.country) ? (
            <>
              <input aria-label={`Note for ${d.rider_name}`} placeholder="What to fix (if sending back)" value={notes[d.id] ?? ""}
                onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))} className="h-10 w-64 rounded-full border border-line px-3" />
              <button type="button" onClick={() => void review(d, "reject")} disabled={!notes[d.id]} className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili disabled:opacity-40">Send back</button>
              <button type="button" onClick={() => void review(d, "approve")} className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">Approve</button>
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
        <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">Partners</h1>
        <nav aria-label="Partners" className="ml-auto flex rounded-full bg-white p-1">
          {TABS.map((t) => (
            <button key={t.key} type="button" onClick={() => router.replace(`/partners?scope=${scope}&tab=${t.key}`)} aria-current={tab === t.key ? "page" : undefined}
              className={`h-9 rounded-full px-4 text-sm ${tab === t.key ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>{t.label}</button>
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
