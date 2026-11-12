"use client";
// CustomerCheckout.html on the web: the bag, where it goes, the tip, the fair
// bill from a live quote (the price is held while you pay), then pay.
import { errorMessage, unwrap, type CoreSchemas } from "@bhojango/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { api, cartItems, useBag, useHydrated, useSession } from "@/lib/client";
import { Button, FairBill, Segmented, Sheet } from "@bhojango/ui";
import { money } from "@bhojango/ui/bill";

type Quote = CoreSchemas["QuoteOut"];
type Address = { id: string; street: string; city: string; state?: string | null; postal_code?: string | null; country?: string | null;
  lat?: number | null; lng?: number | null; label?: string | null };
type Where = { addressId?: string; lat?: number; lng?: number; street: string; city: string; state: string; zip: string; country: string };

const TIPS: Record<string, number[]> = { INR: [0, 10, 20, 30], USD: [0, 2, 3, 5] };

export default function Checkout() {
  const ready = useHydrated();
  const router = useRouter();
  const user = useSession((s) => s.user);
  const bag = useBag();
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [where, setWhere] = useState<Where | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const currency = bag.restaurant?.currency ?? "INR";

  useEffect(() => {
    if (!ready || !user) return;
    api.core.GET("/api/v1/me/addresses").then((r) => {
      const list = (unwrap(r) as Address[]).filter((a) => a.lat != null);
      setAddresses(list);
      const sameCity = list.find((a) => a.city === bag.restaurant?.city) ?? list[0];
      if (sameCity) setWhere((w) => w ?? fromAddress(sameCity));
    }).catch(() => setAddresses([]));
  }, [ready, user, bag.restaurant?.city]);

  const lines = bag.lines;
  const key = useMemo(() => JSON.stringify([bag.restaurant?.id, lines, bag.tip, where]), [bag.restaurant?.id, lines, bag.tip, where]);
  useEffect(() => {
    if (!user || !bag.restaurant || !where || !lines.length) return;
    let live = true;
    api.core.POST("/api/v1/pricing/quote", { body: {
      restaurant_id: bag.restaurant.id, items: cartItems(lines), tip: bag.tip,
      deliver_to: where.addressId ? { address_id: where.addressId } : { lat: where.lat!, lng: where.lng! },
    } }).then((r) => {
      if (!live) return;
      setQuote(unwrap(r));
      setError(null);
    }).catch((e) => {
      if (!live) return;
      setQuote(null);
      setError(errorMessage((e as { body?: unknown }).body));
    });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, user]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (!ready) return <div className="mx-auto max-w-content px-5 py-14 text-muted">Loading your bag…</div>;
  if (!lines.length || !bag.restaurant) {
    return (
      <div className="mx-auto max-w-md px-5 py-20 text-center">
        <h1 className="font-display text-3xl font-semibold">Your bag is empty</h1>
        <Link href="/" className="mt-6 inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white">Find something to eat</Link>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="mx-auto max-w-md px-5 py-20 text-center">
        <h1 className="font-display text-3xl font-semibold">Sign in to check out</h1>
        <p className="mt-2 text-muted">Your bag from {bag.restaurant.name} is saved.</p>
        <Link href="/sign-in?next=/checkout" className="mt-6 inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white">Sign in with your phone</Link>
      </div>
    );
  }

  const held = quote ? Math.max(0, Math.floor((Date.parse(quote.expires_at) - now) / 1000)) : 0;

  async function pay(outcome: "approve" | "decline") {
    if (!quote || !where || !bag.restaurant) return;
    setSheet(false);
    setPaying(true);
    setError(null);
    try {
      const order = unwrap(await api.core.POST("/api/v1/orders", {
        params: { header: { "X-Idempotency-Key": quote.quote_id } },
        body: {
          restaurant_id: bag.restaurant.id, items: cartItems(lines), payment_method: currency === "INR" ? "upi" : "card", quote_token: quote.token,
          delivery_address: { street: where.street, city: where.city, state: where.state, zip: where.zip || "000000", country: where.country,
            ...(where.lat != null ? { lat: where.lat, lng: where.lng } : {}) },
        },
      })) as { id: string };
      unwrap(await api.core.POST("/api/v1/payments/initiate", { body: {
        order_id: order.id, payment_method_type: currency === "INR" ? "upi" : "card", payment_method_id: outcome === "decline" ? "fake_decline" : "fake_ok" } }));
      // The provider's webhook places the order (or fails the payment) in a moment.
      for (let i = 0; i < 30; i++) {
        const s = unwrap(await api.core.GET("/api/v1/payments/orders/{order_id}/status", { params: { path: { order_id: order.id } } })) as unknown as { payment_status: string; failure_reason: string | null };
        if (s.payment_status === "succeeded") {
          bag.clear();
          router.push(`/orders/${order.id}`);
          return;
        }
        if (s.payment_status === "failed") {
          setError(`Your payment didn't go through${s.failure_reason ? ` (${s.failure_reason})` : ""}. You weren't charged; the price is held, so you can try again.`);
          return;
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
      setError("Your payment is taking longer than usual. We'll update your order when it's confirmed.");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, "Something went wrong. Please try again."));
    } finally {
      setPaying(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-content gap-8 px-5 py-10 md:grid-cols-[1fr_420px] md:px-8">
      <div className="space-y-6">
        <h1 className="font-display text-4xl font-semibold tracking-[-1px]">Checkout</h1>
        <section className="rounded-card bg-white p-6" aria-labelledby="bag-h">
          <h2 id="bag-h" className="mb-3 text-lg font-extrabold">Your bag · {bag.restaurant.name}</h2>
          <ul className="space-y-3">
            {lines.map((l) => (
              <li key={l.key} className="flex items-start gap-3">
                <div className="min-w-0 flex-1"><p className="font-bold">{l.name}</p>{l.summary ? <p className="text-sm text-muted">{l.summary}</p> : null}</div>
                <div className="flex items-center gap-2">
                  <button type="button" aria-label={`One less ${l.name}`} onClick={() => bag.setQuantity(l.key, l.quantity - 1)} className="h-9 w-9 rounded-pill border border-line-strong">−</button>
                  <span className="w-5 text-center tabular-nums">{l.quantity}</span>
                  <button type="button" aria-label={`One more ${l.name}`} onClick={() => bag.setQuantity(l.key, l.quantity + 1)} className="h-9 w-9 rounded-pill border border-line-strong">+</button>
                </div>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-card bg-white p-6" aria-labelledby="where-h">
          <h2 id="where-h" className="mb-3 text-lg font-extrabold">Deliver to</h2>
          <AddressPicker addresses={addresses} where={where} city={bag.restaurant.city} onChange={setWhere} />
        </section>
        <section className="rounded-card bg-white p-6" aria-labelledby="tip-h">
          <h2 id="tip-h" className="mb-1 text-lg font-extrabold">Tip your rider</h2>
          <p className="mb-3 text-sm text-muted">100% goes to your rider.</p>
          <Segmented label="Tip" value={String(bag.tip)} onChange={(v) => bag.setTip(Number(v))}
            options={(TIPS[currency] ?? TIPS.INR!).map((t) => ({ value: String(t), label: t === 0 ? "No tip" : money(t, currency, { decimals: 0 }) }))} />
        </section>
      </div>
      <aside className="space-y-4 md:sticky md:top-24 md:self-start">
        {quote ? <FairBill lines={quote.lines as never} currency={quote.currency} /> : (
          <div className="rounded-card bg-white p-6 text-muted">{where ? (error ? null : "Working out your bill…") : "Choose where it goes to see the whole bill."}</div>
        )}
        {quote ? <p className="text-center text-sm text-muted" aria-live="polite">{held > 0 ? `Price held for ${Math.floor(held / 60)}:${String(held % 60).padStart(2, "0")}` : "The price has expired; we'll work it out again."}</p> : null}
        {error ? <p role="alert" className="rounded-card bg-[#FBEAE8] p-4 text-sm font-semibold text-chili">{error}</p> : null}
        <Button block size="lg" loading={paying} disabled={!quote || held === 0} onClick={() => setSheet(true)}>
          {quote ? `Pay ${money(Number(quote.total), quote.currency)}` : "Pay"}
        </Button>
      </aside>
      <Sheet open={sheet} onClose={() => setSheet(false)} title="Pay (test mode)"
        footer={<div className="flex gap-3"><Button variant="secondary" onClick={() => pay("decline")}>Decline</Button><Button block onClick={() => pay("approve")}>Approve {quote ? money(Number(quote.total), quote.currency) : ""}</Button></div>}>
        <p className="text-muted">This stands in for {currency === "INR" ? "Razorpay Checkout (UPI, cards)" : "Stripe (cards, Apple Pay, Google Pay)"} until live keys are set. Nothing is charged.</p>
      </Sheet>
    </div>
  );
}

function fromAddress(a: Address): Where {
  return { addressId: a.id, street: a.street, city: a.city, state: a.state ?? "", zip: a.postal_code ?? "", country: a.country ?? "IN" };
}

function AddressPicker({ addresses, where, city, onChange }: { addresses: Address[] | null; where: Where | null; city: string; onChange: (w: Where) => void }) {
  const [street, setStreet] = useState("");
  const [locating, setLocating] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  function here() {
    setMsg(null);
    if (!navigator.geolocation) return setMsg("Your browser can't share your location.");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLocating(false);
        onChange({ lat: p.coords.latitude, lng: p.coords.longitude, street: street || "Current location", city, state: "", zip: "", country: city === "Boise" ? "US" : "IN" });
      },
      () => {
        setLocating(false);
        setMsg("We couldn't get your location. Allow it in the browser, or choose a saved address.");
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }
  return (
    <div className="space-y-3">
      {(addresses ?? []).map((a) => {
        const on = where?.addressId === a.id;
        return (
          <label key={a.id} className={`flex cursor-pointer items-start gap-3 rounded-card border-[1.5px] p-4 ${on ? "border-peacock bg-peacock-mist" : "border-line"}`}>
            <input type="radio" name="address" checked={on} onChange={() => onChange(fromAddress(a))} className="mt-1 accent-[#0B5D66]" />
            <span><b className="block">{a.label ?? "Saved address"}</b><span className="text-sm text-muted">{a.street}, {a.city}</span></span>
          </label>
        );
      })}
      <div className="rounded-card border-[1.5px] border-dashed border-line-strong p-4">
        <p className="mb-2 text-sm font-bold">Somewhere else</p>
        <div className="flex flex-wrap gap-2">
          <input aria-label="Flat, building and street" placeholder="Flat, building and street" value={street} onChange={(e) => setStreet(e.target.value)}
            className="h-12 min-w-0 flex-1 rounded-card border-[1.5px] border-line-strong px-3" />
          <Button variant="secondary" loading={locating} onClick={here}>Use my location</Button>
        </div>
        {where && !where.addressId ? <p className="mt-2 text-sm text-peacock">Delivering to your current location{where.street !== "Current location" ? ` · ${where.street}` : ""}.</p> : null}
        {msg ? <p className="mt-2 text-sm text-chili">{msg}</p> : null}
      </div>
    </div>
  );
}
