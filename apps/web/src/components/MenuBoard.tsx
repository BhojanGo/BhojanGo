"use client";
// The menu and the bag on a restaurant page: tap a dish to choose its options
// (as on CustomerMenu.html), add it to the bag, go to checkout.
import Link from "next/link";
import { useState } from "react";

import { useBag, useHydrated, type Pick } from "@/lib/client";
import { Button, Sheet } from "@bhojango/ui";
import { money } from "@bhojango/ui/bill";

type Option = { id: string; name: string; price: string | number; is_default: boolean; is_available: boolean };
type Group = { id: string; name: string; min_picks: number; max_picks: number; options: Option[] };
type Item = { id: string; name: string; description?: string | null; price: string | number; is_veg?: boolean; is_available: boolean;
  sold_out_today?: boolean; option_groups?: Group[] };
type Restaurant = { id: string; name: string; slug: string; city: string; currency: string };

function defaults(groups: Group[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const g of groups) {
    const d = g.options.filter((o) => o.is_default && o.is_available).map((o) => o.name);
    const first = g.options.find((o) => o.is_available);
    out[g.name] = d.length ? d.slice(0, g.max_picks) : g.min_picks > 0 && first ? [first.name] : [];
  }
  return out;
}

export function MenuBoard({ restaurant, categories }: { restaurant: Restaurant; categories: { name: string; items: Item[] }[] }) {
  const [open, setOpen] = useState<Item | null>(null);
  return (
    <div className="mt-8 space-y-10">
      {categories.length === 0 ? <p className="text-muted">The menu isn&apos;t available right now.</p> : null}
      {categories.map((c) => (
        <section key={c.name} aria-labelledby={`cat-${c.name}`}>
          <h2 id={`cat-${c.name}`} className="mb-3 font-display text-2xl font-semibold">{c.name}</h2>
          <ul className="grid gap-3 lg:grid-cols-2">
            {c.items.map((i) => {
              const off = !i.is_available || i.sold_out_today;
              return (
                <li key={i.id}>
                  <button type="button" disabled={off} onClick={() => setOpen(i)} aria-label={`${i.name}, ${money(Number(i.price), restaurant.currency, { decimals: 0 })}`}
                    className="flex w-full items-center gap-3 rounded-card bg-white p-4 text-left transition enabled:hover:shadow-float disabled:opacity-50">
                    <span className="min-w-0 flex-1">
                      <span className="block font-extrabold">{i.name}</span>
                      {i.description ? <span className="mt-1 line-clamp-2 block text-sm text-muted">{i.description}</span> : null}
                      <span className="mt-1 block font-bold">{off ? "Sold out today" : money(Number(i.price), restaurant.currency, { decimals: 0 })}</span>
                    </span>
                    <span aria-hidden className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill border-[1.5px] border-line-strong text-2xl font-extrabold text-peacock">+</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {open ? <ItemSheet key={open.id} item={open} restaurant={restaurant} onClose={() => setOpen(null)} /> : null}
      <MobileBagBar />
    </div>
  );
}

function ItemSheet({ item, restaurant, onClose }: { item: Item; restaurant: Restaurant; onClose: () => void }) {
  const groups = (item.option_groups ?? []).map((g) => ({ ...g, options: g.options.filter((o) => o.is_available) }));
  const [picks, setPicks] = useState<Record<string, string[]>>(() => defaults(groups));
  const [qty, setQty] = useState(1);
  const add = useBag((s) => s.add);
  const extra = groups.reduce((sum, g) => sum + g.options.filter((o) => picks[g.name]?.includes(o.name)).reduce((a, o) => a + Number(o.price), 0), 0);
  const unit = Number(item.price) + extra;
  const valid = groups.every((g) => (picks[g.name]?.length ?? 0) >= g.min_picks);

  function toggle(g: Group, name: string) {
    setPicks((p) => {
      const cur = p[g.name] ?? [];
      if (g.max_picks === 1) return { ...p, [g.name]: [name] };
      return { ...p, [g.name]: cur.includes(name) ? cur.filter((x) => x !== name) : cur.length < g.max_picks ? [...cur, name] : cur };
    });
  }

  function addToBag() {
    const list: Pick[] = groups.flatMap((g) => (picks[g.name] ?? []).map((o) => ({ group: g.name, option: o })));
    add(restaurant, { menuItemId: item.id, name: item.name, unitPrice: unit, quantity: qty, picks: list, summary: list.map((p) => p.option).join(", ") });
    onClose();
  }

  return (
    <Sheet open onClose={onClose} title={item.name}
      footer={<Button block size="lg" disabled={!valid} onClick={addToBag}>Add to bag · {money(unit * qty, restaurant.currency, { decimals: 0 })}</Button>}>
      <div className="space-y-5">
        {item.description ? <p className="text-muted">{item.description}</p> : null}
        {groups.map((g) => (
          <fieldset key={g.id} className="space-y-2">
            <legend className="mb-1 text-sm font-extrabold">
              {g.name} <span className="font-semibold text-muted">{g.min_picks > 0 ? (g.max_picks === 1 ? "· pick 1" : `· pick ${g.min_picks}–${g.max_picks}`) : `· optional${g.max_picks > 1 ? `, up to ${g.max_picks}` : ""}`}</span>
            </legend>
            {g.options.map((o) => {
              const on = picks[g.name]?.includes(o.name) ?? false;
              return (
                <label key={o.id} className={`flex cursor-pointer items-center justify-between rounded-card border-[1.5px] px-4 py-3 ${on ? "border-peacock bg-peacock-mist" : "border-line"}`}>
                  <span className="flex items-center gap-3">
                    <input type={g.max_picks === 1 ? "radio" : "checkbox"} name={g.id} checked={on} onChange={() => toggle(g, o.name)} className="accent-[#0B5D66]" />
                    {o.name}
                  </span>
                  {Number(o.price) > 0 ? <span className="text-sm font-bold">+{money(Number(o.price), restaurant.currency, { decimals: 0 })}</span> : null}
                </label>
              );
            })}
          </fieldset>
        ))}
        <div className="flex items-center gap-4">
          <span className="text-sm font-extrabold">Quantity</span>
          <button type="button" aria-label="One less" onClick={() => setQty((q) => Math.max(1, q - 1))} className="h-10 w-10 rounded-pill border-[1.5px] border-line-strong text-xl font-bold">−</button>
          <span className="w-6 text-center font-extrabold tabular-nums">{qty}</span>
          <button type="button" aria-label="One more" onClick={() => setQty((q) => Math.min(20, q + 1))} className="h-10 w-10 rounded-pill border-[1.5px] border-line-strong text-xl font-bold">+</button>
        </div>
      </div>
    </Sheet>
  );
}

/** The bag beside the menu (desktop). */
export function BagPanel() {
  const ready = useHydrated();
  const { restaurant, lines, setQuantity } = useBag();
  if (!ready || !restaurant || !lines.length) {
    return <div className="rounded-card bg-white p-6 text-muted"><h2 className="mb-1 font-display text-xl font-semibold text-kohl">Your bag</h2>Pick a dish to start your order.</div>;
  }
  const subtotal = lines.reduce((a, l) => a + l.unitPrice * l.quantity, 0);
  return (
    <div className="rounded-card bg-white p-6">
      <h2 className="font-display text-xl font-semibold">Your bag</h2>
      <p className="mb-4 text-sm text-muted">from {restaurant.name}</p>
      <ul className="space-y-3">
        {lines.map((l) => (
          <li key={l.key} className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <p className="font-bold">{l.name}</p>
              {l.summary ? <p className="truncate text-sm text-muted">{l.summary}</p> : null}
            </div>
            <div className="flex items-center gap-2">
              <button type="button" aria-label={`One less ${l.name}`} onClick={() => setQuantity(l.key, l.quantity - 1)} className="h-8 w-8 rounded-pill border border-line-strong">−</button>
              <span className="w-4 text-center tabular-nums">{l.quantity}</span>
              <button type="button" aria-label={`One more ${l.name}`} onClick={() => setQuantity(l.key, l.quantity + 1)} className="h-8 w-8 rounded-pill border border-line-strong">+</button>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex justify-between border-t border-line pt-3 font-bold"><span>Food</span><span>{money(subtotal, restaurant.currency)}</span></div>
      <p className="mt-1 text-xs text-muted">Delivery, service and tax are worked out for your address at checkout — every one shown.</p>
      <Link href="/checkout" className="mt-4 flex h-14 items-center justify-center rounded-pill bg-peacock font-extrabold text-white hover:bg-peacock-deep">Go to checkout</Link>
    </div>
  );
}

function MobileBagBar() {
  const ready = useHydrated();
  const n = useBag((s) => s.lines.reduce((a, l) => a + l.quantity, 0));
  if (!ready || !n) return null;
  return (
    <Link href="/checkout" className="fixed inset-x-5 bottom-6 z-20 flex h-14 items-center justify-between rounded-pill bg-peacock px-6 font-extrabold text-white shadow-bar md:hidden">
      View bag · {n} {n === 1 ? "item" : "items"} <span aria-hidden>→</span>
    </Link>
  );
}
