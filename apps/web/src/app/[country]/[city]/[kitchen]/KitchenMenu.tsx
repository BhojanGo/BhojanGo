"use client";
// The menu and the bag on the kitchen page (WebKitchen, MWebMenu, WebCustomise):
// category chips with counts and a menu search, dishes with veg marks, Add or a
// stepper, the dish-options dialog, and "Your bag" with the fair bill from a
// live quote when we know who and where. The bag holds one kitchen.
import Link from "next/link";
import { useEffect, useId, useMemo, useState } from "react";

import { FairBill } from "@/components/FairBill";
import { Check, Close, Minus, Plus, Search } from "@/components/Icons";
import { foodSubtotal, useQuote, type DeliverTo } from "@/components/order/useQuote";
import { photo } from "@/lib/format";
import { useBag, useHydrated, useSession, type BagLine, type Pick } from "@/lib/client";
import { useFormat, useT } from "@/lib/i18n";

type Option = { id: string; name: string; price: string | number; is_default: boolean; is_available: boolean };
type Group = { id: string; name: string; min_picks: number; max_picks: number; options: Option[] };
export type Item = {
  id: string;
  name: string;
  description?: string | null;
  price: number | string;
  is_veg?: boolean;
  is_available: boolean;
  sold_out_today?: boolean;
  image_url?: string | null;
  option_groups?: Group[];
  tags?: string[];
};
export type Category = { key: string; name: string; description: string | null; items: Item[] };
type Kitchen = { id: string; name: string; slug: string; city: string; currency: string };
type T = ReturnType<typeof useT>;
type NewLine = Omit<BagLine, "key">;

const groupsOf = (i: Item): Group[] => (i.option_groups ?? []).map((g) => ({ ...g, options: (g.options ?? []).filter((o) => o.is_available) })).filter((g) => g.options.length);

// Badges only from the dish's own tags (data); unknown tags are not shown.
const BADGES: Record<string, string> = { bestseller: "kitchen.badge_most_ordered", most_ordered: "kitchen.badge_most_ordered", "most-ordered": "kitchen.badge_most_ordered", popular: "kitchen.badge_most_ordered", spicy: "kitchen.badge_spicy", new: "common.new" };

function VegMark({ veg, t }: { veg?: boolean; t: T }) {
  if (veg === undefined) return null;
  const c = veg ? "#2E7D32" : "#8C1D18";
  return (
    <span role="img" aria-label={veg ? t("common.veg") : t("common.non_veg")} title={veg ? t("common.veg") : t("common.non_veg")} style={{ borderColor: c }} className="inline-flex h-[14px] w-[14px] shrink-0 items-center justify-center rounded-[3px] border-[1.5px]">
      {veg ? <span className="h-[6px] w-[6px] rounded-full bg-[#2E7D32]" /> : <span className="h-0 w-0 border-x-[4px] border-b-[7px] border-x-transparent border-b-[#8C1D18]" />}
    </span>
  );
}

function Marks({ item, t }: { item: Item; t: T }) {
  const badges = [...new Set((item.tags ?? []).map((x) => BADGES[x.toLowerCase()]).filter(Boolean) as string[])];
  return (
    <span className="flex items-center gap-2">
      <VegMark veg={item.is_veg} t={t} />
      {badges.map((b) => (
        <span key={b} className="rounded-md bg-[#F6E7CC] px-2 py-[3px] text-xs font-extrabold text-[#7A4F0E]">{t(b)}</span>
      ))}
    </span>
  );
}

function Img({ src, className }: { src: string | null; className?: string }) {
  if (!src) return <span aria-hidden="true" className={`block h-full w-full bg-[#EFF6F6] ${className ?? ""}`} />;
  // eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library, already optimised
  return <img src={src} alt="" loading="lazy" className={`block h-full w-full object-cover ${className ?? ""}`} />;
}

export function KitchenMenu({ restaurant, categories, deliverTo, closed }: { restaurant: Kitchen; categories: Category[]; deliverTo: DeliverTo | null; closed: boolean }) {
  const t = useT();
  const f = useFormat();
  const hydrated = useHydrated();
  const bag = useBag();
  const user = useSession((s) => s.user);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(categories[0]?.key ?? "");
  const [open, setOpen] = useState<Item | null>(null);
  const [pending, setPending] = useState<{ line: NewLine } | null>(null);
  const fmt = (n: number | string) => f.money(n, restaurant.currency, { whole: true });

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return categories;
    return categories
      .map((c) => ({ ...c, items: c.items.filter((i) => `${i.name} ${i.description ?? ""}`.toLowerCase().includes(needle)) }))
      .filter((c) => c.items.length);
  }, [categories, q]);

  // Which section is on screen: the chip follows it.
  useEffect(() => {
    const els = categories.map((c) => document.getElementById(`cat-${c.key}`)).filter(Boolean) as HTMLElement[];
    if (!els.length || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (top) setActive(top.target.id.slice(4));
      },
      { rootMargin: "-200px 0px -60% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [categories, shown]);

  const mine = hydrated && bag.restaurant?.id === restaurant.id ? bag.lines : [];
  const qtyOf = (id: string) => mine.filter((l) => l.menuItemId === id).reduce((n, l) => n + l.quantity, 0);

  function put(line: NewLine) {
    if (bag.restaurant && bag.restaurant.id !== restaurant.id && bag.lines.length) setPending({ line });
    else bag.add(restaurant, line);
  }
  function plus(item: Item) {
    if (groupsOf(item).length) return setOpen(item);
    put({ menuItemId: item.id, name: item.name, unitPrice: Number(item.price), quantity: 1, picks: [], summary: "" });
  }
  function minus(item: Item) {
    const last = [...mine].reverse().find((l) => l.menuItemId === item.id);
    if (last) bag.setQuantity(last.key, last.quantity - 1);
  }

  const quote = useQuote({
    enabled: hydrated && !!user && bag.restaurant?.id === restaurant.id,
    restaurantId: restaurant.id,
    lines: mine,
    deliverTo,
    fallbackError: t("common.error"),
  });

  return (
    <section className="mx-auto grid max-w-[1440px] gap-12 px-5 pb-28 pt-2 md:grid-cols-[minmax(0,1fr)_400px] md:px-16 md:pb-[72px]">
      <div className="min-w-0">
        {/* chips + search */}
        <div className={`sticky ${deliverTo ? "top-[126px] md:top-[76px]" : "top-0"} z-20 -mx-5 flex items-center gap-2 border-b border-[#E2E7E8] bg-white px-5 py-3 md:mx-0 md:px-0 md:py-4`}>
          <nav aria-label={t("kitchen.categories")} className="flex min-w-0 flex-grow gap-2 overflow-x-auto [scrollbar-width:none]">
            {categories.map((c) => {
              const on = c.key === active;
              return (
                <a
                  key={c.key}
                  href={`#cat-${c.key}`}
                  aria-current={on ? "true" : undefined}
                  onClick={() => setActive(c.key)}
                  className={`flex h-10 shrink-0 items-center rounded-full px-4 text-sm font-bold ${on ? "bg-[#111418] text-white hover:text-white" : "border border-[#C9D3D4] text-[#111418] hover:text-[#111418]"}`}
                >
                  <span className="md:hidden">{c.name}</span>
                  <span className="hidden md:inline">{t("kitchen.category_count", { name: c.name, count: c.items.length })}</span>
                </a>
              );
            })}
          </nav>
          <label className="hidden h-10 w-[180px] shrink-0 items-center gap-2 rounded-full bg-[#F4F6F6] px-4 text-sm text-[#4C5A5E] focus-within:ring-2 focus-within:ring-[#0B5D66] md:flex lg:w-[200px]">
            <Search size={16} color="#4C5A5E" />
            <span className="sr-only">{t("kitchen.search_menu")}</span>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("kitchen.search_menu")} className="min-w-0 flex-grow bg-transparent text-[#111418] outline-none placeholder:text-[#4C5A5E]" />
          </label>
        </div>

        {closed && <p className="mt-5 rounded-2xl bg-[#F1E3E1] px-4 py-3 text-sm font-semibold text-[#8C1D18]">{t("kitchen.closed_note")}</p>}
        {categories.length === 0 && <p className="mt-8 text-[#4C5A5E]">{t("kitchen.menu_unavailable")}</p>}
        {q.trim() && shown.length === 0 && <p className="mt-8 text-[#4C5A5E]">{t("kitchen.no_match", { q: q.trim() })}</p>}

        {shown.map((c, ci) => (
          <section key={c.key} id={`cat-${c.key}`} aria-labelledby={`h-${c.key}`} className="scroll-mt-[150px] md:scroll-mt-[160px]">
            <div className={ci ? "mt-8" : "mt-6"}>
              <h2 id={`h-${c.key}`} className="m-0 font-display text-[22px] font-semibold tracking-[-0.5px] md:text-2xl">{c.name}</h2>
              {c.description && <div className="text-sm text-[#4C5A5E]">{c.description}</div>}
            </div>
            {c.items.map((i) => {
              const off = !i.is_available || !!i.sold_out_today;
              const n = qtyOf(i.id);
              // A dish photo only when the kitchen has one; otherwise a clean text row.
              const pic = photo(i.image_url, 400);
              const control = off ? (
                  <span className="flex h-10 items-center whitespace-nowrap rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-4 text-sm font-extrabold text-[#4C5A5E]">{t("kitchen.sold_out")}</span>
                ) : n > 0 ? (
                  <span className="flex h-10 items-center gap-1 rounded-full bg-[#0B5D66] px-1 font-extrabold text-white shadow-[0_6px_16px_rgba(11,93,102,0.3)]">
                    <button type="button" aria-label={t("kitchen.one_less", { name: i.name })} onClick={() => minus(i)} className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-[#083F46]"><Minus color="#FFFFFF" /></button>
                    <span aria-live="polite" className="min-w-[14px] text-center tabular-nums">{n}</span>
                    <button type="button" aria-label={t("kitchen.one_more", { name: i.name })} disabled={closed} onClick={() => plus(i)} className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-[#083F46] disabled:opacity-50"><Plus color="#FFFFFF" /></button>
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={closed}
                    aria-label={t("kitchen.add_dish", { name: i.name })}
                    onClick={() => plus(i)}
                    className="flex h-10 items-center rounded-full border-[1.5px] border-[#0B5D66] bg-white px-[22px] font-extrabold text-[#0B5D66] shadow-[0_6px_16px_rgba(17,20,24,0.12)] hover:bg-[#EFF6F6] disabled:border-[#C9D3D4] disabled:text-[#4C5A5E]"
                  >
                    {t("common.add")}
                  </button>
                );
              return (
                <div key={i.id} className={`flex gap-4 border-b border-[#E2E7E8] md:gap-5 ${pic ? "pb-[30px] pt-[22px]" : "items-center py-[22px]"} ${off ? "opacity-60" : ""}`}>
                  <span className="min-w-0 flex-grow">
                    <Marks item={i} t={t} />
                    <b className="mt-2 block text-lg">{i.name}</b>
                    <b className="mt-1 block text-base">{fmt(i.price)}</b>
                    {i.description && <span className="mt-2 block text-sm leading-[1.5] text-[#4C5A5E]">{i.description}</span>}
                    {off && <span className="mt-2 block text-sm font-bold text-[#8C1D18]">{t("kitchen.sold_out_today")}</span>}
                  </span>
                  {pic ? (
                    <span className="relative h-[104px] w-[112px] shrink-0 rounded-2xl md:h-[140px] md:w-[156px] md:rounded-[18px]">
                      <span className="block h-full w-full overflow-hidden rounded-2xl md:rounded-[18px]">
                        <Img src={pic} />
                      </span>
                      <span className="absolute bottom-[-18px] left-1/2 -translate-x-1/2">{control}</span>
                    </span>
                  ) : (
                    <span className="shrink-0">{control}</span>
                  )}
                </div>
              );
            })}
          </section>
        ))}
      </div>

      <aside className="hidden md:block" aria-label={t("kitchen.your_bag")}>
        <div className="sticky top-[100px]">
          <BagPanel quote={quote} signedIn={!!user} hasAddress={!!deliverTo} kitchenId={restaurant.id} />
        </div>
      </aside>

      <PhoneBagBar quote={quote.quote?.total ?? null} />

      {open && <Customise key={open.id} item={open} currency={restaurant.currency} onClose={() => setOpen(null)} onAdd={(line) => { setOpen(null); put(line); }} />}
      {pending && (
        <NewBag
          from={bag.restaurant?.name ?? ""}
          dish={pending.line.name}
          onKeep={() => setPending(null)}
          onStart={() => {
            bag.clear();
            bag.add(restaurant, pending.line);
            setPending(null);
          }}
        />
      )}
    </section>
  );
}

// ── the dish-options dialog (WebCustomise) ───────────────────────────────────

function defaults(groups: Group[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const g of groups) {
    const d = g.options.filter((o) => o.is_default).map((o) => o.name);
    const first = g.options[0];
    out[g.name] = d.length ? d.slice(0, Math.max(1, g.max_picks)) : g.min_picks > 0 && first ? [first.name] : [];
  }
  return out;
}

function useEscape(onClose: () => void) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", k);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", k);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);
}

function Customise({ item, currency, onClose, onAdd }: { item: Item; currency: string; onClose: () => void; onAdd: (line: NewLine) => void }) {
  const t = useT();
  const f = useFormat();
  const titleId = useId();
  const groups = useMemo(() => groupsOf(item), [item]);
  const [picks, setPicks] = useState<Record<string, string[]>>(() => defaults(groups));
  const [qty, setQty] = useState(1);
  useEscape(onClose);
  const fmt = (n: number) => f.money(n, currency, { whole: true });
  const base = Number(item.price);
  const extra = groups.reduce((sum, g) => sum + g.options.filter((o) => picks[g.name]?.includes(o.name)).reduce((a, o) => a + Number(o.price), 0), 0);
  const unit = base + extra;
  const valid = groups.every((g) => (picks[g.name]?.length ?? 0) >= g.min_picks);

  function toggle(g: Group, name: string) {
    setPicks((p) => {
      const cur = p[g.name] ?? [];
      if (g.max_picks === 1) return { ...p, [g.name]: g.min_picks === 0 && cur.includes(name) ? [] : [name] };
      return { ...p, [g.name]: cur.includes(name) ? cur.filter((x) => x !== name) : cur.length < g.max_picks ? [...cur, name] : cur };
    });
  }
  function add() {
    const list: Pick[] = groups.flatMap((g) => (picks[g.name] ?? []).map((o) => ({ group: g.name, option: o })));
    onAdd({ menuItemId: item.id, name: item.name, unitPrice: unit, quantity: qty, picks: list, summary: list.map((p) => p.option).join(", ") });
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-[rgba(17,20,24,0.5)] md:items-center md:p-6" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(e) => e.stopPropagation()} className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-[28px] bg-white md:max-h-[90vh] md:w-[640px] md:rounded-[28px]">
        <div className="min-h-0 flex-grow overflow-y-auto">
          {/* the dish photo only when there is one (no stand-in picture) */}
          <div className={item.image_url ? "relative h-[200px] md:h-[260px]" : "flex justify-end px-4 pt-4"}>
            {item.image_url && <Img src={photo(item.image_url, 800)} />}
            <button type="button" autoFocus aria-label={t("common.close")} onClick={onClose} className={`flex h-11 w-11 items-center justify-center rounded-full bg-white shadow-[0_2px_8px_rgba(17,20,24,0.18)] ${item.image_url ? "absolute right-4 top-4" : "border border-[#E2E7E8]"}`}>
              <Close color="#111418" />
            </button>
          </div>
          <div className={`px-5 pb-5 md:px-7 ${item.image_url ? "pt-6" : "pt-0"}`}>
            <Marks item={item} t={t} />
            <h2 id={titleId} className="m-0 mt-2 font-display text-[26px] font-semibold tracking-[-0.6px] md:text-[30px]">{item.name}</h2>
            {item.description && <p className="m-0 mt-2 text-[15px] text-[#4C5A5E]">{item.description}</p>}
            {groups.map((g) => {
              const radio = g.max_picks === 1;
              const absolute = g.min_picks >= 1 && radio && g.options.some((o) => Number(o.price) > 0); // a portion: show the dish's price with it
              return (
                <fieldset key={g.id} className="mt-6 border-0 p-0">
                  <legend className="flex w-full items-center justify-between">
                    <b className="text-[17px]">{g.name}</b>
                    {g.min_picks > 0 ? (
                      <span className="rounded-md bg-[#DDEBEC] px-2 py-[3px] text-xs font-extrabold uppercase text-[#083F46]">
                        {g.min_picks === g.max_picks ? t("kitchen.required_pick", { count: g.min_picks }) : t("kitchen.required_range", { min: g.min_picks, max: g.max_picks })}
                      </span>
                    ) : (
                      <span className="text-xs font-extrabold uppercase text-[#4C5A5E]">{t("kitchen.optional_upto", { count: g.max_picks })}</span>
                    )}
                  </legend>
                  <div className="mt-2">
                    {g.options.map((o) => {
                      const on = picks[g.name]?.includes(o.name) ?? false;
                      const price = Number(o.price);
                      const full = !on && !radio && (picks[g.name]?.length ?? 0) >= g.max_picks;
                      return (
                        <label key={o.id} className={`flex h-[53px] cursor-pointer items-center gap-[14px] border-b border-[#EEF1F1] ${full ? "cursor-not-allowed opacity-50" : ""}`}>
                          <input type={radio ? "radio" : "checkbox"} name={g.id} checked={on} disabled={full} onChange={() => toggle(g, o.name)} className="peer sr-only" />
                          {radio ? (
                            <span aria-hidden="true" className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border-2 peer-focus-visible:ring-2 peer-focus-visible:ring-[#0B5D66] peer-focus-visible:ring-offset-2 ${on ? "border-[#0B5D66]" : "border-[#C9D3D4]"}`}>
                              {on && <span className="h-3 w-3 rounded-full bg-[#0B5D66]" />}
                            </span>
                          ) : (
                            <span aria-hidden="true" className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[6px] border-2 peer-focus-visible:ring-2 peer-focus-visible:ring-[#0B5D66] peer-focus-visible:ring-offset-2 ${on ? "border-[#0B5D66] bg-[#0B5D66]" : "border-[#C9D3D4]"}`}>
                              {on && <Check color="#FFFFFF" />}
                            </span>
                          )}
                          <span className={`flex-grow text-base ${on ? "font-bold" : ""}`}>{o.name}</span>
                          <span className="text-base text-[#4C5A5E]">{absolute ? fmt(base + price) : price > 0 ? `+${fmt(price)}` : ""}</span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>
              );
            })}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-4 border-t border-[#E2E7E8] px-5 py-[18px] md:px-7">
          <span className="flex h-14 items-center gap-1 rounded-full border-[1.5px] border-[#C9D3D4] px-2">
            <button type="button" aria-label={t("kitchen.less")} onClick={() => setQty((n) => Math.max(1, n - 1))} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-[#F4F6F6]"><Minus /></button>
            <b aria-live="polite" className="w-5 text-center text-lg tabular-nums">{qty}</b>
            <button type="button" aria-label={t("kitchen.more_qty")} onClick={() => setQty((n) => Math.min(20, n + 1))} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-[#F4F6F6]"><Plus /></button>
          </span>
          <button type="button" disabled={!valid} onClick={add} className="h-14 flex-grow rounded-full bg-[#0B5D66] px-5 text-[15px] font-extrabold text-white hover:bg-[#083F46] disabled:bg-[#8FB3B7]">
            {t("kitchen.add_to_bag", { price: fmt(unit * qty) })}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewBag({ from, dish, onKeep, onStart }: { from: string; dish: string; onKeep: () => void; onStart: () => void }) {
  const t = useT();
  const titleId = useId();
  useEscape(onKeep);
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-[rgba(17,20,24,0.5)] md:items-center" onClick={onKeep}>
      <div role="alertdialog" aria-modal="true" aria-labelledby={titleId} onClick={(e) => e.stopPropagation()} className="w-full rounded-t-[28px] bg-white p-6 md:w-[460px] md:rounded-[28px]">
        <h2 id={titleId} className="m-0 font-display text-2xl font-semibold tracking-[-0.5px]">{t("kitchen.new_bag_title")}</h2>
        <p className="mt-2 text-[15px] text-[#4C5A5E]">{t("kitchen.new_bag_body", { kitchen: from, dish })}</p>
        <div className="mt-6 flex gap-3">
          <button type="button" autoFocus onClick={onKeep} className="h-12 flex-1 rounded-full border-[1.5px] border-[#C9D3D4] font-extrabold">{t("kitchen.keep_bag")}</button>
          <button type="button" onClick={onStart} className="h-12 flex-1 rounded-full bg-[#0B5D66] font-extrabold text-white hover:bg-[#083F46]">{t("kitchen.start_new_bag")}</button>
        </div>
      </div>
    </div>
  );
}

// ── your bag ─────────────────────────────────────────────────────────────────

function BagPanel({ quote, signedIn, hasAddress, kitchenId }: { quote: ReturnType<typeof useQuote>; signedIn: boolean; hasAddress: boolean; kitchenId: string }) {
  const t = useT();
  const f = useFormat();
  const hydrated = useHydrated();
  const { restaurant, lines, setQuantity } = useBag();
  const count = lines.reduce((n, l) => n + l.quantity, 0);
  const box = "rounded-[24px] border border-[#E2E7E8] p-[22px]";
  const head = (
    <div className="flex items-baseline justify-between">
      <h2 className="m-0 font-display text-[22px] font-semibold tracking-[-0.5px]">{t("kitchen.your_bag")}</h2>
      {count > 0 && <span className="text-sm text-[#4C5A5E]">{t("kitchen.items", { count })}</span>}
    </div>
  );
  if (!hydrated || !restaurant || !lines.length) {
    return (
      <div className={box}>
        {head}
        <p className="mt-2 text-[15px] text-[#4C5A5E]">{t("kitchen.bag_empty")}</p>
      </div>
    );
  }
  const currency = restaurant.currency;
  const q = quote.quote;
  return (
    <div className={box}>
      {head}
      {restaurant.id !== kitchenId && <p className="mt-1 text-sm text-[#4C5A5E]">{t("kitchen.from_kitchen", { kitchen: restaurant.name })}</p>}
      <ul className="mt-[14px] flex list-none flex-col gap-3 p-0 text-[15px]">
        {lines.map((l) => (
          <li key={l.key} className="flex items-start gap-[10px]">
            <span className="min-w-0 flex-grow">
              {t("kitchen.line", { count: l.quantity, name: l.name })}
              {l.summary && <span className="block truncate text-[13px] text-[#4C5A5E]">{l.summary}</span>}
            </span>
            <span className="flex shrink-0 items-center gap-1">
              <button type="button" aria-label={t("kitchen.one_less", { name: l.name })} onClick={() => setQuantity(l.key, l.quantity - 1)} className="flex h-7 w-7 items-center justify-center rounded-full border border-[#E2E7E8] hover:bg-[#F4F6F6]"><Minus size={12} /></button>
              <button type="button" aria-label={t("kitchen.one_more", { name: l.name })} onClick={() => setQuantity(l.key, l.quantity + 1)} className="flex h-7 w-7 items-center justify-center rounded-full border border-[#E2E7E8] hover:bg-[#F4F6F6]"><Plus size={12} /></button>
            </span>
            <b className="min-w-[64px] shrink-0 text-right tabular-nums">{f.money(l.unitPrice * l.quantity, currency, { whole: true })}</b>
          </li>
        ))}
      </ul>
      <div className="mt-4 border-t border-[#E2E7E8] pt-[14px] text-sm">
        {q ? (
          <FairBill
            lines={q.lines}
            total={q.total}
            currency={q.currency}
            formatLocale={f.formatLocale}
            t={t}
            distance={t(q.distance_unit === "mi" ? "common.mi" : "common.km", { n: q.distance })}
            note={t("kitchen.before_tip")}
            compact
          />
        ) : (
          <>
            <div className="flex items-baseline justify-between text-base">
              <span>{t("bill.line_food")}</span>
              <b className="tabular-nums">{f.money(foodSubtotal(lines), currency)}</b>
            </div>
            <p className="mt-1 text-[13px] text-[#4C5A5E]" aria-live="polite">
              {quote.loading ? t("kitchen.working_out") : quote.error ? quote.error : !signedIn ? t("kitchen.bill_after_sign_in") : !hasAddress ? t("kitchen.bill_after_address") : t("kitchen.bill_at_checkout")}
            </p>
          </>
        )}
      </div>
      <Link href="/checkout" className="mt-4 flex h-14 w-full items-center justify-center rounded-full bg-[#0B5D66] px-[22px] text-[15px] font-extrabold text-white hover:bg-[#083F46] hover:text-white">
        {t("kitchen.go_to_checkout")}
      </Link>
    </div>
  );
}

function PhoneBagBar({ quote }: { quote: string | null }) {
  const t = useT();
  const f = useFormat();
  const hydrated = useHydrated();
  const { restaurant, lines } = useBag();
  const count = lines.reduce((n, l) => n + l.quantity, 0);
  if (!hydrated || !restaurant || !count) return null;
  return (
    <Link
      href="/checkout"
      className="fixed inset-x-4 bottom-4 z-40 flex h-14 items-center justify-between rounded-full bg-[#0B5D66] px-[22px] text-base font-extrabold text-white shadow-[0_10px_30px_rgba(11,93,102,0.35)] hover:text-white md:hidden"
    >
      <span>{t("kitchen.bar_summary", { count, total: f.money(quote ?? foodSubtotal(lines), restaurant.currency) })}</span>
      <span>{t("kitchen.view_bag")} →</span>
    </Link>
  );
}
