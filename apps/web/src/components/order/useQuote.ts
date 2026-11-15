"use client";
// A live quote for the bag (the fair bill): POST /pricing/quote whenever the
// bag, the address, the tip or the promo code changes. Amounts are the
// engine's; nothing is computed here. A quote that belongs to an older bag is
// never shown (it is keyed by the request it answered).
import { errorMessage, quoteRefusal, unwrap, type CoreSchemas, type QuoteRefusal } from "@bhojango/api-client";
import { useEffect, useState } from "react";

import { api, cartItems, type BagLine } from "@/lib/client";
import { useFormat, useT } from "@/lib/i18n";

export type Quote = CoreSchemas["QuoteOut"];
export type DeliverTo = { address_id: string } | { lat: number; lng: number };

export function useQuote(opts: {
  enabled: boolean;
  restaurantId: string | null | undefined;
  lines: BagLine[];
  deliverTo: DeliverTo | null;
  tip?: number;
  promo?: string | null;
  nonce?: number; // bump to ask again (an expired price)
  fallbackError: string;
}) {
  const { enabled, restaurantId, lines, deliverTo, tip, promo, nonce, fallbackError } = opts;
  const body =
    enabled && restaurantId && deliverTo && lines.length
      ? { restaurant_id: restaurantId, items: cartItems(lines), deliver_to: deliverTo, tip: tip ?? 0, ...(promo ? { promo_code: promo } : {}) }
      : null;
  const key = body ? JSON.stringify([body, nonce ?? 0]) : null;
  const t = useT();
  const f = useFormat();
  const [res, setRes] = useState<{ key: string; quote?: Quote; error?: string; refusal?: QuoteRefusal | null } | null>(null);

  useEffect(() => {
    if (!key) return;
    let live = true;
    const [request] = JSON.parse(key) as [CoreSchemas["QuoteRequest"]];
    const timer = setTimeout(() => {
      api.core
        .POST("/api/v1/pricing/quote", { body: request })
        .then((r) => live && setRes({ key, quote: unwrap(r) }))
        .catch((e: unknown) => {
          const b = (e as { body?: unknown }).body;
          if (live) setRes({ key, error: errorMessage(b, fallbackError), refusal: quoteRefusal(b) });
        });
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [key, fallbackError]);

  const fresh = res && key && res.key === key ? res : null;
  // refusal: why the API said no (MIN_ORDER with zone, amount, currency; the city's tip_presets).
  // A bag under the minimum is worded here, in the visitor's language, with the amount
  // in the country's format (whole amounts without ".00"); anything else shows the API's message.
  const refusal = fresh?.refusal ?? null;
  const error =
    refusal?.code === "MIN_ORDER" && refusal.zone && refusal.amount
      ? t("checkout.min_order", { zone: refusal.zone, amount: f.money(refusal.amount, refusal.currency ?? undefined, { whole: true }) })
      : fresh?.error ?? null;
  return { quote: fresh?.quote ?? null, error, refusal, loading: !!key && !fresh };
}

/** The food subtotal of the bag (the kitchen's prices; the full bill is the quote's). */
export function foodSubtotal(lines: BagLine[]): number {
  return lines.reduce((a, l) => a + l.unitPrice * l.quantity, 0);
}
