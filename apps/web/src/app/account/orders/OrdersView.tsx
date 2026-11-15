"use client";
// WebOrders: order history (search, status and date filters) on the left, the
// chosen order's receipt on the right: items, the full fair bill, the PDF,
// order again, report a problem. Phone: the list, then one receipt at a time.
// Deep link: /account/orders?order=<id>.

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { isActive, orderCode, Thumb, useKitchenBrief, type Order } from "@/components/account/shared";
import { Search } from "@/components/Icons";
import { authed } from "@/lib/client";
import { photo } from "@/lib/format";
import { useFormat, useT } from "@/lib/i18n";
import { Receipt } from "./Receipt";

type Filter = "all" | "active" | "delivered" | "cancelled";
const FILTERS: Filter[] = ["all", "active", "delivered", "cancelled"];
const PAGE = 20;

interface Page {
  key: string;
  items: Order[];
  page: number;
  pages: number;
  total: number;
  error?: boolean;
}

async function fetchOrders(f: { q: string; status: Filter; from: string; to: string }, page: number) {
  const qs = new URLSearchParams({ page: String(page), limit: String(PAGE) });
  if (f.q) qs.set("q", f.q);
  if (f.status !== "all") qs.set("status", f.status);
  if (f.from) qs.set("from", f.from);
  if (f.to) qs.set("to", f.to);
  const r = await authed<{ items: Order[]; page: number; total: number; total_pages: number }>("GET", `/api/v1/orders?${qs}`);
  // An order still waiting for payment isn't an order yet.
  return { ...r, items: r.items.filter((o) => o.status !== "pending_payment") };
}

export function StatusPill({ status }: { status: string }) {
  const t = useT();
  const cls = isActive(status)
    ? "bg-[#111418] text-white"
    : status === "cancelled"
      ? "bg-[#FCE8E6] text-[#8C1D18]"
      : "bg-[#DDEBEC] text-[#083F46]";
  return <span className={`inline-flex h-[26px] shrink-0 items-center whitespace-nowrap rounded-full px-[10px] text-xs font-extrabold ${cls}`}>{t(`account.status.${status}`)}</span>;
}

function OrderRow({ o, selected, onPick }: { o: Order; selected: boolean; onPick: () => void }) {
  const f = useFormat();
  const kitchen = useKitchenBrief(o.restaurant_id);
  const summary = o.items_summary ?? (o.items as { name?: string; quantity?: number }[]).map((i) => (i.quantity && i.quantity > 1 ? `${i.quantity} × ${i.name}` : i.name)).join(", ");
  const at = o.placed_at ?? o.created_at;
  return (
    <button
      type="button"
      onClick={onPick}
      aria-current={selected ? "true" : undefined}
      className={`flex w-full items-center gap-[14px] rounded-2xl p-[14px] text-left text-[#111418] ${
        selected ? "bg-[#EFF6F6] shadow-[inset_0_0_0_1.5px_#0B5D66]" : "border border-[#E2E7E8] hover:bg-[#F4F6F6]"
      }`}
    >
      <Thumb src={photo(kitchen?.cover_url, 400)} className="h-16 w-16 shrink-0 rounded-xl" />
      <span className="min-w-0 flex-grow">
        <span className="flex justify-between gap-2">
          <b className="truncate text-[15px]">{o.restaurant_name}</b>
          <b className="shrink-0 text-[15px] tabular-nums">{f.money(o.total, o.currency)}</b>
        </span>
        <span className="mt-[2px] block truncate text-[13px] text-[#4C5A5E]">{summary}</span>
        <span className="mt-[6px] flex items-center justify-between gap-2 text-[13px] text-[#4C5A5E]">
          <span className="min-w-0 truncate">
            {f.date(at)}, {f.time(at)} · {orderCode(o.id)}
          </span>
          <StatusPill status={o.status} />
        </span>
      </span>
    </button>
  );
}

export function OrdersView() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const chosen = params.get("order");

  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<Filter>("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [list, setList] = useState<Page | null>(null);
  const [more, setMore] = useState(false);
  const [retry, setRetry] = useState(0);

  // Search as you type, a moment after the last key.
  useEffect(() => {
    const h = setTimeout(() => setQ(qInput.trim()), 300);
    return () => clearTimeout(h);
  }, [qInput]);

  const filters = { q, status, from, to };
  const key = JSON.stringify([filters, retry]);
  useEffect(() => {
    let live = true;
    const f = JSON.parse(key)[0] as typeof filters;
    fetchOrders(f, 1)
      .then((r) => live && setList({ key, items: r.items, page: 1, pages: r.total_pages, total: r.total }))
      .catch(() => live && setList({ key, items: [], page: 1, pages: 1, total: 0, error: true }));
    return () => {
      live = false;
    };
  }, [key]);

  const loading = !list || list.key !== key;
  const items = loading ? [] : list.items;

  async function older() {
    if (!list) return;
    setMore(true);
    try {
      const r = await fetchOrders(filters, list.page + 1);
      setList((l) => (l && l.key === key ? { ...l, items: [...l.items, ...r.items], page: l.page + 1, pages: r.total_pages } : l));
    } catch {
      /* keep what we have; the button stays */
    } finally {
      setMore(false);
    }
  }

  const pick = (id: string | null) => router.replace(id ? `/account/orders?order=${id}` : "/account/orders", { scroll: false });
  // Desktop shows the first order's receipt until one is chosen; phones show the list.
  const shown = chosen ?? items[0]?.id ?? null;
  const filtered = !!(q || status !== "all" || from || to);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
      <div className={chosen ? "hidden lg:block" : ""}>
        <div className="flex items-baseline justify-between">
          <h1 className="font-display text-[28px] font-semibold tracking-[-0.8px] md:text-[32px]">{t("account.orders.title")}</h1>
          {!loading && !list.error && <span className="text-sm text-[#4C5A5E]">{t("account.orders.count", { count: list.total })}</span>}
        </div>
        <label className="mt-4 flex h-11 items-center gap-[10px] rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-4 text-sm focus-within:border-[#0B5D66]">
          <Search size={16} color="#4C5A5E" />
          <span className="sr-only">{t("account.orders.search")}</span>
          <input
            type="search"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder={t("account.orders.search")}
            className="min-w-0 flex-grow bg-transparent text-[#111418] outline-none placeholder:text-[#4C5A5E]"
          />
        </label>
        <div role="group" aria-label={t("account.orders.filters")} className="mt-3 flex gap-2 overflow-x-auto">
          {FILTERS.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={status === s}
              onClick={() => setStatus(s)}
              className={`flex h-10 shrink-0 items-center rounded-full px-4 text-sm font-bold ${status === s ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
            >
              {t(`account.orders.${s}`)}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3 text-[13px] text-[#4C5A5E]">
          <label className="flex flex-col gap-1 font-bold">
            {t("account.orders.from")}
            <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} className="h-10 rounded-xl border border-[#C9D3D4] px-3 text-sm font-normal text-[#111418]" />
          </label>
          <label className="flex flex-col gap-1 font-bold">
            {t("account.orders.to")}
            <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} className="h-10 rounded-xl border border-[#C9D3D4] px-3 text-sm font-normal text-[#111418]" />
          </label>
          {(from || to) && (
            <button type="button" onClick={() => { setFrom(""); setTo(""); }} className="h-10 font-bold text-[#0B5D66]">
              {t("account.orders.clear_dates")}
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-[10px]" aria-busy={loading}>
          {loading && <p role="status" className="py-6 text-[#4C5A5E]">{t("account.loading")}</p>}
          {!loading && list.error && (
            <p role="alert" className="py-6 text-[#4C5A5E]">
              {t("account.orders.error")}{" "}
              <button type="button" onClick={() => setRetry((n) => n + 1)} className="font-bold text-[#0B5D66]">{t("common.retry")}</button>
            </p>
          )}
          {!loading && !list.error && !items.length && (
            <p className="py-6 text-[#4C5A5E]">
              {filtered ? t("account.orders.empty_filtered") : t("account.orders.empty")}{" "}
              {!filtered && <Link href="/" className="font-bold">{t("account.orders.find_food")}</Link>}
            </p>
          )}
          {items.map((o) => (
            <OrderRow key={o.id} o={o} selected={o.id === shown} onPick={() => pick(o.id)} />
          ))}
        </div>
        {!loading && list.page < list.pages && (
          <div className="mt-3 text-center">
            <button type="button" onClick={older} disabled={more} className="font-bold text-[#0B5D66] disabled:opacity-60">
              {more ? t("account.loading") : t("account.orders.show_older")}
            </button>
          </div>
        )}
      </div>

      <div className={chosen ? "" : "hidden lg:block"}>
        {chosen && (
          <button type="button" onClick={() => pick(null)} className="mb-3 text-sm font-bold text-[#0B5D66] lg:hidden">
            ← {t("account.orders.back")}
          </button>
        )}
        {shown ? (
          <Receipt key={shown} id={shown} />
        ) : (
          !loading && items.length > 0 && <p className="text-[#4C5A5E]">{t("account.receipt.pick_order")}</p>
        )}
      </div>
    </div>
  );
}
