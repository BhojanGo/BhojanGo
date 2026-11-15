"use client";
// Report a problem: which items, what went wrong, a photo if you like. Up to
// the city's limit it's refunded at once; above it, support looks at it and
// gets back to you. (Same calls as before: POST /orders/{id}/problems, the
// photo via /uploads.)

import { errorMessage, unwrap, type CoreSchemas } from "@bhojango/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, urls, useSession } from "@/lib/client";
import { useFormat, useT } from "@/lib/i18n";

type Order = CoreSchemas["OrderResponse"];
type Outcome = CoreSchemas["ProblemOut"];
const REASONS = ["missing_item", "wrong_item", "quality", "damaged_in_transit", "late"] as const;
type Reason = (typeof REASONS)[number];

class PhotoError extends Error {}

async function uploadPhoto(file: File, token: string | null): Promise<string> {
  const form = new FormData();
  form.append("purpose", "problem_photo");
  form.append("file", file);
  const res = await fetch(`${urls.core}/api/v1/uploads`, { method: "POST", headers: token ? { authorization: `Bearer ${token}` } : {}, body: form });
  const body = (await res.json().catch(() => null)) as { key?: string } | null;
  if (!res.ok || !body?.key) throw new PhotoError();
  return body.key;
}

const field = "mt-1 block h-12 w-full rounded-xl border-[1.5px] border-[#C9D3D4] bg-white px-3 font-normal text-[#111418] focus:border-[#0B5D66] focus:outline-none";

export function ReportView({ id }: { id: string }) {
  const t = useT();
  const f = useFormat();
  const token = useSession((s) => s.access);
  const [order, setOrder] = useState<{ id: string; order: Order | null } | null>(null);
  const [pick, setPick] = useState<Record<string, number>>({});
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Outcome | null>(null);

  useEffect(() => {
    let live = true;
    api.core
      .GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })
      .then((r) => live && setOrder({ id, order: unwrap(r) }))
      .catch(() => live && setOrder({ id, order: null }));
    return () => {
      live = false;
    };
  }, [id]);

  const back = `/account/orders?order=${encodeURIComponent(id)}`;

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
      setError(err instanceof PhotoError ? t("account.report.photo_failed") : errorMessage((err as { body?: unknown }).body, t("account.report.send_failed")));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <section aria-labelledby="report-done" className="max-w-[640px] rounded-3xl border border-[#E2E7E8] p-6 md:p-7">
        <h1 id="report-done" className="text-h1 tracking-[-0.8px]">
          {done.outcome === "refunded" ? t("account.report.refunded") : t("account.report.ticket")}
        </h1>
        <p className="mt-3 text-body-lg">{done.message}</p>
        {done.outcome === "ticket" && <p className="mt-2 tabular-nums text-[#4C5A5E]">{t("account.report.ticket_note", { amount: f.money(done.limit, done.currency, { whole: true }) })}</p>}
        <Link href={back} className="mt-6 inline-flex h-12 items-center rounded-full bg-[#0B5D66] px-6 font-bold text-white hover:bg-[#083F46] hover:text-white">
          {t("account.report.back_to_order")}
        </Link>
      </section>
    );
  }

  const loaded = order?.id === id ? order : null;
  const items = (loaded?.order?.items ?? []) as { menu_item_id: string; name: string; quantity: number }[];
  const chosen = Object.values(pick).some((n) => n > 0);
  return (
    <form onSubmit={send} aria-labelledby="report-title" className="max-w-[640px] space-y-5">
      <div>
        <Link href={back} className="text-label">← {t("account.report.back")}</Link>
        <h1 id="report-title" className="mt-2 text-h1 tracking-[-0.8px]">{t("account.report.title")}</h1>
        {loaded?.order && <p className="text-[#4C5A5E]">{loaded.order.restaurant_name}</p>}
        {!loaded && <p role="status" className="text-[#4C5A5E]">{t("account.loading")}</p>}
        {loaded && !loaded.order && <p role="alert" className="text-[#4C5A5E]">{t("account.report.not_found")}</p>}
      </div>
      <fieldset className="space-y-3 rounded-3xl border border-[#E2E7E8] p-5 md:p-6">
        <legend className="px-1 text-h3">{t("account.report.which_items")}</legend>
        {items.map((i) => (
          <label key={i.menu_item_id} className="flex items-center gap-3">
            <span className="flex-1 font-semibold">
              {i.name} <span className="font-normal text-[#4C5A5E]">· {t("account.report.ordered", { count: i.quantity })}</span>
            </span>
            <input
              type="number"
              min={0}
              max={i.quantity}
              value={pick[i.menu_item_id] ?? 0}
              aria-label={t("account.report.how_many", { item: i.name })}
              onChange={(e) => setPick((p) => ({ ...p, [i.menu_item_id]: Math.max(0, Math.min(i.quantity, Number(e.target.value))) }))}
              className="h-11 w-20 rounded-xl border-[1.5px] border-[#C9D3D4] px-3 text-center tabular-nums focus:border-[#0B5D66] focus:outline-none"
            />
          </label>
        ))}
      </fieldset>
      <fieldset className="space-y-4 rounded-3xl border border-[#E2E7E8] p-5 md:p-6">
        <legend className="px-1 text-h3">{t("account.report.what_wrong")}</legend>
        <div className="flex flex-wrap gap-2">
          {REASONS.map((r) => (
            <label
              key={r}
              className={`flex h-11 cursor-pointer items-center rounded-full px-4 text-label focus-within:ring-2 focus-within:ring-[#0B5D66] ${
                reason === r ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"
              }`}
            >
              <input type="radio" name="reason" value={r} checked={reason === r} onChange={() => setReason(r)} className="sr-only" />
              {t(`account.report.reason_${r}`)}
            </label>
          ))}
        </div>
        <label className="block text-label">
          {t("account.report.more")}
          <input value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} className={field} />
        </label>
        <label className="block text-label">
          {t("account.report.photo")}
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} className="mt-1 block w-full text-small" />
        </label>
      </fieldset>
      {error && <p role="alert" className="font-semibold text-[#8C1D18]">{error}</p>}
      <button
        type="submit"
        disabled={busy || !chosen || !reason}
        className="flex h-[52px] w-full items-center justify-center rounded-full bg-[#0B5D66] px-7 font-bold text-white hover:bg-[#083F46] disabled:opacity-50 md:w-auto"
      >
        {busy ? t("account.report.sending") : t("account.report.send")}
      </button>
    </form>
  );
}
