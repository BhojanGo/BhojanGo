"use client";
// Small helpers the account pages share: order codes, kitchen paths, a
// kitchen's public card (cover, city) by slug, and saving a file.

import { ACTIVE_STATUSES, type CoreSchemas, type OrderStatus } from "@bhojango/api-client";
import { useEffect, useState } from "react";

import { KitchenPhoto } from "@/components/KitchenPhoto";
import { urls } from "@/lib/client";

/** An order as the history lists it (GET /orders adds the kitchen's slug and a one-line summary). */
export type Order = CoreSchemas["OrderResponse"] & { restaurant_slug?: string | null; items_summary?: string | null };

export const isActive = (s: string) => ACTIVE_STATUSES.includes(s as OrderStatus);

/** A photo from data (a kitchen's photo_url, a dish's photo), else the branded tile (no text:
 * the kitchen's name is beside or on top of it). `glyph={false}` under overlaid text. */
export function Thumb({ src, className, glyph = true }: { src: string | null; className: string; glyph?: boolean }) {
  return <KitchenPhoto src={src} className={className} glyph={glyph} />;
}

/** "#D4X8P1": the first six hex digits of the order id (as on the receipt PDF). */
export function orderCode(id: string): string {
  return `#${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/** The slug rule the website uses for cities: lower-case, non-alphanumerics → "-". */
export function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/** A kitchen's page: /{country}/{city}/{kitchen}. */
export function kitchenPath(country: string, city: string, slug: string): string {
  return `/${country.toLowerCase()}/${slugify(city)}/${slug}`;
}

export interface KitchenBrief {
  id: string;
  slug: string;
  name: string;
  city: string;
  country: string;
  currency: string;
  cover_url: string | null;
  /** What to show: the cover, else the first dish photo, else the cuisine's library photo (R8). */
  photo_url?: string | null;
}

// One request per kitchen per page load, shared by every row that shows it.
const briefs = new Map<string, Promise<KitchenBrief | null>>();

/** A kitchen's public card by id (its public page data: cover, city, country, currency). */
export function kitchenBrief(id: string): Promise<KitchenBrief | null> {
  let p = briefs.get(id);
  if (!p) {
    p = fetch(`${urls.core}/api/v1/restaurants/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? (r.json() as Promise<KitchenBrief>) : null))
      .catch(() => null);
    briefs.set(id, p);
  }
  return p;
}

/** The kitchen's public card once loaded (null until then, or if it's gone). */
export function useKitchenBrief(id: string | null | undefined): KitchenBrief | null {
  const [got, setGot] = useState<{ id: string; brief: KitchenBrief | null } | null>(null);
  useEffect(() => {
    if (!id) return;
    let live = true;
    void kitchenBrief(id).then((brief) => live && setGot({ id, brief }));
    return () => {
      live = false;
    };
  }, [id]);
  return got && got.id === id ? got.brief : null;
}

/** Hand the browser a file to save. */
export function saveFile(blob: Blob, name: string) {
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}
