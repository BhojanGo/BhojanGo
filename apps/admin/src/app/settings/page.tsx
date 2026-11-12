"use client";
// Settings: who can do what, where. Your own access, the admins in your
// scopes, and granting or removing a role (super admins any; country managers
// city ops, support, finance and viewer inside their country).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useState } from "react";

import { ConsoleShell, parseScope } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { can, ROLE_LABELS, useAdminMe } from "@/lib/markets";
import { apiMessage, useScope } from "@/lib/ops";

interface Assignment { id: string; user_id: string; role: string; scope: string; email: string | null; full_name: string | null; created_at: string }

function SettingsPage() {
  const scope = useScope();
  const { country, region, city } = parseScope(scope);
  const { data: me } = useAdminMe();
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["assignments", scope],
    queryFn: async () => (await adminApi.get<Assignment[]>("/user/admin/role-assignments", { params: scope === "*" ? {} : { scope } })).data,
  });
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("support_agent");
  const [where, setWhere] = useState(scope === "*" ? "" : scope);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string) {
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      await qc.invalidateQueries({ queryKey: ["assignments"] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    }
  }
  const mayGrant = (me?.permissions["admins.grant"] ?? []).length > 0;
  return (
    <ConsoleShell section="Settings" country={country} region={region} city={city} scopeHref={(s) => `/settings?scope=${s}`}>
      <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">Settings</h1>
      <section className="rounded-2xl bg-white p-6" aria-label="Your access">
        <h2 className="m-0 mb-2 text-lg font-extrabold">Your access</h2>
        <ul className="space-y-1 text-sm">
          {(me?.assignments ?? []).map((a) => <li key={a.id}><b>{ROLE_LABELS[a.role] ?? a.role}</b> · {a.scope === "*" ? "everywhere" : a.scope}</li>)}
        </ul>
        <p className="mt-2 text-sm text-muted">Country, state and city settings (money, tax, service hours, languages) are in Markets; states inherit from the country and cities from their state.</p>
      </section>
      <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Admins">
        <h2 className="m-0 text-lg font-extrabold">Admins {scope !== "*" ? `in ${scope}` : ""}</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-[12px] uppercase tracking-wide text-muted"><tr><th className="py-2">Admin</th><th>Role</th><th>Where</th><th /></tr></thead>
          <tbody className="divide-y divide-line">
            {(list.data ?? []).map((a) => (
              <tr key={a.id}><td className="py-2.5"><b>{a.full_name ?? "—"}</b> <span className="text-muted">{a.email}</span></td><td>{ROLE_LABELS[a.role] ?? a.role}</td>
                <td>{a.scope === "*" ? "Everywhere" : a.scope}</td>
                <td className="text-right">{mayGrant && a.user_id !== me?.user_id && can(me, "admins.grant", a.scope === "*" ? "*" : a.scope) ? (
                  <button type="button" onClick={() => void act(() => adminApi.delete(`/user/admin/role-assignments/${a.id}`), "Removed.")} className="h-8 rounded-full border border-line-strong px-3 text-xs font-bold text-chili">Remove</button>
                ) : null}</td></tr>
            ))}
          </tbody>
        </table>
        {mayGrant ? (
          <form className="flex flex-wrap items-end gap-2 border-t border-line pt-3" onSubmit={(e) => {
            e.preventDefault();
            void act(() => adminApi.post("/user/admin/role-assignments", { email, role, scope: where || "*" }), `Granted ${ROLE_LABELS[role]} to ${email}.`);
          }}>
            <label className="text-sm font-bold">Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 block h-10 w-64 rounded-lg border border-line px-2 font-normal" /></label>
            <label className="text-sm font-bold">Role<select value={role} onChange={(e) => setRole(e.target.value)} className="mt-1 block h-10 rounded-lg border border-line px-2 font-normal">
              {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <label className="text-sm font-bold">Where<input placeholder="IN, IN-TG or IN-TG-HYD" value={where} onChange={(e) => setWhere(e.target.value.toUpperCase())} className="mt-1 block h-10 w-44 rounded-lg border border-line px-2 font-normal" /></label>
            <button type="submit" className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">Grant</button>
          </form>
        ) : <p className="text-sm text-muted">Granting roles needs a country manager or super admin.</p>}
        {msg ? <p role="status" className={`text-sm font-semibold ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
      </section>
    </ConsoleShell>
  );
}

export default function Page() {
  return <Suspense><SettingsPage /></Suspense>;
}
