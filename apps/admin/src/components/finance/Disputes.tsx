"use client";
// R39: chargebacks (Stripe charge.dispute.*). Open ones hold the restaurant's share from its next payout;
// finance adds evidence (files and a note) and sends it to the payment provider once. Won: the hold comes
// back; lost: the restaurant bears the food for a food-quality reason, BhojanGo bears everything else.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { adminApi } from "@/lib/api";
import { can, useAdminMe } from "@/lib/markets";
import { apiMessage, money } from "@/lib/ops";

export interface Dispute {
  id: string; provider: string; provider_dispute_id: string; order_id: string | null; order_code: string | null;
  restaurant: string | null; city: string | null; currency: string; amount: number; reason: string; status: string;
  outcome: "won" | "lost" | null; held: number; hold_applied: boolean; settled: boolean; next_payout: number;
  loss_bearer: "restaurant" | "platform" | null; restaurant_loss: number; platform_loss: number;
  evidence: { n: number; name?: string | null; content_type?: string | null; size?: number | null; note?: string | null; uploaded_at?: string | null }[];
  evidence_submitted_at: string | null; evidence_due_by: string | null; opened_at: string | null; closed_at: string | null;
}

const REASONS: Record<string, string> = {
  fraudulent: "Fraud (card not authorised)", product_unacceptable: "Food not as described / quality", product_not_received: "Order not received",
  duplicate: "Charged twice", credit_not_processed: "Refund not received", general: "Other", unrecognized: "Charge not recognised",
};

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—");

/** One line a finance admin reads: where the money stands. */
export function disputeState(d: Dispute): string {
  const m = (minor: number) => money(minor / 100, d.currency, 2);
  if (d.outcome === "won") return d.hold_applied && !d.settled ? `Won: ${m(d.held)} goes back on the next payout` : "Won: nothing lost";
  if (d.outcome === "lost") {
    return d.loss_bearer === "restaurant"
      ? `Lost: the restaurant bears ${m(d.restaurant_loss)} (food), BhojanGo ${m(d.platform_loss)}`
      : `Lost: BhojanGo bears ${m(d.platform_loss)}`;
  }
  if (d.evidence_submitted_at) return `Evidence sent: waiting for the bank. ${m(d.held)} held`;
  return d.hold_applied ? `Open: ${m(d.held)} held from the restaurant's payout` : `Open: ${m(d.held)} will be held from the next payout`;
}

export function Disputes({ country }: { country: string }) {
  const qc = useQueryClient();
  const { data: me } = useAdminMe();
  const list = useQuery({
    queryKey: ["disputes", country], enabled: Boolean(country),
    queryFn: async () => (await adminApi.get<Dispute[]>("/user/finance/disputes", { params: { country } })).data,
  });
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const mayEdit = can(me, "finance.edit", country);
  const d = list.data?.find((x) => x.id === open) ?? null;

  async function act(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      await qc.invalidateQueries({ queryKey: ["disputes", country] });
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  async function view(n: number) {
    const r = await adminApi.get<Blob>(`/user/finance/disputes/${open}/evidence/${n}`, { responseType: "blob" });
    window.open(URL.createObjectURL(r.data), "_blank", "noopener");
  }
  if (!list.data?.length) return null;
  const openCount = list.data.filter((x) => !x.outcome).length;
  return (
    <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Chargebacks" data-testid="disputes">
      <div>
        <h2 className="m-0 text-h3">Chargebacks · {openCount} open</h2>
        <p className="m-0 mt-1 text-small text-muted">A customer&apos;s bank disputed these payments. While one is open, the restaurant&apos;s share of the order is held from its next payout. Add evidence and send it before the due date. If the bank sides with the customer, the restaurant bears the food when the reason is the food&apos;s quality; BhojanGo bears the rest, and all of it for fraud.</p>
      </div>
      <div className="table-scroll"><table className="table-stack w-full text-left text-small tabular-nums [&_td]:pr-3 [&_th]:pr-3">
        <thead className="text-caption text-muted"><tr><th className="py-2">Order</th><th>Restaurant</th><th>Disputed</th><th>Reason</th><th>Where it stands</th><th>Evidence due</th><th><span className="sr-only">Open</span></th></tr></thead>
        <tbody className="divide-y divide-line">
          {list.data.map((x) => (
            <tr key={x.id} data-testid="dispute-row" className={open === x.id ? "bg-peacock-tint" : undefined}>
              <td className="stack-title py-2.5 font-semibold">#{x.order_code ?? "—"}</td>
              <td data-label="Restaurant">{x.restaurant ?? "—"}</td>
              <td data-label="Disputed" className="font-semibold">{money(x.amount / 100, x.currency, 2)}</td>
              <td data-label="Reason">{REASONS[x.reason] ?? x.reason.replace(/_/g, " ")}</td>
              <td data-label="Where it stands" data-testid="dispute-state" className={x.outcome === "lost" ? "text-chili" : x.outcome === "won" ? "text-peacock" : ""}>{disputeState(x)}</td>
              <td data-label="Evidence due">{x.outcome ? "—" : day(x.evidence_due_by)}</td>
              <td className="stack-actions text-right"><button type="button" onClick={() => { setOpen(open === x.id ? null : x.id); setMsg(null); }}
                aria-expanded={open === x.id} className="h-9 rounded-full border border-line-strong px-3 text-label text-peacock">{open === x.id ? "Close" : "Evidence"}</button></td>
            </tr>
          ))}
        </tbody>
      </table></div>
      {d ? (
        <div className="space-y-3 rounded-xl bg-porcelain p-4 text-small" data-testid="dispute-evidence">
          <h3 className="m-0 text-label">Evidence for #{d.order_code} · {d.provider === "stripe" ? "Stripe" : d.provider} {d.provider_dispute_id}</h3>
          {d.evidence.length ? (
            <ul className="m-0 space-y-1 p-0">
              {d.evidence.map((e) => (
                <li key={e.n} className="list-none">{e.name ? <button type="button" className="font-bold text-peacock" onClick={() => void view(e.n)}>{e.name}</button> : null}
                  {e.note ? <span className="text-muted">{e.name ? " · " : ""}{e.note}</span> : null}</li>
              ))}
            </ul>
          ) : <p className="m-0 text-muted">No evidence yet. Useful: the receipt, the delivery photo, the chat with the customer, the restaurant&apos;s note.</p>}
          {d.evidence_submitted_at ? <p className="m-0 font-bold">Sent to the bank on {day(d.evidence_submitted_at)}.</p> : null}
          {mayEdit && !d.outcome && !d.evidence_submitted_at ? (
            <form className="space-y-2" onSubmit={(e) => {
              e.preventDefault();
              const body = new FormData();
              body.append("note", note);
              if (file) body.append("file", file);
              void act(async () => { await adminApi.post(`/user/finance/disputes/${d.id}/evidence`, body); setNote(""); setFile(null); }, "Evidence added.");
            }}>
              <textarea aria-label="Note for the bank" value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={4000}
                placeholder="What happened, in plain words (the bank reads this)" className="w-full rounded-xl border border-line bg-white p-3" />
              <input aria-label="Evidence file" type="file" accept="application/pdf,image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block text-small" />
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={busy || (!note.trim() && !file)} className="h-10 rounded-full border border-line-strong bg-white px-4 font-bold text-peacock disabled:opacity-40">Add evidence</button>
                <button type="button" disabled={busy || d.evidence.length === 0} onClick={() => void act(() => adminApi.post(`/user/finance/disputes/${d.id}/submit`), "Evidence sent to the bank.")}
                  className="h-10 rounded-full bg-peacock px-4 font-bold text-white disabled:opacity-40">Send evidence to the bank</button>
              </div>
            </form>
          ) : null}
        </div>
      ) : null}
      {msg ? <p role={msg.ok ? "status" : "alert"} className={`m-0 text-label ${msg.ok ? "text-peacock" : "text-chili"}`}>{msg.text}</p> : null}
    </section>
  );
}
