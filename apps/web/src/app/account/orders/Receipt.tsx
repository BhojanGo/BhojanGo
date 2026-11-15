"use client";
// One order's receipt (WebOrders, right): the kitchen, when, the items with
// their options, the full fair bill from the pricing engine, the PDF (a tax
// invoice where the bill carries GST, else a receipt), order again, report a
// problem, track.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { isActive, kitchenBrief, orderCode, saveFile, Thumb, useKitchenBrief, type Order } from "@/components/account/shared";
import { FairBill } from "@/components/FairBill";
import { RateOrder } from "@/components/order/RateOrder";
import { authed, useBag } from "@/lib/client";
import { photo } from "@/lib/format";
import { useFormat, useT } from "@/lib/i18n";
import type { BillLine } from "@/lib/server";

interface Bill {
  currency: string;
  total: string;
  lines: BillLine[];
  distance?: string | number | null;
  distance_unit?: string | null;
}

interface Reorder {
  restaurant: { id: string; slug: string; name: string; currency?: string };
  items: { menu_item_id: string; name: string; quantity: number; options: { group: string; option: string; name?: string }[]; price: number; available?: boolean }[];
  unavailable: string[];
}

type ItemOption = string | { name?: string; option?: string };
type Item = { menu_item_id?: string; name?: string; quantity?: number; options?: ItemOption[]; total?: number; unit_price?: number };

interface Loaded {
  id: string;
  order: Order | null;
  bill: Bill | null;
}

const btn = "flex h-12 shrink-0 items-center whitespace-nowrap rounded-full px-5 font-bold";
const ghost = `${btn} border-[1.5px] border-[#C9D3D4] text-[#111418] hover:bg-[#F4F6F6] hover:text-[#111418] disabled:opacity-60`;

export function Receipt({ id }: { id: string }) {
  const t = useT();
  const f = useFormat();
  const router = useRouter();
  const [data, setData] = useState<Loaded | null>(null);
  const [busy, setBusy] = useState<"pdf" | "again" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [missing, setMissing] = useState<{ names: string[]; added: boolean } | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([
      authed<Order>("GET", `/api/v1/orders/${id}`).catch(() => null),
      authed<Bill>("GET", `/api/v1/pricing/orders/${id}/bill`).catch(() => null),
    ]).then(([order, bill]) => live && setData({ id, order, bill }));
    return () => {
      live = false;
    };
  }, [id]);

  const order = data?.id === id ? data.order : null;
  const kitchen = useKitchenBrief(order?.restaurant_id);

  if (!data || data.id !== id) {
    return <div role="status" className="rounded-3xl border border-[#E2E7E8] p-6 text-[#4C5A5E]">{t("account.loading")}</div>;
  }
  if (!order) {
    return <div role="alert" className="rounded-3xl border border-[#E2E7E8] p-6 text-[#4C5A5E]">{t("account.receipt.not_found")}</div>;
  }

  const bill = data.bill;
  const code = orderCode(order.id);
  const at = order.placed_at ?? order.created_at;
  const delivered = order.status === "delivered" && order.actual_delivery_time;
  const minutes = delivered ? Math.max(1, Math.round((new Date(order.actual_delivery_time as string).getTime() - new Date(at).getTime()) / 60000)) : 0;
  const active = isActive(order.status);
  const cancelled = order.status === "cancelled";
  // A GST bill gets a tax invoice; anywhere else a receipt. The bill says which (its tax lines).
  const gst = (bill?.lines ?? []).some((l) => /\bGST\b/i.test(l.label));
  const items = (order.items ?? []) as Item[];
  const addr = (order.delivery_address ?? {}) as { label?: string; street?: string; city?: string };
  const payKey = `account.pay.${order.payment_method}`;
  const payLabel = t(payKey) === payKey ? order.payment_method : t(payKey);
  const distance = bill?.distance != null && bill.distance !== "" ? t(bill.distance_unit === "mi" ? "common.mi" : "common.km", { n: f.number(Number(bill.distance)) }) : null;

  async function download() {
    setBusy("pdf");
    setProblem(null);
    try {
      const blob = await authed<Blob>("GET", `/api/v1/orders/${id}/receipt.pdf`);
      saveFile(blob, `bhojango-${code.slice(1)}.pdf`);
    } catch {
      setProblem(t("account.receipt.download_failed"));
    } finally {
      setBusy(null);
    }
  }

  async function orderAgain() {
    setBusy("again");
    setProblem(null);
    setMissing(null);
    try {
      const r = await authed<Reorder>("POST", `/api/v1/orders/${id}/reorder`);
      const ok = r.items.filter((i) => i.available !== false);
      const names = [...r.unavailable, ...r.items.filter((i) => i.available === false).map((i) => i.name)];
      if (ok.length) {
        const brief = await kitchenBrief(r.restaurant.id);
        const restaurant = {
          id: r.restaurant.id,
          name: r.restaurant.name,
          slug: r.restaurant.slug,
          city: brief?.city ?? "",
          currency: r.restaurant.currency ?? brief?.currency ?? order!.currency,
        };
        const bag = useBag.getState();
        bag.clear();
        for (const i of ok) {
          bag.add(restaurant, {
            menuItemId: i.menu_item_id,
            name: i.name,
            unitPrice: Number(i.price),
            quantity: i.quantity,
            picks: i.options.map((o) => ({ group: o.group, option: o.option })),
            summary: i.options.map((o) => o.name ?? o.option).join(", "),
          });
        }
      }
      if (!names.length) router.push("/checkout");
      else setMissing({ names, added: ok.length > 0 });
    } catch {
      setProblem(t("account.receipt.reorder_failed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <article aria-label={t("account.receipt.label", { code })} className="overflow-hidden rounded-3xl border border-[#E2E7E8]">
      <div className="relative h-[140px] md:h-[160px]">
        <Thumb src={photo(kitchen?.cover_url, 800)} name={order.restaurant_name} className="h-full w-full" />
        <span aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(180deg,rgba(17,20,24,0)_30%,rgba(17,20,24,0.75)_100%)]" />
        <div className="absolute bottom-[18px] left-5 right-5 text-white md:left-6">
          <h2 className="font-display text-[24px] font-semibold md:text-[26px]">{order.restaurant_name}</h2>
          <span className="text-sm">
            {delivered
              ? t("account.receipt.delivered_line", { date: f.date(order.actual_delivery_time as string), time: f.time(order.actual_delivery_time as string), minutes, code })
              : t("account.receipt.status_line", { status: t(`account.status.${order.status}`), date: f.date(at), time: f.time(at), code })}
          </span>
        </div>
      </div>

      <div className="p-5 md:p-6">
        <div className="flex flex-wrap gap-[10px]">
          {active && (
            <Link href={`/orders/${order.id}/track`} className={`${btn} bg-[#0B5D66] font-extrabold text-white hover:bg-[#083F46] hover:text-white`}>
              {t("account.receipt.track")}
            </Link>
          )}
          {!active && (
            <button type="button" onClick={orderAgain} disabled={busy !== null} className={`${btn} bg-[#0B5D66] font-extrabold text-white hover:bg-[#083F46] disabled:opacity-60`}>
              {busy === "again" ? t("account.receipt.adding") : t("account.receipt.order_again")}
            </button>
          )}
          {!cancelled && (
            <Link href={`/account/orders/${order.id}/report`} className={ghost}>
              {t("account.receipt.report")}
            </Link>
          )}
          {!cancelled && (
            <button type="button" onClick={download} disabled={busy !== null} className={ghost}>
              {busy === "pdf" ? t("account.receipt.downloading") : gst ? t("account.receipt.tax_invoice") : t("account.receipt.receipt_pdf")}
            </button>
          )}
        </div>
        {problem && <p role="alert" className="mt-3 text-sm font-semibold text-[#8C1D18]">{problem}</p>}
        {missing && (
          <div role="status" className="mt-3 rounded-2xl bg-[#F6E7CC] p-4 text-sm text-[#7A4F0E]">
            {missing.added ? t("account.receipt.unavailable", { items: missing.names.join(", ") }) : t("account.receipt.none_available")}
            {missing.added && (
              <Link href="/checkout" className="mt-2 block font-extrabold text-[#0B5D66]">
                {t("account.receipt.continue_checkout")}
              </Link>
            )}
          </div>
        )}

        {order.status === "delivered" && <RateOrder key={order.id} orderId={order.id} order={order} compact />}

        <h3 className="mt-6 text-[13px] font-extrabold uppercase tracking-[1px] text-[#4C5A5E]">{t("account.receipt.items")}</h3>
        <ul className="mt-[10px] flex flex-col gap-2 text-[15px]">
          {items.map((i, n) => {
            const opts = (i.options ?? []).map((o) => (typeof o === "string" ? o : o.name ?? o.option)).filter(Boolean).join(", ");
            const line = i.total ?? (i.unit_price != null ? i.unit_price * (i.quantity ?? 1) : null);
            return (
              <li key={`${i.menu_item_id}-${n}`} className="flex justify-between gap-3">
                <span>
                  {i.quantity ?? 1} × {i.name}
                  {opts && <span className="text-[#4C5A5E]"> · {opts}</span>}
                </span>
                {line != null && <b className="shrink-0 tabular-nums">{f.money(line, order.currency)}</b>}
              </li>
            );
          })}
        </ul>

        <h3 className="mt-6 text-[13px] font-extrabold uppercase tracking-[1px] text-[#4C5A5E]">{t("account.receipt.fair_bill")}</h3>
        <div className="mt-[10px]">
          {bill ? (
            <FairBill
              lines={bill.lines}
              total={bill.total}
              currency={bill.currency}
              formatLocale={f.formatLocale}
              t={t}
              distance={distance}
              totalLabel={cancelled ? t("account.receipt.total") : t("account.receipt.you_paid")}
            />
          ) : (
            <>
              <p className="text-sm text-[#4C5A5E]">{t("account.receipt.no_bill")}</p>
              <div className="mt-4 flex items-baseline justify-between border-t border-dashed border-[#C9D3D4] pt-4">
                <b className="text-xl">{t("account.receipt.total")}</b>
                <b className="text-xl tabular-nums">{f.money(order.total, order.currency)}</b>
              </div>
            </>
          )}
          {!cancelled && order.placed_at && (
            <p className="mt-[6px] text-[13px] text-[#4C5A5E]">{t("account.receipt.paid_with", { method: payLabel, date: f.date(order.placed_at), time: f.time(order.placed_at) })}</p>
          )}
        </div>

        {(addr.street || addr.label) && (
          <div className="mt-6 rounded-2xl bg-[#F4F6F6] p-4 text-sm">
            <b className="block">{delivered ? t("account.receipt.delivered_to") : t("account.receipt.deliver_to")}</b>
            <span className="text-[#4C5A5E]">{[addr.label, addr.street, addr.city].filter(Boolean).join(" · ")}</span>
          </div>
        )}
      </div>
    </article>
  );
}
