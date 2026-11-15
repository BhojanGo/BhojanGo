"use client";
// WebCheckout / MWebCheckout: where it goes, when, the tip, how to pay, and the
// fair bill from a live quote (the price is held while you pay). Placing the
// order uses the quote's token and an idempotency key; paying opens the
// checkout the gateway asks for (pay.ts); then the live tracking page.
import { errorMessage, unwrap, type CoreSchemas } from "@bhojango/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { km } from "@/components/discover/places";
import { FairBill } from "@/components/FairBill";
import { Check, Clock, Close, Pin } from "@/components/Icons";
import { foodSubtotal, useQuote, type DeliverTo } from "@/components/order/useQuote";
import { api, authed, cartItems, useBag, useHydrated, useSession } from "@/lib/client";
import { tipPresetsOf, type TipPresets } from "@/lib/contract";
import { photo } from "@/lib/format";
import { useFormat, useT } from "@/lib/i18n";
import type { Place } from "@/lib/prefs";
import { slugify } from "../[country]/[city]/[kitchen]/data";
import { completeFake, mountStripe, payWithRazorpay, waitForPayment, type PayType } from "./pay";

type Restaurant = CoreSchemas["PublicRestaurant"];
interface Address {
  id: string;
  label?: string | null;
  street: string;
  city: string;
  state?: string | null;
  postal_code?: string | null;
  country: string;
  lat?: number | null;
  lng?: number | null;
  is_default?: boolean;
  delivery_notes?: string | null;
}
interface SavedMethod {
  id: string;
  provider?: string;
  provider_token?: string | null;
  brand?: string | null;
  last4?: string | null;
  exp_month?: number | null;
  exp_year?: number | null;
  is_default?: boolean;
  type?: string | null;
}
type Method = { key: string; type: PayType; token: string | null; title: string; sub: string };

const NEAR_KM = 1.5; // a saved address this close to the area picked in the header is "there"

// How people pay in each country (the gateway's own list decides inside its sheet).
// Markets' payment methods -> the web's payment flows: wallets in a card sheet (Apple
// Pay, Google Pay) go through the card flow; methods the web can't take yet are left out.
const FLOW: Record<string, PayType> = { card: "card", apple_pay: "card", google_pay: "card", upi: "upi", net_banking: "net_banking" };
function flowsFor(methods: string[] | undefined): PayType[] {
  const out: PayType[] = [];
  for (const m of methods ?? ["card"]) {
    const f = FLOW[m];
    if (f && !out.includes(f)) out.push(f);
  }
  return out.length ? out : ["card"];
}

const card = "rounded-[24px] border border-[#E2E7E8] bg-white p-5 md:p-6";

function StepHead({ n, done, title, action }: { n: number; done: boolean; title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-[14px]">
      <span aria-hidden="true" className={`hidden h-8 w-8 shrink-0 items-center justify-center rounded-full text-label text-white md:flex ${done ? "bg-[#0B5D66]" : "bg-[#111418]"}`}>
        {done ? <Check color="#FFFFFF" /> : n}
      </span>
      <h2 className="m-0 flex-grow text-h2 tracking-[-0.4px]">{title}</h2>
      {action}
    </div>
  );
}

function Radio({ on }: { on: boolean }) {
  return (
    <span aria-hidden="true" className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border-2 ${on ? "border-[#0B5D66]" : "border-[#C9D3D4]"}`}>
      {on && <span className="h-3 w-3 rounded-full bg-[#0B5D66]" />}
    </span>
  );
}

export function Checkout({ place, countryMethods }: { place: Place | null; countryMethods: Record<string, string[]> }) {
  const t = useT();
  const f = useFormat();
  const router = useRouter();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const bag = useBag();
  const [rest, setRest] = useState<Restaurant | null>(null);
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [saved, setSaved] = useState<SavedMethod[]>([]);
  const [choice, setChoice] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [street, setStreet] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [promoInput, setPromoInput] = useState("");
  const [promo, setPromo] = useState<string | null>(null);
  const [other, setOther] = useState(false);
  const [method, setMethod] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<{ id: string; quoteId: string } | null>(null);
  const [fake, setFake] = useState<{ orderId: string; checkout: Record<string, unknown> } | null>(null);
  const [stripe, setStripe] = useState<{ orderId: string; checkout: Record<string, unknown> } | null>(null);

  // Signed in only.
  useEffect(() => {
    if (hydrated && !user) router.replace("/signin?next=/checkout");
  }, [hydrated, user, router]);

  const slug = bag.restaurant?.slug;
  useEffect(() => {
    if (!slug) return;
    api.core.GET("/api/v1/restaurants/by-slug/{slug}", { params: { path: { slug } } }).then((r) => setRest(unwrap(r))).catch(() => undefined);
  }, [slug]);

  useEffect(() => {
    if (!hydrated || !user) return;
    authed<Address[]>("GET", "/api/v1/me/addresses").then(setAddresses).catch(() => setAddresses([]));
    authed<SavedMethod[] | { methods: SavedMethod[] }>("GET", "/api/v1/me/payment-methods")
      .then((r) => setSaved(Array.isArray(r) ? r : r.methods ?? []))
      .catch(() => undefined); // not every backend has saved methods yet
  }, [hydrated, user]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Where: the chosen one, else the address in the header, else the default saved one.
  // An area picked in the header with a saved address in it (within NEAR_KM) means
  // that saved address: it has the flat and street the rider needs.
  const list = addresses ?? [];
  const placeIsSaved = !!place?.address_id && list.some((a) => a.id === place.address_id);
  const savedNear = place && !place.address_id
    ? [...list].sort((a, b) => Number(!!b.is_default) - Number(!!a.is_default)).find((a) => a.lat != null && a.lng != null && km(place, { lat: a.lat, lng: a.lng }) <= NEAR_KM)
    : undefined;
  const fallback = place?.address_id && placeIsSaved ? place.address_id : savedNear ? savedNear.id : place ? "place" : (list.find((a) => a.is_default) ?? list[0])?.id ?? null;
  const picked = choice ?? fallback;
  const address = picked && picked !== "place" ? list.find((a) => a.id === picked) ?? null : null;
  const usingPlace = picked === "place" && !!place;
  const deliverTo: DeliverTo | null = address ? { address_id: address.id } : usingPlace && place ? (place.address_id ? { address_id: place.address_id } : { lat: place.lat, lng: place.lng }) : null;
  const riderNote = note ?? address?.delivery_notes ?? "";

  const lines = bag.lines;
  const subtotal = foodSubtotal(lines);
  const quote = useQuote({ enabled: hydrated && !!user, restaurantId: bag.restaurant?.id, lines, deliverTo, tip: bag.tip, promo, nonce, fallbackError: t("common.error") });
  const q = quote.quote;
  const money = (n: number | string, whole = false) => f.money(n, bag.restaurant?.currency ?? q?.currency, { whole });
  const held = q ? Math.max(0, Math.floor((Date.parse(q.expires_at) - now) / 1000)) : 0;
  // Tip choices are the city's, from the quote, or from a refusal that knows them (a bag
  // under the minimum); kept while the next quote loads. None set: "Other" only.
  const [tipCfg, setTipCfg] = useState<TipPresets | null>(null);
  const [tipTouched, setTipTouched] = useState(false);
  const refused = quote.refusal;
  const fromQuote = q ? tipPresetsOf(q) : refused && "tip_presets" in refused ? tipPresetsOf(refused) : undefined;
  if (fromQuote !== undefined && JSON.stringify(fromQuote) !== JSON.stringify(tipCfg)) setTipCfg(fromQuote);
  const presets = useMemo(() => [...new Set((tipCfg?.amounts ?? []).map(Number).filter((n) => Number.isFinite(n) && n > 0))], [tipCfg]);
  const setTip = bag.setTip;
  const tipNow = bag.tip;
  useEffect(() => {
    // The city's suggested tip, until the customer picks one themselves.
    if (tipTouched || !tipCfg || tipNow !== 0 || tipCfg.default_index == null) return;
    const n = Number(tipCfg.amounts[tipCfg.default_index]);
    if (Number.isFinite(n) && n > 0) setTip(n);
  }, [tipCfg, tipTouched, tipNow, setTip]);

  const methods: Method[] = useMemo(() => {
    const out: Method[] = saved.map((m) => {
      const upi = (m.type ?? m.brand ?? "").toLowerCase() === "upi";
      return {
        key: `saved:${m.id}`,
        type: upi ? "upi" : "card",
        token: m.provider_token ?? m.id,
        title: upi ? t("checkout.saved_upi", { id: m.last4 ?? "" }) : t("checkout.card_ending", { brand: m.brand ?? "", last4: m.last4 ?? "" }),
        sub: m.exp_month && m.exp_year ? t("checkout.expires", { date: `${String(m.exp_month).padStart(2, "0")}/${String(m.exp_year).slice(-2)}` }) : upi ? t("checkout.method_upi_sub") : "",
      };
    });
    for (const type of flowsFor(countryMethods[rest?.country ?? ""])) {
      out.push({ key: `new:${type}`, type, token: null, title: t(`checkout.method_${type}`), sub: t(`checkout.method_${type}_sub`) });
    }
    return out;
  }, [saved, rest?.country, t, countryMethods]);
  const defaultMethod = saved.find((m) => m.is_default) ? `saved:${saved.find((m) => m.is_default)!.id}` : methods[0]?.key;
  const chosen = methods.find((m) => m.key === (method ?? defaultMethod)) ?? methods[0];

  if (!hydrated || !user) return <div className="mx-auto max-w-[1440px] px-5 py-14 text-[#4C5A5E] md:px-16">{t("common.loading")}</div>;
  if (!lines.length || !bag.restaurant) {
    return (
      <div className="mx-auto max-w-md px-5 py-20 text-center">
        <h1 className="text-h1">{t("checkout.empty_title")}</h1>
        <p className="mt-2 text-[#4C5A5E]">{t("checkout.empty_body")}</p>
        <Link href="/" className="mt-6 inline-flex h-12 items-center rounded-full bg-[#0B5D66] px-6 font-bold text-white hover:text-white">{t("checkout.find_food")}</Link>
      </div>
    );
  }
  const kitchen = bag.restaurant;
  const kitchenPath = rest ? `/${rest.country.toLowerCase()}/${slugify(rest.city)}/${rest.slug}` : "/";
  const area = (rest?.address as { landmark?: string } | undefined)?.landmark;
  const count = lines.reduce((n, l) => n + l.quantity, 0);
  const arrive = rest
    // on the kitchen's city clock (where the order is cooked and delivered), not the device's
    ? t("checkout.arrives", { from: f.zone(rest.time_zone).time(new Date(now + rest.delivery_time_min * 60000)), to: f.zone(rest.time_zone).time(new Date(now + rest.delivery_time_max * 60000)) })
    : null;
  const distance = q ? t(q.distance_unit === "mi" ? "common.mi" : "common.km", { n: q.distance }) : null;
  const placeLine = (a: Address) => [a.label, a.street].filter(Boolean).join(" · ");

  async function settle(orderId: string) {
    const s = await waitForPayment(orderId);
    if (s.payment_status === "succeeded") {
      bag.clear();
      router.push(`/orders/${orderId}/track`);
      return;
    }
    if (s.payment_status === "failed") setError(s.failure_reason ? t("checkout.payment_failed_reason", { reason: s.failure_reason }) : t("checkout.payment_failed"));
    else setError(t("checkout.payment_slow"));
  }

  async function pay() {
    if (!q || !deliverTo || !chosen) return;
    setBusy(true);
    setError(null);
    try {
      let orderId = order?.quoteId === q.quote_id ? order.id : null;
      if (!orderId) {
        const where = address
          ? { street: address.street, city: address.city, state: address.state ?? "", zip: address.postal_code ?? "", country: address.country, ...(address.lat != null && address.lng != null ? { lat: address.lat, lng: address.lng } : {}) }
          : { street: street.trim() || place!.label, city: kitchen.city, state: "", zip: "", country: place!.country, lat: place!.lat, lng: place!.lng, landmark: place!.zone ?? null };
        const created = unwrap(
          await api.core.POST("/api/v1/orders", {
            params: { header: { "X-Idempotency-Key": q.quote_id } },
            body: {
              restaurant_id: kitchen.id,
              items: cartItems(lines),
              payment_method: chosen.type,
              quote_token: q.token,
              delivery_address: where,
              ...(promo ? { promo_code: promo } : {}),
              ...(riderNote.trim() ? { special_instructions: riderNote.trim() } : {}),
            },
          }),
        ) as { id: string };
        orderId = created.id;
        setOrder({ id: orderId, quoteId: q.quote_id });
      }
      const init = unwrap(
        await api.core.POST("/api/v1/payments/initiate", {
          body: { order_id: orderId, payment_method_type: chosen.type, ...(chosen.token ? { payment_method_id: chosen.token } : {}) },
        }),
      );
      const c = (init.checkout ?? {}) as Record<string, unknown>;
      if (init.provider === "fake" || c.sdk === "fake") {
        setFake({ orderId, checkout: c });
        return;
      }
      if (c.sdk === "stripe_payment_sheet") {
        setStripe({ orderId, checkout: c });
        return;
      }
      if (c.sdk === "razorpay_checkout") await payWithRazorpay(c, t("checkout.payment_cancelled"));
      await settle(orderId);
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, (e as Error).message || t("common.error")));
    } finally {
      setBusy(false);
    }
  }

  async function finishFake(outcome: "succeeded" | "failed") {
    if (!fake) return;
    const { orderId, checkout } = fake;
    setFake(null);
    setBusy(true);
    try {
      await completeFake(checkout, outcome);
      await settle(orderId);
    } catch (e) {
      setError((e as Error).message || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const payLabel = q ? t("checkout.pay_with", { amount: f.money(q.total, q.currency), method: chosen ? t(`checkout.short_${chosen.type}`) : "" }) : t("checkout.pay");
  const canPay = !!q && held > 0 && !busy && !!chosen;

  const bill = (
    <>
      <div className="mb-2 text-caption text-[#4C5A5E]">{t("checkout.fair_bill")}</div>
      {q ? (
        <FairBill lines={q.lines} total={q.total} currency={q.currency} formatLocale={f.formatLocale} t={t} distance={distance} totalLabel={t("checkout.you_pay")} compact />
      ) : (
        <div>
          <div className="flex justify-between text-body"><span>{t("bill.line_food")}</span><b className="tabular-nums">{money(subtotal)}</b></div>
          <p className="mt-2 text-small text-[#4C5A5E]" aria-live="polite">{quote.loading ? t("checkout.working_out") : quote.error ?? (deliverTo ? t("checkout.working_out") : t("checkout.choose_address"))}</p>
        </div>
      )}
    </>
  );

  return (
    <div className="mx-auto max-w-[1440px] px-5 pb-32 pt-4 md:px-16 md:pb-20 md:pt-6">
      <div className="mb-4 flex items-center justify-between text-body">
        <Link href={kitchenPath} className="inline-flex items-center gap-2 font-bold text-[#0B5D66]">
          <span aria-hidden="true">←</span> {t("checkout.back_to_menu")}
        </Link>
        <span className="hidden items-center gap-2 text-[#4C5A5E] md:flex">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>
          {t("checkout.secure")}
        </span>
      </div>
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_460px] md:gap-10">
        <div className="flex flex-col gap-4">
          <h1 className="m-0 text-h1 tracking-[-0.8px] md:tracking-[-1.2px]">{t("checkout.title")}</h1>

          {/* where */}
          <section className={card} aria-labelledby="where-h">
            <StepHead
              n={1}
              done={!!deliverTo}
              title={t("checkout.deliver_to")}
              action={deliverTo && (list.length > 0 || place) ? <button type="button" aria-expanded={editing} onClick={() => setEditing((e) => !e)} className="font-bold text-[#0B5D66]">{editing ? t("checkout.done") : t("checkout.change")}</button> : null}
            />
            <span id="where-h" className="sr-only">{t("checkout.deliver_to")}</span>
            <div className="mt-3 md:pl-[46px]">
              {!editing && deliverTo ? (
                <div className="flex items-start gap-3">
                  <span className="mt-[2px] md:hidden"><Pin size={20} color="#0B5D66" /></span>
                  <span>
                    <b className="block text-label">{address ? placeLine(address) : place?.label}</b>
                    <span className="text-small text-[#4C5A5E]">{[address?.delivery_notes, distance ? t("checkout.from_kitchen", { distance }) : null, arrive].filter(Boolean).join(" · ")}</span>
                  </span>
                </div>
              ) : (
                <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
                  <legend className="sr-only">{t("checkout.deliver_to")}</legend>
                  {place && !placeIsSaved && (
                    <label className={`flex cursor-pointer items-center gap-3 rounded-2xl border-[1.5px] p-4 ${picked === "place" ? "border-[#0B5D66] bg-[#EFF6F6]" : "border-[#E2E7E8]"}`}>
                      <input type="radio" name="where" className="peer sr-only" checked={picked === "place"} onChange={() => { setChoice("place"); setNote(null); }} />
                      <Radio on={picked === "place"} />
                      <span><b className="block">{place.label}</b><span className="text-small text-[#4C5A5E]">{t("checkout.the_area_you_chose")}</span></span>
                    </label>
                  )}
                  {list.map((a) => (
                    <label key={a.id} className={`flex cursor-pointer items-center gap-3 rounded-2xl border-[1.5px] p-4 ${picked === a.id ? "border-[#0B5D66] bg-[#EFF6F6]" : "border-[#E2E7E8]"}`}>
                      <input type="radio" name="where" className="peer sr-only" checked={picked === a.id} onChange={() => { setChoice(a.id); setNote(null); }} />
                      <Radio on={picked === a.id} />
                      <span><b className="block">{placeLine(a)}</b><span className="text-small text-[#4C5A5E]">{[a.city, a.delivery_notes].filter(Boolean).join(" · ")}</span></span>
                    </label>
                  ))}
                  {!place && list.length === 0 && addresses !== null && <p className="m-0 text-body text-[#4C5A5E]">{t("checkout.no_address")}</p>}
                </fieldset>
              )}
              {usingPlace && (
                <label className="mt-3 block">
                  <span className="sr-only">{t("checkout.street")}</span>
                  <input value={street} onChange={(e) => setStreet(e.target.value)} placeholder={t("checkout.street")} autoComplete="address-line1" className="h-12 w-full rounded-[14px] border border-[#C9D3D4] px-[14px] text-body outline-none focus:border-[#0B5D66]" />
                </label>
              )}
              {deliverTo && (
                <label className="mt-3 hidden md:block">
                  <span className="sr-only">{t("checkout.rider_note")}</span>
                  <input value={riderNote} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder={t("checkout.rider_note")} className="h-12 w-full rounded-[14px] border border-[#C9D3D4] px-[14px] text-body outline-none focus:border-[#0B5D66]" />
                </label>
              )}
            </div>
          </section>

          {/* when */}
          <section className={`${card} hidden md:block`} aria-label={t("checkout.when")}>
            <StepHead n={2} done title={t("checkout.when")} />
            <div className="mt-4 pl-[46px]">
              <div className="flex max-w-[350px] items-center gap-3 rounded-2xl border-2 border-[#0B5D66] bg-[#EFF6F6] px-4 py-3">
                <Radio on />
                <span><b className="block">{t("checkout.asap")}</b>{arrive && <span className="text-small text-[#4C5A5E]">{arrive}</span>}</span>
              </div>
            </div>
          </section>

          {/* tip */}
          <section className={card} aria-labelledby="tip-h">
            <StepHead n={3} done={false} title={t("checkout.tip_title")} />
            <span id="tip-h" className="sr-only">{t("checkout.tip_title")}</span>
            <div className="mt-4 flex flex-wrap gap-2 md:gap-[10px] md:pl-[46px]" role="radiogroup" aria-label={t("checkout.tip_title")}>
              {[0, ...presets].map((n) => {
                const on = !other && bag.tip === n;
                return (
                  <button key={n} type="button" role="radio" aria-checked={on} onClick={() => { setTipTouched(true); setOther(false); bag.setTip(n); }} className={`h-11 rounded-full px-4 text-label tabular-nums md:h-[50px] md:px-5 ${on ? "bg-[#111418] text-white" : "border-[1.5px] border-[#C9D3D4] bg-white"}`}>
                    {n === 0 ? t("checkout.tip_none") : money(n, true)}
                  </button>
                );
              })}
              <button type="button" role="radio" aria-checked={other} onClick={() => { setTipTouched(true); setOther(true); }} className={`h-11 rounded-full px-4 text-label md:h-[50px] md:px-5 ${other ? "bg-[#111418] text-white" : "border-[1.5px] border-[#C9D3D4] bg-white"}`}>
                {t("checkout.tip_other")}
              </button>
              {other && (
                <label className="flex h-11 items-center gap-2 rounded-full border-[1.5px] border-[#0B5D66] px-4 md:h-[50px]">
                  <span className="sr-only">{t("checkout.tip_amount")}</span>
                  <input type="number" min={0} step="any" inputMode="decimal" autoFocus value={bag.tip || ""} onChange={(e) => bag.setTip(Math.max(0, Number(e.target.value) || 0))} placeholder={t("checkout.tip_amount")} className="w-24 bg-transparent text-label outline-none" />
                </label>
              )}
            </div>
            <p className="m-0 mt-3 text-body text-[#4C5A5E] md:pl-[46px]">{t("checkout.tip_note")}</p>
          </section>

          {/* the bill (phone) */}
          <section className={`${card} md:hidden`} aria-label={t("checkout.fair_bill")}>{bill}</section>

          {/* pay with */}
          <section className={card} aria-labelledby="pay-h">
            <StepHead n={4} done={false} title={t("checkout.pay_with_title")} />
            <span id="pay-h" className="sr-only">{t("checkout.pay_with_title")}</span>
            <fieldset className="m-0 mt-4 flex flex-col gap-[10px] border-0 p-0 md:pl-[46px]">
              <legend className="sr-only">{t("checkout.pay_with_title")}</legend>
              {methods.map((m) => {
                const on = chosen?.key === m.key;
                return (
                  <label key={m.key} className={`flex cursor-pointer items-center gap-[14px] rounded-[18px] px-4 py-[14px] ${on ? "border-2 border-[#0B5D66] bg-[#EFF6F6]" : "border border-[#E2E7E8]"}`}>
                    <input type="radio" name="method" className="sr-only" checked={on} onChange={() => setMethod(m.key)} />
                    <Radio on={on} />
                    <span><b className="block text-h3">{m.title}</b>{m.sub && <span className="text-small text-[#24383B]">{m.sub}</span>}</span>
                  </label>
                );
              })}
            </fieldset>
          </section>
          {/* rider note (phone) */}
          {deliverTo && (
            <label className="md:hidden">
              <span className="sr-only">{t("checkout.rider_note")}</span>
              <input value={riderNote} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder={t("checkout.rider_note")} className="h-12 w-full rounded-[14px] border border-[#C9D3D4] px-[14px] text-body outline-none focus:border-[#0B5D66]" />
            </label>
          )}
        </div>

        {/* summary */}
        <aside className="md:sticky md:top-[100px] md:self-start" aria-label={t("checkout.summary")}>
          <div className="overflow-hidden rounded-[24px] border border-[#E2E7E8]">
            <div className="hidden items-center gap-[14px] bg-[#F4F6F6] px-5 py-[18px] md:flex">
              <span className="h-14 w-14 shrink-0 overflow-hidden rounded-[14px] bg-[#DDEBEC]">
                {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
                {rest && photo(rest.logo_url ?? rest.cover_url, 400) && <img src={photo(rest.logo_url ?? rest.cover_url, 400)!} alt="" className="h-full w-full object-cover" />}
              </span>
              <span>
                <b className="block text-h3">{kitchen.name}</b>
                <span className="text-small text-[#4C5A5E]">{[t("kitchen.items", { count }), area].filter(Boolean).join(" · ")}</span>
              </span>
            </div>
            <div className="p-5">
              <ul className="m-0 hidden list-none flex-col gap-2 p-0 text-body md:flex">
                {lines.map((l) => (
                  <li key={l.key} className="flex gap-3">
                    <span className="flex-grow">{t("kitchen.line", { count: l.quantity, name: l.name })}{l.summary && <span className="text-[#4C5A5E]"> · {l.summary}</span>}</span>
                    <b className="tabular-nums">{money(l.unitPrice * l.quantity, true)}</b>
                  </li>
                ))}
              </ul>
              <div className="mb-4 mt-4 rounded-[14px] border border-dashed border-[#C9D3D4] px-4 py-3 text-body">
                {promo ? (
                  <div className="flex items-center gap-2">
                    <Check color="#0B5D66" />
                    <span className="flex-grow"><b>{promo}</b> {quote.error ? "" : t("checkout.promo_applied")}</span>
                    <button type="button" onClick={() => setPromo(null)} className="font-bold text-[#0B5D66]">{t("checkout.remove")}</button>
                  </div>
                ) : (
                  <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (promoInput.trim()) setPromo(promoInput.trim().toUpperCase()); }}>
                    <label className="flex-grow">
                      <span className="sr-only">{t("checkout.promo")}</span>
                      <input value={promoInput} onChange={(e) => setPromoInput(e.target.value)} placeholder={t("checkout.promo")} className="w-full bg-transparent uppercase outline-none placeholder:normal-case" />
                    </label>
                    <button type="submit" className="font-bold text-[#0B5D66]">{t("checkout.apply")}</button>
                  </form>
                )}
              </div>
              <div className="hidden md:block">{bill}</div>
              {q && (
                <p className="m-0 mt-4 flex items-center gap-2 rounded-xl bg-[#EFF6F6] px-4 py-[10px] text-small text-[#24383B]" aria-live="off">
                  <Clock size={14} />
                  {held > 0 ? t("checkout.held", { time: `${Math.floor(held / 60)}:${String(held % 60).padStart(2, "0")}` }) : t("checkout.expired")}
                </p>
              )}
              {error && <p role="alert" className="m-0 mt-3 rounded-xl bg-[#F1E3E1] px-4 py-3 text-label text-[#8C1D18]">{error}</p>}
              <div className="fixed inset-x-4 bottom-4 z-40 md:static md:mt-4">
                {q && held === 0 ? (
                  <button type="button" onClick={() => setNonce((n) => n + 1)} className="h-[60px] w-full rounded-full bg-[#0B5D66] text-h3 text-white shadow-[0_10px_30px_rgba(11,93,102,0.3)] md:shadow-none">{t("checkout.fresh_price")}</button>
                ) : (
                  <button type="button" disabled={!canPay} onClick={() => void pay()} aria-busy={busy} className="h-[60px] w-full rounded-full bg-[#0B5D66] text-h3 tabular-nums text-white shadow-[0_10px_30px_rgba(11,93,102,0.3)] hover:bg-[#083F46] disabled:bg-[#8FB3B7] md:shadow-none">
                    {busy ? t("checkout.paying") : payLabel}
                  </button>
                )}
              </div>
            </div>
          </div>
        </aside>
      </div>

      {fake && <FakePay amount={q ? f.money(q.total, q.currency) : ""} onClose={() => setFake(null)} onOutcome={(o) => void finishFake(o)} />}
      {stripe && (
        <StripePay
          checkout={stripe.checkout}
          returnUrl={`${typeof window !== "undefined" ? window.location.origin : ""}/orders/${stripe.orderId}/track`}
          amount={q ? f.money(q.total, q.currency) : ""}
          onClose={() => setStripe(null)}
          onPaid={() => {
            const id = stripe.orderId;
            setStripe(null);
            setBusy(true);
            void settle(id).finally(() => setBusy(false));
          }}
        />
      )}
    </div>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const t = useT();
  const id = useId();
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-[rgba(17,20,24,0.5)] md:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby={id} onClick={(e) => e.stopPropagation()} className="w-full rounded-t-[28px] bg-white p-6 md:w-[480px] md:rounded-[28px]">
        <div className="mb-3 flex items-center">
          <h2 id={id} className="m-0 flex-grow text-h2">{title}</h2>
          <button type="button" aria-label={t("common.close")} onClick={onClose}><Close color="#4C5A5E" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** The local fake gateway's checkout (no keys, nothing charged). */
function FakePay({ amount, onClose, onOutcome }: { amount: string; onClose: () => void; onOutcome: (o: "succeeded" | "failed") => void }) {
  const t = useT();
  return (
    <Modal title={t("checkout.test_title")} onClose={onClose}>
      <p className="m-0 text-body text-[#4C5A5E]">{t("checkout.test_body")}</p>
      <div className="mt-6 flex gap-3">
        <button type="button" onClick={() => onOutcome("failed")} className="h-12 flex-1 rounded-full border-[1.5px] border-[#C9D3D4] font-bold">{t("checkout.test_decline")}</button>
        <button type="button" autoFocus onClick={() => onOutcome("succeeded")} className="h-12 flex-[2] rounded-full bg-[#0B5D66] text-label tabular-nums text-white">{t("checkout.test_approve", { amount })}</button>
      </div>
    </Modal>
  );
}

/** Stripe's Payment Element (cards, Apple Pay, Google Pay) in a dialog. */
function StripePay({ checkout, returnUrl, amount, onClose, onPaid }: { checkout: Record<string, unknown>; returnUrl: string; amount: string; onClose: () => void; onPaid: () => void }) {
  const t = useT();
  const box = useRef<HTMLDivElement>(null);
  const handle = useRef<Awaited<ReturnType<typeof mountStripe>> | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    if (!box.current) return;
    mountStripe(checkout, box.current)
      .then((h) => {
        if (!live) return h.destroy();
        handle.current = h;
        setReady(true);
      })
      .catch(() => live && setError(t("common.error")));
    return () => {
      live = false;
      handle.current?.destroy();
    };
  }, [checkout, t]);
  async function confirm() {
    if (!handle.current) return;
    setBusy(true);
    setError(null);
    try {
      await handle.current.confirm(returnUrl);
      onPaid();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={t("checkout.card_title")} onClose={onClose}>
      <div ref={box} className="min-h-[120px]" />
      {error && <p role="alert" className="mt-3 text-label text-[#8C1D18]">{error}</p>}
      <button type="button" disabled={!ready || busy} onClick={() => void confirm()} className="mt-5 h-14 w-full rounded-full bg-[#0B5D66] text-label tabular-nums text-white disabled:bg-[#8FB3B7]">
        {busy ? t("checkout.paying") : t("checkout.pay_amount", { amount })}
      </button>
    </Modal>
  );
}
