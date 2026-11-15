"use client";
// After signing in: with no address chosen yet, the default saved address
// becomes the delivery address (the header, the kitchens and the fees follow it).
import { placeFromPoint } from "@/components/AddressBox";
import { authed } from "@/lib/client";
import { setCookie } from "@/lib/i18n";

interface Address {
  id: string;
  label?: string | null;
  street?: string;
  country?: string;
  lat?: number | null;
  lng?: number | null;
  is_default?: boolean;
}

export async function placeFromDefaultAddress(hasPlace: boolean): Promise<void> {
  if (hasPlace) return;
  try {
    const list = await authed<Address[]>("GET", "/api/v1/me/addresses");
    const a = list.find((x) => x.is_default && x.lat != null && x.lng != null);
    if (!a || a.lat == null || a.lng == null) return;
    const p = await placeFromPoint(a.lat, a.lng, [a.label, a.street].filter(Boolean).join(" · ") || undefined);
    setCookie("bg_addr", JSON.stringify({ ...p, country: p.country || a.country || "", address_id: a.id }));
  } catch {
    // no saved addresses (or none yet): the visitor picks one
  }
}
