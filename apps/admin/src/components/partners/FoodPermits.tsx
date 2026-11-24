"use client";
// R39: US food permits waiting for review (new restaurants and renewals). A restaurant goes live only with an
// approved permit; an expired one pauses its listing until a renewed one is approved here.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { adminApi } from "@/lib/api";
import { apiMessage } from "@/lib/ops";

export interface Permit {
  restaurant_id: string; name: string; city: string; restaurant_status: string; number: string | null; expires_on: string | null;
  document_key: string | null; status: string | null; note: string | null; paused: boolean;
}

const day = (iso: string | null) => (iso ? new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—");

export function FoodPermits({ mayReview, openFile }: { mayReview: (p: Permit) => boolean; openFile: (key: string) => Promise<void> }) {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["food-permits"], queryFn: async () => (await adminApi.get<Permit[]>("/user/restaurants/admin/permits")).data });
  const [why, setWhy] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function review(p: Permit, decision: "approve" | "reject") {
    setMsg(null);
    try {
      await adminApi.post(`/user/restaurants/${p.restaurant_id}/food-permit/review`, { decision, note: why[p.restaurant_id] || null });
      setMsg({ ok: true, text: `${p.name}: permit ${decision === "approve" ? "approved" : "turned down"}.` });
      await qc.invalidateQueries({ queryKey: ["food-permits"] });
      await qc.invalidateQueries({ queryKey: ["application"] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    }
  }
  if (!list.data) return null;
  return (
    <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Food permits to review" data-testid="food-permits">
      <div>
        <h2 className="m-0 text-h3">Food permits to review · {list.data.length}</h2>
        <p className="m-0 mt-1 text-small text-muted">The health district&apos;s food establishment permit (Boise: Central District Health). Check the number and the expiry date against the photo. A restaurant goes live only with an approved permit; the owner is reminded 30 days before it expires, and an expired permit pauses the restaurant until a renewed one is approved here.</p>
      </div>
      {list.data.length === 0 ? <p className="m-0 text-small text-muted">Nothing waiting.</p> : (
        <div className="table-scroll"><table className="table-stack w-full text-left text-small tabular-nums [&_td]:pr-3 [&_th]:pr-3">
          <thead className="text-caption text-muted"><tr><th className="py-2">Restaurant</th><th>Permit</th><th>Expires</th><th>Permit file</th><th><span className="sr-only">Review</span></th></tr></thead>
          <tbody className="divide-y divide-line">
            {list.data.map((p) => (
              <tr key={p.restaurant_id} data-testid="permit-row">
                <td className="stack-title py-2.5"><b>{p.name}</b> <span className="text-muted">{p.city} · {p.restaurant_status === "active" ? (p.paused ? "paused: permit expired" : "live, renewal") : "applying"}</span></td>
                <td data-label="Permit" className="font-semibold">{p.number}</td>
                <td data-label="Expires">{day(p.expires_on)}</td>
                <td data-label="Permit file">{p.document_key ? <button type="button" className="font-bold text-peacock" onClick={() => void openFile(p.document_key!)}>View permit</button> : "—"}</td>
                <td className="stack-actions">{mayReview(p) ? (
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <button type="button" onClick={() => void review(p, "approve")} className="h-9 rounded-full bg-peacock px-3 font-bold text-white">Approve permit</button>
                    <input aria-label={`Why ${p.name}'s permit is turned down`} placeholder="Why (the restaurant sees it)" value={why[p.restaurant_id] ?? ""}
                      onChange={(e) => setWhy({ ...why, [p.restaurant_id]: e.target.value })} className="h-9 w-48 rounded-full border border-line px-3" />
                    <button type="button" disabled={(why[p.restaurant_id] ?? "").trim().length < 3} onClick={() => void review(p, "reject")}
                      className="h-9 rounded-full border border-line-strong px-3 font-bold text-chili disabled:opacity-40">Turn down</button>
                  </div>
                ) : null}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {msg ? <p role={msg.ok ? "status" : "alert"} className={`m-0 text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
    </section>
  );
}
