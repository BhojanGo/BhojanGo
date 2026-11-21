// The account area's data (round 4, website parity): orders and receipts,
// ratings, addresses, saved cards, notification preferences, your data. The
// same API calls as the website's account pages (apps/web/src/app/account).
import { ACTIVE_STATUSES, api, billLineLabel, unwrap, urls, useSession, type CoreSchemas, type OrderStatus, type Translate } from "@bhojango/mobile-core";
import * as Crypto from "expo-crypto";
import { File, Paths } from "expo-file-system";
import * as Location from "expo-location";
import * as Sharing from "expo-sharing";

import { useWhere } from "./where";

export type Order = CoreSchemas["OrderResponse"];
export type Address = CoreSchemas["AddressResponse"];
export type AddressBody = CoreSchemas["AddressCreate"];
export type PaymentMethod = CoreSchemas["PaymentMethodOut"];
export type Prefs = CoreSchemas["NotificationPreferencesOut"];
export type Rating = CoreSchemas["OrderRating"];
export type Area = CoreSchemas["Area"];
export type Reorder = CoreSchemas["ReorderResponse"];

export interface BillLine {
  code: string;
  label: string;
  amount: string;
  funded_by?: string | null;
}
export interface Bill {
  currency: string;
  total: string;
  lines: BillLine[];
  /** R27: refunds on the order and what was paid after them */
  refunds?: { amount: string; kind: string; reason: string; items: string[] }[];
  paid?: string;
}

/** The bill's lines with the website's translated labels (R27: tax lines too; offers keep the rule's name). */
export function billLines(t: Translate, bill: Bill): BillLine[] {
  return bill.lines.map((ln) => ({ ...ln, label: billLineLabel(t, ln) }));
}

export const NOTIFY_KINDS = ["orders", "account", "offers"] as const;
export const NOTIFY_CHANNELS = ["push", "sms", "email"] as const;
export type NotifyKind = (typeof NOTIFY_KINDS)[number];
export type NotifyChannel = (typeof NOTIFY_CHANNELS)[number];

export const isActive = (status: string) => ACTIVE_STATUSES.includes(status as OrderStatus);

/** "#D4X8P1": the first six hex digits of the order id (as on the receipt PDF and the website). */
export function orderCode(id: string): string {
  return `#${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/** The website's words for an order's state (account.status.*). */
export function statusLabel(t: Translate, status: string): string {
  const key = `account.status.${status}`;
  return t(key) === key ? status : t(key);
}

/** "UPI", "Card", "Apple Pay"...: a payment method's name (account.pay.*, app.pay.*), else its code. */
export function payLabel(t: Translate, method: string | null | undefined): string {
  if (!method) return "";
  for (const key of [`account.pay.${method}`, `app.pay.${method}`]) if (t(key) !== key) return t(key);
  return method;
}

/** "Visa", "Mastercard", "Amex": a card brand as the website writes it. */
export const brandName = (b: string) => (b === "amex" ? "Amex" : b.charAt(0).toUpperCase() + b.slice(1));

/** One item of an order as the API stores it. */
export interface OrderItem {
  menu_item_id?: string;
  name?: string;
  quantity?: number;
  options?: (string | { name?: string; option?: string })[];
  total?: number;
  unit_price?: number;
}

export function itemOptions(i: OrderItem): string {
  return (i.options ?? []).map((o) => (typeof o === "string" ? o : o.name ?? o.option)).filter(Boolean).join(", ");
}

export function itemsSummary(o: Order): string {
  return o.items_summary ?? (o.items as OrderItem[]).map((i) => (i.quantity && i.quantity > 1 ? `${i.quantity} × ${i.name}` : i.name)).join(", ");
}

// ── orders ────────────────────────────────────────────────────────────────────

export async function listOrders(limit = 50): Promise<Order[]> {
  const r = unwrap(await api.core.GET("/api/v1/orders", { params: { query: { limit } } })) as { items: Order[] };
  // An order still waiting for payment isn't an order yet.
  return r.items.filter((o) => o.status !== "pending_payment");
}

export async function getOrder(id: string): Promise<Order> {
  return unwrap(await api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } }));
}

/** The fair bill the pricing engine kept for the order (null when it has none). */
export async function getBill(id: string): Promise<Bill | null> {
  try {
    return unwrap(await api.core.GET("/api/v1/pricing/orders/{order_id}/bill", { params: { path: { order_id: id } } })) as unknown as Bill;
  } catch {
    return null;
  }
}

/** Your rating of the order, or null when it isn't rated yet. */
export async function getRating(id: string): Promise<Rating | null> {
  const r = unwrap(await api.core.GET("/api/v1/orders/{order_id}/rating", { params: { path: { order_id: id } } }));
  return r && r.stars ? r : null;
}

/** Rate (or, within 7 days, re-rate) a delivered order. */
export async function rateOrder(id: string, stars: number, comment: string): Promise<Rating> {
  return unwrap(await api.core.POST("/api/v1/orders/{order_id}/rating", {
    params: { path: { order_id: id } }, body: { stars, comment: comment.trim() || null },
  }));
}

export async function reorder(id: string): Promise<Reorder> {
  return unwrap(await api.core.POST("/api/v1/orders/{order_id}/reorder", { params: { path: { order_id: id } } }));
}

/**
 * The receipt PDF (a tax invoice where the bill carries GST) from the API, saved
 * in the app's cache and handed to the phone's share sheet (save to Files, open
 * in a PDF viewer, mail it). The download sends the session's token.
 */
export async function shareReceipt(id: string, title: string): Promise<void> {
  const token = useSession.getState().accessToken ?? "";
  const dest = new File(Paths.cache, `bhojango-${orderCode(id).slice(1)}.pdf`);
  const file = await File.downloadFileAsync(`${urls.core}/api/v1/orders/${encodeURIComponent(id)}/receipt.pdf`, dest, {
    headers: { Authorization: `Bearer ${token}` }, idempotent: true,
  });
  await share(file.uri, "application/pdf", title);
}

// ── your data ─────────────────────────────────────────────────────────────────

/** Everything the account holds (GET /me/export) as a JSON file, through the share sheet. */
export async function shareMyData(title: string): Promise<void> {
  const data = unwrap(await api.core.GET("/api/v1/me/export"));
  const file = new File(Paths.cache, "bhojango-data.json");
  if (file.exists) file.delete();
  file.create();
  await file.write(JSON.stringify(data, null, 2));
  await share(file.uri, "application/json", title);
}

async function share(uri: string, mimeType: string, dialogTitle: string) {
  if (!(await Sharing.isAvailableAsync())) throw new Error("sharing");
  await Sharing.shareAsync(uri, { mimeType, dialogTitle, UTI: mimeType === "application/pdf" ? "com.adobe.pdf" : "public.json" });
}

// ── addresses ─────────────────────────────────────────────────────────────────

export async function listAddresses(): Promise<Address[]> {
  return unwrap(await api.core.GET("/api/v1/me/addresses")) as Address[];
}

export async function saveAddress(id: string | null, body: AddressBody): Promise<Address> {
  return id
    ? unwrap(await api.core.PATCH("/api/v1/me/addresses/{address_id}", { params: { path: { address_id: id } }, body }))
    : unwrap(await api.core.POST("/api/v1/me/addresses", { body }));
}

export async function makeDefaultAddress(id: string): Promise<void> {
  unwrap(await api.core.POST("/api/v1/me/addresses/{address_id}/default", { params: { path: { address_id: id } } }));
}

export async function deleteAddress(id: string): Promise<void> {
  unwrap(await api.core.DELETE("/api/v1/me/addresses/{address_id}", { params: { path: { address_id: id } } }));
}

/** Deliver to this saved address from now on (the home screen, the country). */
export function followAddress(a: Address) {
  if (a.lat == null || a.lng == null) return;
  void useWhere.getState().setPoint({
    label: `${a.label} · ${a.street.split(",").slice(-1)[0]?.trim() || a.city}`, addressId: a.id,
    lat: a.lat, lng: a.lng, street: a.street, city: a.city, state: a.state, zip: a.postal_code, country: a.country,
  }).catch(() => undefined);
}

/** Areas Markets knows by name (the website's address search; no paid geocoder). */
export async function searchAreas(q: string): Promise<Area[]> {
  return unwrap(await api.core.GET("/api/v1/markets/areas", { params: { query: { q } } })) as Area[];
}

/** A point on the map with what Markets knows about it. */
export interface Pin {
  lat: number;
  lng: number;
  country: string;
  label: string;
  city?: string;
  state?: string;
  postal?: string;
  street?: string;
}

/** Where the phone is (asks for permission when tapped), named by Markets (zone, city) and the phone's geocoder. */
export async function pinHere(): Promise<Pin> {
  const perm = await Location.requestForegroundPermissionsAsync();
  if (perm.status !== "granted") throw new Error("location");
  const pos = await Location.getCurrentPositionAsync({});
  const { latitude: lat, longitude: lng } = pos.coords;
  const [loc, geo] = await Promise.all([
    api.core.GET("/api/v1/markets/locate", { params: { query: { lat, lng } } }).then(unwrap).catch(() => null),
    Location.reverseGeocodeAsync(pos.coords).then((g) => g[0] ?? null).catch(() => null),
  ]);
  const city = loc?.city_name ?? geo?.city ?? "";
  return {
    lat, lng, country: loc?.country_code ?? geo?.isoCountryCode ?? "",
    label: [loc?.zone_name, city].filter(Boolean).join(", ") || [geo?.street, geo?.city].filter(Boolean).join(", "),
    city, state: geo?.region ?? undefined, postal: geo?.postalCode ?? undefined,
    street: [geo?.streetNumber, geo?.street].filter(Boolean).join(" ") || undefined,
  };
}

// ── payment methods ───────────────────────────────────────────────────────────

export async function listPaymentMethods(): Promise<PaymentMethod[]> {
  return unwrap(await api.core.GET("/api/v1/me/payment-methods"));
}

export async function makeDefaultPaymentMethod(id: string): Promise<void> {
  unwrap(await api.core.POST("/api/v1/me/payment-methods/{payment_method_id}/default", { params: { path: { payment_method_id: id } } }));
}

export async function removePaymentMethod(id: string): Promise<void> {
  unwrap(await api.core.DELETE("/api/v1/me/payment-methods/{payment_method_id}", { params: { path: { payment_method_id: id } } }));
}

/**
 * Test environments run the fake payment provider: save a test card (a random
 * pm_fake_ token plus the brand, last 4 digits and expiry). Never a card number.
 */
export async function addTestCard(card: { brand: string; last4: string; exp_month: number; exp_year: number }): Promise<void> {
  const token = `pm_fake_${Array.from(Crypto.getRandomBytes(12), (b) => b.toString(16).padStart(2, "0")).join("")}`;
  unwrap(await api.core.POST("/api/v1/me/payment-methods", { body: { provider: "fake", provider_token: token, ...card } }));
}

// ── notifications ─────────────────────────────────────────────────────────────

export async function getPrefs(): Promise<Prefs> {
  return unwrap(await api.core.GET("/api/v1/me/notification-preferences"));
}

export async function setPref(kind: NotifyKind, channel: NotifyChannel, value: boolean): Promise<Prefs> {
  return unwrap(await api.core.PUT("/api/v1/me/notification-preferences", { body: { [kind]: { [channel]: value } } }));
}

// ── profile ───────────────────────────────────────────────────────────────────

export async function updateMe(body: CoreSchemas["UserUpdateRequest"]): Promise<void> {
  const me = unwrap(await api.core.PATCH("/api/v1/users/me", { body }));
  useSession.setState({ user: me });
}
