"use client";
// AdminPricing.html: Pricing & Rules. Every rule family, with the whole life of a
// rule wired: add one for a country, city or restaurant; edit, delete or submit a
// draft; on a live rule, a new version, end it (now or at a date; the inherited rule
// applies again) or roll back to an earlier version. Live rules are never deleted.
// Each row says where the rule comes from ("Inherited from United States · 20%
// (tier B)" / "Set for Boise · 15%" / "Set for Spice Route Kitchen · 12% until 14
// Feb 2027"). A commission draft shows what it would have done to the last 7 days'
// payouts before it's submitted. Money rules (and batching) need a second admin.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { RuleEditor } from "@/components/ops/RuleEditor";
import { adminApi } from "@/lib/api";
import { can, useAdminMe, useMarkets } from "@/lib/markets";
import { ago, apiMessage, FAMILIES, useScope, type Rule } from "@/lib/ops";
import { versionState } from "@/lib/ruleState";
import { describe, unitsFor } from "@/lib/ruleWords";

interface History {
  versions: Rule[];
  approvals: Record<string, { requested_at: string; decision: string | null; decided_at: string | null; note: string | null }[]>;
}
interface Template { family: string; template: string; money: boolean; allowed_levels: string[] }
interface KitchenRef { id: string; name: string; city: string; cityCode: string }
interface Preview {
  orders: number; days: number; commission_now: string; commission_new: string; payout_difference: string;
  restaurants: { name: string; orders: number; commission_now: string; commission_new: string; payout_difference: string }[];
}

const STATUS_STYLE: Record<string, string> = {
  paused: "bg-kesar-tint text-kesar-ink", live: "bg-peacock-tint text-peacock-dark", scheduled: "bg-peacock-tint text-peacock-dark",
  pending_approval: "bg-kesar-tint text-kesar-ink", draft: "bg-line-soft text-muted", rejected: "bg-danger-tint text-danger-ink",
  replaced: "bg-line-soft text-muted", ended: "bg-line-soft text-muted", superseded: "bg-line-soft text-muted",
};
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const past = (iso: string | null | undefined) => !!iso && new Date(iso).getTime() <= Date.now();
const today = () => new Date().toISOString().slice(0, 10);

function Pill({ v, all }: { v: Rule; all?: Rule[] }) {
  const s = versionState(v, all);
  return <span className={`rounded-lg px-2 py-1 text-xs font-bold ${STATUS_STYLE[s.key] ?? "bg-line-soft"}`}>{s.label}</span>;
}

/** The short form for a row: "20% (tier B)", "15%", "$1.00 per order"; otherwise the full sentence. */
function short(r: Rule): string {
  const p = r.params as Record<string, unknown>;
  const { cur } = unitsFor(r.market_scope === "*" ? "IN" : r.market_scope);
  if (r.template === "percent") return `${Number(p.percent)}%`;
  if (r.template === "percent_by_tier") {
    const tiers = p.tiers as Record<string, unknown>;
    return `${Number(tiers[String(p.default_tier)])}% (tier ${String(p.default_tier)})`;
  }
  if (r.template === "flat_per_order") return `${cur}${Number(p.amount).toFixed(2)} per order`;
  return describe(r.template, r.params, r.market_scope);
}

function useNames() {
  const markets = useMarkets();
  return useMemo(() => {
    const names: Record<string, string> = { "*": "everywhere" };
    for (const c of markets.data ?? []) {
      names[c.code] = c.name;
      for (const s of c.regions) {
        names[s.code] = s.name;
        for (const ci of s.cities) names[ci.code] = ci.name;
      }
    }
    return names;
  }, [markets.data]);
}

function useKitchens(scope: string) {
  const markets = useMarkets();
  const cities = (markets.data ?? []).flatMap((c) => c.regions.flatMap((s) => s.cities))
    .filter((ci) => scope === "*" || ci.code.startsWith(scope) || scope.startsWith(ci.code));
  return useQuery({
    queryKey: ["kitchen-refs", cities.map((c) => c.code).join(",")],
    queryFn: async (): Promise<KitchenRef[]> => (await Promise.all(cities.map(async (c) =>
      (await adminApi.get<{ items: KitchenRef[] }>("/user/restaurants", { params: { city: c.name, limit: 100 } })).data.items
        .map((k) => ({ ...k, cityCode: c.code }))))).flat(),
    enabled: cities.length > 0,
  });
}

/** "Inherited from United States · 20% (tier B)" / "Set for Boise · 15%" / "Set for Spice Route Kitchen · 12% until 14 Feb 2027". */
function source(r: Rule, scope: string, names: Record<string, string>, kitchens: Record<string, string>): string {
  const who = r.scope_level === "restaurant" ? kitchens[r.scope_id] ?? "a restaurant" : names[r.market_scope] ?? r.market_scope;
  const inherited = r.scope_level !== "restaurant" && r.market_scope !== scope && scope !== "*" && r.market_scope.length < scope.length;
  const until = r.effective_to && !past(r.effective_to) ? ` until ${day(r.effective_to)}` : "";
  return `${inherited ? "Inherited from" : "Set for"} ${who} · ${short(r)}${until}`;
}

function Params({ rule }: { rule: Rule }) {
  return <p className="rounded-xl bg-porcelain p-4 text-[15px] leading-relaxed" data-testid="rule-words">{describe(rule.template, rule.params, rule.market_scope)}</p>;
}

const STARTERS: Record<string, Record<string, unknown>> = {
  percent: { percent: 15 },
  percent_by_tier: { tiers: { A: 25, B: 20, C: 15 }, default_tier: "B" },
  flat_per_order: { amount: 1 },
};
const TEMPLATE_WORDS: Record<string, string> = { percent: "Percent of food", percent_by_tier: "Percent by tier", flat_per_order: "Flat per order" };
const LEVEL_WORDS: Record<string, string> = { platform: "Everywhere", country: "Country", region: "State", city: "City", zone: "Zone", restaurant: "A restaurant" };

function AddRule({ family, scope, templates, rules, kitchens, names, onDone }: {
  family: string; scope: string; templates: Template[]; rules: Rule[]; kitchens: KitchenRef[];
  names: Record<string, string>; onDone: (id: string) => void;
}) {
  const { country, city } = parseScope(scope);
  const mine = templates.filter((t) => t.family === family && t.template !== "payout_schedule");
  const [template, setTemplate] = useState(mine[0]?.template ?? "");
  const t = mine.find((x) => x.template === template);
  const levels = (t?.allowed_levels ?? []).filter((l) => (l === "country" && country) || (l === "city" && city) || l === "restaurant");
  const [level, setLevel] = useState<string>(city && levels.includes("city") ? "city" : levels[0] ?? "");
  const [kitchenQ, setKitchenQ] = useState("");
  const [kitchen, setKitchen] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [from, setFrom] = useState(today());
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const starter = STARTERS[template] ?? rules.find((r) => r.template === template)?.params ?? {};
  const matches = kitchens.filter((k) => !kitchenQ || k.name.toLowerCase().includes(kitchenQ.toLowerCase())).slice(0, 8);
  const scopeId = level === "country" ? country : level === "city" ? city : kitchen;
  async function create(params: Record<string, unknown>) {
    if (!scopeId) return setErr(level === "restaurant" ? "Pick the restaurant." : "Pick a country or city in the scope bar first.");
    if (!from) return setErr("A start date is needed.");
    setBusy(true);
    setErr(null);
    try {
      const r = (await adminApi.post<Rule>("/user/rules", {
        family, template, params, scope_level: level, scope_id: scopeId, name: name || null,
        effective_from: new Date(`${from}T00:00:00`).toISOString(), effective_to: to ? new Date(`${to}T00:00:00`).toISOString() : null,
      })).data;
      onDone(r.id);
    } catch (e) {
      setErr(apiMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="space-y-4 rounded-2xl bg-white p-6" aria-label="Add a rule">
      <h2 className="m-0 font-display text-2xl font-semibold">Add a rule · {FAMILIES.find((f) => f.key === family)?.label}</h2>
      <div className="flex flex-wrap items-end gap-3 text-sm">
        <label className="font-bold">Type
          <select aria-label="Type" value={template} onChange={(e) => setTemplate(e.target.value)} className="mt-1 block h-10 rounded-lg border border-line px-2 font-normal">
            {mine.map((m) => <option key={m.template} value={m.template}>{TEMPLATE_WORDS[m.template] ?? m.template.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        <label className="font-bold">For
          <select aria-label="For" value={level} onChange={(e) => setLevel(e.target.value)} className="mt-1 block h-10 rounded-lg border border-line px-2 font-normal">
            {levels.map((l) => <option key={l} value={l}>{l === "country" ? names[country ?? ""] ?? "Country" : l === "city" ? names[city ?? ""] ?? "City" : LEVEL_WORDS[l]}</option>)}
          </select>
        </label>
        <label className="font-bold">Name (optional)
          <input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Launch deal" className="mt-1 block h-10 w-56 rounded-lg border border-line px-2 font-normal" />
        </label>
        <label className="font-bold">Starts
          <input aria-label="Starts" type="date" required value={from} onChange={(e) => setFrom(e.target.value)} className="mt-1 block h-10 rounded-lg border border-line px-2 font-normal" />
        </label>
        <label className="font-bold">Ends (optional)
          <input aria-label="Ends" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="mt-1 block h-10 rounded-lg border border-line px-2 font-normal" />
        </label>
      </div>
      {level === "restaurant" ? (
        <div className="space-y-2 text-sm">
          <input aria-label="Find a restaurant" placeholder="Find a restaurant in this scope" value={kitchenQ} onChange={(e) => { setKitchenQ(e.target.value); setKitchen(null); }}
            className="h-10 w-80 rounded-full border border-line-strong px-4" />
          <div className="flex flex-wrap gap-2">
            {matches.map((k) => (
              <button key={k.id} type="button" onClick={() => { setKitchen(k.id); setKitchenQ(k.name); }} aria-pressed={kitchen === k.id}
                className={`h-9 rounded-full px-3 font-bold ${kitchen === k.id ? "bg-kohl text-white" : "border border-line-strong"}`}>{k.name} · {names[k.cityCode] ?? k.cityCode}</button>
            ))}
          </div>
        </div>
      ) : null}
      {template ? <RuleEditor key={template} params={starter as Record<string, unknown>} busy={busy} onCancel={() => onDone("")} onSave={(p) => void create(p)} saveLabel="Create draft" /> : null}
      {err ? <p role="alert" className="text-sm font-semibold text-chili">{err}</p> : null}
      <p className="text-xs text-muted">A new rule starts as a draft. {t?.money ? "Submitting sends it to a second admin to approve." : "Submitting makes it live."}</p>
    </section>
  );
}

function PreviewBox({ rule }: { rule: Rule }) {
  const { cur } = unitsFor(rule.market_scope);
  const p = useQuery({ queryKey: ["commission-preview", rule.id, JSON.stringify(rule.params)], queryFn: async () => (await adminApi.get<Preview>(`/user/rules/commission/preview/${rule.id}`)).data });
  if (!p.data) return <p className="text-sm text-muted">Working out the last 7 days…</p>;
  const diff = Number(p.data.payout_difference);
  const m = (v: string | number) => `${cur}${Number(v).toFixed(2)}`;
  const signed = (v: number) => `${v >= 0 ? "+" : "−"}${m(Math.abs(v))}`;
  return (
    <section className="space-y-2 rounded-xl border border-line p-4 text-sm" aria-label="Preview: the last 7 days">
      <h3 className="m-0 text-sm font-extrabold">Preview: the last {p.data.days} days with this draft</h3>
      {p.data.orders === 0 ? <p className="text-muted" data-testid="preview-summary">No delivered orders in this scope in the last {p.data.days} days.</p> : (
        <>
          <p data-testid="preview-summary">{p.data.orders} orders · commission {m(p.data.commission_now)} → {m(p.data.commission_new)} · restaurant payouts{" "}
            <b className={diff >= 0 ? "text-peacock-dark" : "text-chili"}>{signed(diff)}</b></p>
          <table className="w-full text-left"><thead className="text-[12px] uppercase text-muted"><tr><th>Restaurant</th><th>Orders</th><th>Commission now</th><th>With this draft</th><th>Payout change</th></tr></thead>
            <tbody>{p.data.restaurants.map((x) => <tr key={x.name}><td>{x.name}</td><td>{x.orders}</td><td>{m(x.commission_now)}</td><td>{m(x.commission_new)}</td><td>{signed(Number(x.payout_difference))}</td></tr>)}</tbody></table>
        </>
      )}
    </section>
  );
}

function RuleDetail({ rule, label, onChanged }: { rule: Rule; label: string; onChanged: (id?: string) => void }) {
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const history = useQuery({ queryKey: ["rule-history", rule.id], queryFn: async () => (await adminApi.get<History>(`/user/rules/${rule.id}/history`)).data });
  const [editing, setEditing] = useState<"version" | "draft" | null>(null);
  const [note, setNote] = useState("");
  const [endAt, setEndAt] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const where = rule.market_scope;
  const versions = history.data?.versions ?? [];
  const state = versionState(rule, versions);
  async function run(fn: () => Promise<unknown>, ok: string, next?: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      setEditing(null);
      await qc.invalidateQueries({ queryKey: ["rules"] });
      await qc.invalidateQueries({ queryKey: ["rule-history"] });
      onChanged(next);
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  const money = rule.money ?? rule.family !== "business";
  async function newVersion(params: Record<string, unknown>) {
    await run(async () => {
      const v = (await adminApi.post<Rule>(`/user/rules/${rule.id}/versions`, { params })).data;
      await adminApi.post(`/user/rules/${v.id}/submit`);
    }, money ? "Sent for approval: a second admin approves it." : "Saved and live.");
  }
  const isDraft = rule.status === "draft" || rule.status === "rejected";
  const isLive = state.key === "live" || state.key === "paused" || state.key === "scheduled";
  const mayEdit = can(me, "rules.edit", where);
  const kitchenOffer = rule.family === "promotion" && rule.scope_level === "restaurant" && rule.params.funded_by === "restaurant" && (state.key === "live" || state.key === "paused");
  const mayPause = kitchenOffer && (can(me, "partners.edit", where) || can(me, "rules.approve", where));
  const mineToApprove = rule.status === "pending_approval" && can(me, "rules.approve", where) && rule.created_by !== me?.user_id;
  return (
    <section className="space-y-4 rounded-2xl bg-white p-6" aria-label={`Rule · ${rule.name ?? rule.template}`}>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="m-0 font-display text-2xl font-semibold">{rule.name ?? rule.template.replace(/_/g, " ")}</h2>
        <Pill v={rule} all={versions} /> <span className="text-sm text-muted" data-testid="rule-source">{label} · v{rule.version}</span>
      </div>
      {editing === "version" ? (
        <RuleEditor params={rule.params} busy={busy} onCancel={() => setEditing(null)} onSave={(p) => void newVersion(p)} saveLabel={money ? "Send for approval" : "Save"} />
      ) : editing === "draft" ? (
        <RuleEditor params={rule.params} busy={busy} onCancel={() => setEditing(null)}
          onSave={(p) => void run(() => adminApi.patch(`/user/rules/${rule.id}`, { params: p }), "Draft saved.", rule.id)} saveLabel="Save draft" />
      ) : <Params rule={rule} />}
      {isDraft && rule.family === "commission" && rule.template !== "payout_schedule" ? <PreviewBox rule={rule} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        {isDraft && mayEdit && !editing ? (
          <>
            <button type="button" onClick={() => setEditing("draft")} className="h-10 rounded-full border border-line-strong px-4 font-bold">Edit draft</button>
            <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/${rule.id}/submit`), money ? "Sent for approval." : "Published.", rule.id)}
              className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">{money ? "Submit for approval" : "Publish"}</button>
            <button type="button" disabled={busy} onClick={() => void run(() => adminApi.delete(`/user/rules/${rule.id}`), "Draft deleted.")}
              className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili">Delete draft</button>
          </>
        ) : null}
        {isLive && mayEdit && !editing ? (
          <>
            <button type="button" onClick={() => setEditing("version")} className="h-10 rounded-full border border-line-strong px-4 font-bold">New version</button>
            <input aria-label="End on" type="date" value={endAt} min={today()} onChange={(e) => setEndAt(e.target.value)} className="h-10 rounded-full border border-line px-3 text-sm" />
            <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/${rule.id}/end`, endAt ? { at: new Date(`${endAt}T00:00:00`).toISOString() } : {}),
              endAt ? `Ends on ${day(new Date(`${endAt}T00:00:00`).toISOString())}; then the inherited rule applies.` : "Ended now; the inherited rule applies.", rule.id)}
              className="h-10 rounded-full border border-line-strong px-4 font-bold">{endAt ? "End on that date" : "End now"}</button>
          </>
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
        <Link href={`/pricing/simulator?city=${where.split("-").length === 3 ? where : "IN-TG-HYD"}`} className="ml-auto text-sm font-bold text-peacock">Try it in the price simulator →</Link>
      </div>
      {kitchenOffer ? (
        <section className="space-y-2 rounded-xl border border-line p-4" aria-label="The kitchen's own offer">
          <p className="text-sm">The kitchen pays for this offer, so it went live without approval.{rule.paused_at ? <> <b>Paused {ago(rule.paused_at)}:</b> {rule.paused_reason}</> : null}</p>
          {mayPause && !rule.paused_at ? (
            <div className="flex flex-wrap gap-2">
              <input aria-label="Why pause it (the kitchen sees this)" placeholder="Why pause it? The kitchen sees this" value={reason} maxLength={300}
                onChange={(e) => setReason(e.target.value)} className="h-10 flex-1 rounded-full border border-line px-4 text-sm" />
              <button type="button" disabled={busy || reason.trim().length < 3}
                onClick={() => void run(() => adminApi.post(`/user/rules/${rule.id}/pause`, { reason: reason.trim() }), "Paused. Customers stop seeing it now; the kitchen sees why.", rule.id)}
                className="h-10 rounded-full border border-line-strong px-4 font-bold text-chili disabled:opacity-40">Pause offer</button>
            </div>
          ) : null}
          {mayPause && rule.paused_at ? (
            <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/${rule.id}/resume`), "Resumed. Customers see it again.", rule.id)}
              className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">Resume offer</button>
          ) : null}
        </section>
      ) : null}
      {msg ? <p role="status" className={`text-sm font-semibold ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
      <div>
        <h3 className="mb-2 text-sm font-extrabold">History</h3>
        <ul className="space-y-1 text-sm" aria-label="Versions">
          {versions.slice().reverse().map((v) => {
            const s = versionState(v, versions);
            const canRollBack = mayEdit && v.id !== rule.id && (s.key === "replaced" || s.key === "ended" || v.status === "superseded")
              && !versions.some((o) => ["draft", "pending_approval"].includes(o.status));
            return (
              <li key={v.id} className="flex flex-wrap items-center gap-2"><b>v{v.version}</b> <Pill v={v} all={versions} /> <span className="text-muted">{describe(v.template, v.params, v.market_scope)} · {ago(v.created_at)}
                {(history.data?.approvals[v.id] ?? []).filter((a) => a.decision).map((a) => ` · ${a.decision}${a.note ? ` (“${a.note}”)` : ""}`).join("")}</span>
                {canRollBack ? <button type="button" disabled={busy} onClick={() => void run(() => adminApi.post(`/user/rules/${v.id}/rollback`), money ? `Rolling back to v${v.version}: a second admin approves it.` : `Rolled back to v${v.version}.`)}
                  className="h-8 rounded-full border border-line-strong px-3 text-xs font-bold">Roll back to v{v.version}</button> : null}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function PricingPage() {
  const scope = useScope();
  const params = useSearchParams();
  const router = useRouter();
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const tab = params.get("tab") ?? "delivery_fee";
  const { country, region, city } = parseScope(scope);
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const names = useNames();
  const kitchenList = useKitchens(scope);
  const kitchens = useMemo(() => Object.fromEntries((kitchenList.data ?? []).map((k) => [k.id, k.name])), [kitchenList.data]);
  const catalogue = useQuery({ queryKey: ["rule-templates"], queryFn: async () => (await adminApi.get<Template[]>("/user/rules/templates")).data });
  const approvals = useQuery({ queryKey: ["rules", "approvals"], queryFn: async () => (await adminApi.get<Rule[]>("/user/rules/approvals")).data, retry: false });
  const rules = useQuery({
    queryKey: ["rules", tab, scope],
    queryFn: async () => (await adminApi.get<Rule[]>("/user/rules", { params: { family: tab } })).data,
    enabled: tab !== "approvals",
  });
  const relevant = (tab === "approvals" ? approvals.data ?? [] : rules.data ?? [])
    .filter((r) => scope === "*" || r.market_scope === "*" || r.market_scope.startsWith(scope) || scope.startsWith(r.market_scope));
  const rank = (r: Rule) => ({ live: 0, paused: 0, scheduled: 1, pending_approval: 1, draft: 2, rejected: 2 } as Record<string, number>)[versionState(r).key] ?? 3;
  relevant.sort((a, b) => rank(a) - rank(b));
  const selected = relevant.find((r) => r.id === open) ?? null;
  const mayAdd = tab !== "approvals" && !!country && can(me, "rules.edit", city ?? country);
  const go = (t: string) => {
    setOpen(null);
    setAdding(false);
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
      <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
        <section className="rounded-2xl bg-white p-2" aria-label="Rules">
          {mayAdd ? (
            <button type="button" onClick={() => { setAdding(true); setOpen(null); }} className="m-1 h-10 rounded-full bg-kohl px-4 text-sm font-extrabold text-white">Add</button>
          ) : tab !== "approvals" && !country ? <p className="px-3 py-2 text-xs text-muted">Pick a country or city to add a rule.</p> : null}
          {relevant.length === 0 ? <p className="p-4 text-sm text-muted">{tab === "approvals" ? "Nothing waiting for you." : "No rules here."}</p> : null}
          {relevant.map((r) => (
            <button key={r.id} type="button" onClick={() => { setOpen(r.id); setAdding(false); }}
              className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${open === r.id ? "bg-peacock-tint" : "hover:bg-porcelain"}`}>
              <div className="flex items-center justify-between gap-2"><b>{r.name ?? r.template.replace(/_/g, " ")}</b><Pill v={r} /></div>
              <div className="text-[13px]" data-testid="row-source">{source(r, scope, names, kitchens)}</div>
            </button>
          ))}
        </section>
        {adding ? (
          <AddRule family={tab} scope={scope} templates={catalogue.data ?? []} rules={rules.data ?? []} kitchens={kitchenList.data ?? []}
            names={names} onDone={(id) => void qc.invalidateQueries({ queryKey: ["rules"] }).then(() => { setAdding(false); setOpen(id || null); })} />
        ) : selected ? (
          <RuleDetail key={selected.id} rule={selected} label={source(selected, scope, names, kitchens)}
            onChanged={(id) => void qc.invalidateQueries({ queryKey: ["rules"] }).then(() => setOpen(id ?? null))} />
        ) : <div className="rounded-2xl bg-white p-6 text-muted">Pick a rule to see its settings, history and approvals.</div>}
      </div>
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><PricingPage /></Suspense>;
}
