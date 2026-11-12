"use client";
// Report a problem on the web (B5): which items, what went wrong, a photo if
// you like. Up to the city's limit it's refunded at once; above it, support
// looks at it and gets back to you.
import { errorMessage, unwrap, type CoreSchemas } from "@bhojango/api-client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api, urls, useHydrated, useSession } from "@/lib/client";
import { Button } from "@bhojango/ui";

type Order = CoreSchemas["OrderResponse"];
type Outcome = CoreSchemas["ProblemOut"];
const REASONS = [
  { key: "missing_item", label: "Missing" },
  { key: "wrong_item", label: "Wrong item" },
  { key: "quality", label: "Not good" },
  { key: "damaged_in_transit", label: "Spilled or damaged" },
  { key: "late", label: "Very late" },
] as const;
type Reason = (typeof REASONS)[number]["key"];

async function uploadPhoto(file: File, token: string | null): Promise<string> {
  const form = new FormData();
  form.append("purpose", "problem_photo");
  form.append("file", file);
  const res = await fetch(`${urls.core}/api/v1/uploads`, { method: "POST", headers: token ? { authorization: `Bearer ${token}` } : {}, body: form });
  const body = (await res.json().catch(() => null)) as { key?: string } | null;
  if (!res.ok || !body?.key) throw new Error("The photo didn't upload. Try again, or send without it.");
  return body.key;
}

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const ready = useHydrated();
  const user = useSession((s) => s.user);
  const token = useSession((s) => s.access);
  const [order, setOrder] = useState<Order | null>(null);
  const [pick, setPick] = useState<Record<string, number>>({});
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Outcome | null>(null);

  useEffect(() => {
    if (!ready || !user) return;
    let live = true;
    api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
      .then((r) => live && setOrder(unwrap(r))).catch(() => live && setError("We couldn't find this order."));
    return () => {
      live = false;
    };
  }, [id, ready, user]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      const photo_key = photo ? await uploadPhoto(photo, token) : null;
      const items = Object.entries(pick).filter(([, n]) => n > 0).map(([menu_item_id, quantity]) => ({ menu_item_id, quantity }));
      setDone(unwrap(await api.core.POST("/api/v1/orders/{order_id}/problems", {
        params: { path: { order_id: id } }, body: { items, reason, note: note.trim() || null, photo_key } })));
    } catch (err) {
      setError(err instanceof Error && !("body" in err) ? err.message : errorMessage((err as { body?: unknown }).body, "Couldn't send your report. Try again."));
    } finally {
      setBusy(false);
    }
  }

  if (ready && !user) return <div className="mx-auto max-w-md px-5 py-20 text-center"><Link href={`/sign-in?next=/orders/${id}/report`} className="font-bold text-peacock">Sign in to report a problem</Link></div>;
  if (done) {
    return (
      <section aria-label="Report sent" className="mx-auto max-w-xl space-y-4 px-5 py-14">
        <h1 className="font-display text-4xl font-semibold">{done.outcome === "refunded" ? "Refunded" : "Sent to support"}</h1>
        <p className="text-lg">{done.message}</p>
        {done.outcome === "ticket" ? <p className="text-muted">Refunds above {done.currency === "INR" ? "₹" : "$"}{Number(done.limit).toFixed(0)} on one order are checked by a person first.</p> : null}
        <Link href={`/orders/${id}`} className="inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white">Back to your order</Link>
      </section>
    );
  }
  const items = (order?.items ?? []) as { menu_item_id: string; name: string; quantity: number }[];
  const chosen = Object.values(pick).some((n) => n > 0);
  return (
    <form onSubmit={send} aria-label="Report a problem" className="mx-auto max-w-2xl space-y-5 px-5 py-10">
      <div>
        <Link href={`/orders/${id}`} className="text-sm font-bold text-peacock">← Your order</Link>
        <h1 className="mt-2 font-display text-4xl font-semibold">Report a problem</h1>
        <p className="text-muted">{order?.restaurant_name}</p>
      </div>
      <fieldset className="space-y-2 rounded-card bg-white p-5">
        <legend className="mb-2 font-extrabold">Which items?</legend>
        {items.map((i) => (
          <label key={i.menu_item_id} className="flex items-center gap-3">
            <span className="flex-1 font-semibold">{i.name} <span className="font-normal text-muted">· {i.quantity} ordered</span></span>
            <input type="number" min={0} max={i.quantity} value={pick[i.menu_item_id] ?? 0} aria-label={`How many ${i.name}`}
              onChange={(e) => setPick((p) => ({ ...p, [i.menu_item_id]: Math.max(0, Math.min(i.quantity, Number(e.target.value))) }))}
              className="h-11 w-20 rounded-card border-[1.5px] border-line-strong px-3" />
          </label>
        ))}
      </fieldset>
      <fieldset className="space-y-3 rounded-card bg-white p-5">
        <legend className="mb-2 font-extrabold">What went wrong?</legend>
        <div className="flex flex-wrap gap-2">
          {REASONS.map((r) => (
            <label key={r.key} className={`flex h-11 cursor-pointer items-center rounded-pill border-[1.5px] px-4 font-semibold ${reason === r.key ? "border-peacock bg-peacock-mist" : "border-line"}`}>
              <input type="radio" name="reason" value={r.key} checked={reason === r.key} onChange={() => setReason(r.key)} className="sr-only" />{r.label}
            </label>
          ))}
        </div>
        <label className="block text-sm font-bold">Tell us more (optional)
          <input value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} className="mt-1 block h-12 w-full rounded-card border-[1.5px] border-line-strong px-3 font-normal" />
        </label>
        <label className="block text-sm font-bold">A photo helps (optional)
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm font-normal" />
        </label>
      </fieldset>
      {error ? <p role="alert" className="font-semibold text-chili">{error}</p> : null}
      <Button type="submit" size="lg" loading={busy} disabled={!chosen || !reason}>Send report</Button>
    </form>
  );
}
