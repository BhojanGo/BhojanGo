"use client";
// AdminPricing.html: Pricing & Rules. Rules by family for the scope you picked
// (each with where it comes from: inherited or overridden here), a rule's
// versions and approvals, a new draft version, and the approvals queue (a
// second admin approves money rules). The price simulator is a tab.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, useAdminMe } from "@/lib/markets";
import { RuleEditor } from "@/components/ops/RuleEditor";
import { ago, apiMessage, FAMILIES, useScope, type Rule } from "@/lib/ops";
import { describe } from "@/lib/ruleWords";

interface History {
  versions: Rule[];
  approvals: Record<string, { requested_at: string; decision: string | null; decided_at: string | null; note: string | null }[]>;
}

const STATUS_STYLE: Record<string, string> = {
  published: "bg-peacock-tint text-peacock-dark", pending_approval: "bg-kesar-tint text-kesar-ink", draft: "bg-line-soft text-muted",
  rejected: "bg-danger-tint text-danger-ink", superseded: "bg-line-soft text-muted", ended: "bg-line-soft text-muted",
};
const STATUS_LABEL: Record<string, string> = { published: "Live", pending_approval: "Waiting for approval", draft: "Draft", rejected: "Sent back", superseded: "Retired", ended: "Ended" };

function Pill({ s }: { s: string }) {
  return <span className={`rounded-lg px-2 py-1 text-xs font-bold ${STATUS_STYLE[s] ?? "bg-line-soft"}`}>{STATUS_LABEL[s] ?? s}</span>;
}

function where(r: Rule, scope: string) {
  if (r.market_scope === scope) return "Set here";
  if (scope !== "*" && r.market_scope.length < scope.length) return `Inherited · ${r.market_scope === "*" ? "everywhere" : r.market_scope}`;
  return r.scope_level === "restaurant" ? "A restaurant's own" : r.scope_level === "zone" ? "A zone's" : r.market_scope;
}

function Params({ rule }: { rule: Rule }) {
  return <p className="rounded-xl bg-porcelain p-4 text-[15px] leading-relaxed" data-testid="rule-words">{describe(rule.template, rule.params, rule.market_scope)}</p>;
}

function RuleDetail({ rule, onChanged }: { rule: Rule; onChanged: () => void }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const history = useQuery({ queryKey: ["rule-history", rule.id], queryFn: async () => (await adminApi.get<History>(`/user/rules/${rule.id}/history`)).data });
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const scope = rule.market_scope;
  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      setEditing(false);
      await qc.invalidateQueries({ queryKey: ["rules"] });
      await qc.invalidateQueries({ queryKey: ["rule-history"] });
      onChanged();
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  async function saveDraft(params: Record<string, unknown>) {
    await run(async () => {
      const v = (await adminApi.post<Rule>(`/user/rules/${rule.id}/versions`, { params })).data;
      await adminApi.post(`/user/rules/${v.id}/submit`);
    }, rule.family === "business" ? "Saved and live." : "Sent for approval: a second admin approves money rules.");
  }
  const mineToApprove = rule.status === "pending_approval" && can(me, "rules.approve", scope) && rule.created_by !== me?.user_id;
  return (
    <section className="space-y-4 rounded-2xl bg-white p-6" aria-label={`Rule · ${rule.name ?? rule.template}`}>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 font-display text-2xl font-semibold">{rule.name ?? rule.template.replace(/_/g, " ")}</h2>
        <Pill s={rule.status} /> <span className="text-sm text-muted">v{rule.version} · {rule.market_scope === "*" ? "everywhere" : rule.market_scope} · since {new Date(rule.effective_from).toLocaleDateString()}</span>
      </div>
      {editing ? (
        <RuleEditor params={rule.params} busy={busy} onCancel={() => setEditing(false)} onSave={(p) => void saveDraft(p)}
          saveLabel={rule.family === "business" ? "Save" : "Send for approval"} />
      ) : <Params rule={rule} />}
      <div className="flex flex-wrap items-center gap-2">
        {!editing && rule.status === "published" && can(me, "rules.edit", scope) ? (
          <button type="button" onClick={() => setEditing(true)} className="h-10 rounded-full border border-line-strong px-4 font-bold">New version</button>
        ) : null}
        {mineToApprove ? (
          <>
            <input aria-label="Comment" placeholder="Comment (needed to send back)" value={note} onChange={(e) => setNote(e.target.value)} className="h-10 flex-1 rounded-full border border-line px-4 text-sm" />
            <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/${rule.id}/approve`, { note: note || null }), "Approved and scheduled.")}
              className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">Approve and schedule</button>
            <button type="button" disabled={busy || note.trim().length < 3} onClick={() => void run(() => adminApi.post(`/user/rules/${rule.id}/reject`, { note }), "Sent back with your comment.")}
              className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili disabled:opacity-40">Send back with comment</button>
          </>
        ) : null}
        {rule.status === "pending_approval" && rule.created_by === me?.user_id ? <span className="text-sm text-muted">Waiting for a second admin to approve.</span> : null}
        <Link href={`/pricing/simulator?city=${rule.market_scope.split("-").length === 3 ? rule.market_scope : "IN-TG-HYD"}`} className="ml-auto text-sm font-bold text-peacock">Try it in the price simulator →</Link>
      </div>
      {msg ? <p role="status" className={`text-sm font-semibold ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
      <div>
        <h3 className="mb-2 text-sm font-extrabold">History</h3>
        <ul className="space-y-1 text-sm">
          {(history.data?.versions ?? []).slice().reverse().map((v) => (
            <li key={v.id} className="flex flex-wrap gap-2"><b>v{v.version}</b> <Pill s={v.status} /> <span className="text-muted">{describe(v.template, v.params, v.market_scope)} · {ago(v.created_at)}
              {(history.data?.approvals[v.id] ?? []).filter((a) => a.decision).map((a) => ` · ${a.decision}${a.note ? ` (“${a.note}”)` : ""}`).join("")}</span></li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function PricingPage() {
  const scope = useScope();
  const params = useSearchParams();
  const router = useRouter();
  const tab = params.get("tab") ?? "delivery_fee";
  const { country, region, city } = parseScope(scope);
  const [open, setOpen] = useState<string | null>(null);
  const approvals = useQuery({ queryKey: ["rules", "approvals"], queryFn: async () => (await adminApi.get<Rule[]>("/user/rules/approvals")).data, retry: false });
  const rules = useQuery({
    queryKey: ["rules", tab, scope],
    queryFn: async () => (await adminApi.get<Rule[]>("/user/rules", { params: { family: tab } })).data,
    enabled: tab !== "approvals",
  });
  const relevant = (tab === "approvals" ? approvals.data ?? [] : rules.data ?? [])
    .filter((r) => scope === "*" || r.market_scope === "*" || r.market_scope.startsWith(scope) || scope.startsWith(r.market_scope));
  const selected = relevant.find((r) => r.id === open) ?? null;
  const go = (t: string) => {
    setOpen(null);
    router.replace(`/pricing?scope=${scope}&tab=${t}`);
  };
  return (
    <ConsoleShell section="Pricing & Rules" country={country} region={region} city={city} scopeHref={(s) => `/pricing?scope=${s}&tab=${tab}`}>
      <div>
        <div className="text-[13px] text-muted">Pricing &amp; Rules ▸ {tab === "approvals" ? "Approvals" : FAMILIES.find((f) => f.key === tab)?.label}</div>
        <h1 className="m-0 mt-1 font-display text-[32px] font-semibold tracking-[-0.8px]">Pricing &amp; Rules</h1>
      </div>
      <nav aria-label="Rule families" className="flex flex-wrap gap-1 rounded-2xl bg-white p-1">
        {FAMILIES.map((f) => (
          <button key={f.key} type="button" onClick={() => go(f.key)} aria-current={tab === f.key ? "page" : undefined}
            className={`h-9 rounded-xl px-3 text-sm ${tab === f.key ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>{f.label}</button>
        ))}
        <Link href={`/pricing/simulator?city=${city ?? (country === "US" ? "US-ID-BOI" : "IN-TG-HYD")}`} className="flex h-9 items-center rounded-xl px-3 text-sm font-semibold text-muted">Price simulator</Link>
        <button type="button" onClick={() => go("approvals")} aria-current={tab === "approvals" ? "page" : undefined}
          className={`h-9 rounded-xl px-3 text-sm ${tab === "approvals" ? "bg-kohl font-bold text-white" : "font-semibold text-muted"}`}>
          Approvals {approvals.data?.length ? <span className="ml-1 rounded-full bg-kesar px-1.5 text-xs text-white">{approvals.data.length}</span> : null}
        </button>
      </nav>
      <div className="grid gap-4 xl:grid-cols-[400px_1fr]">
        <section className="rounded-2xl bg-white p-2" aria-label="Rules">
          {relevant.length === 0 ? <p className="p-4 text-sm text-muted">{tab === "approvals" ? "Nothing waiting for you." : "No rules here."}</p> : null}
          {relevant.map((r) => (
            <button key={r.id} type="button" onClick={() => setOpen(r.id)} className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${open === r.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
              <div className="flex items-center justify-between gap-2"><b>{r.name ?? r.template.replace(/_/g, " ")}</b><Pill s={r.status} /></div>
              <div className="text-muted">{where(r, scope)} · v{r.version}</div><div className="mt-0.5 line-clamp-2 text-[13px]">{describe(r.template, r.params, r.market_scope)}</div>
            </button>
          ))}
        </section>
        {selected ? <RuleDetail key={selected.id} rule={selected} onChanged={() => setOpen(null)} /> : <div className="rounded-2xl bg-white p-6 text-muted">Pick a rule to see its settings, history and approvals.</div>}
      </div>
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><PricingPage /></Suspense>;
}
