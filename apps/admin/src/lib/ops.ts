// The admin console's data beyond Markets (P21): the overview, orders, partners,
// rider documents, dispatch, refunds, rules, finance and admins. Everything goes
// through core_api (/api/user/*) or realtime (/api/realtime/*), and every
// endpoint checks the caller's role and scope; this file only shapes the data.
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";

import { adminApi } from "@/lib/api";

/** The scope in the URL (?scope=IN-TG-HYD), "*" when absent. */
export function useScope(): string {
  return useSearchParams().get("scope") ?? "*";
}

export function money(v: number | string | null | undefined, currency: string, decimals = 0): string {
  const n = Number(v ?? 0);
  const locale = currency === "INR" ? "en-IN" : "en-US";
  return n.toLocaleString(locale, { style: "currency", currency, maximumFractionDigits: decimals, minimumFractionDigits: decimals });
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
}

export function clock(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase() : "–";
}

// ── overview ─────────────────────────────────────────────────────────────────

export interface Totals {
  live: number; today: number; gmv_today: string; median_delivery_min: number | null; on_time_pct: number | null;
  completed_pct: number | null; refund_pct: number | null; waiting_for_rider: number; late: number; kitchens: number;
}
export interface OCity { code: string; name: string; status: string; totals: Totals }
export interface OState { code: string; name: string; totals: Totals; cities: OCity[] }
export interface Action { kind: string; label: string; detail: string; count: number; scope: string; urgent: boolean }
export interface OCountry {
  code: string; name: string; currency: string; timezone: string; tax: string; payments: string;
  totals: Totals; states: OState[]; needs_action: Action[];
}

export function useOverview(scope: string) {
  return useQuery({
    queryKey: ["ops", "overview", scope],
    queryFn: async () => (await adminApi.get<{ countries: OCountry[]; generated_at: string }>("/user/ops/overview", { params: { scope } })).data,
    refetchInterval: 30_000,
  });
}

// ── orders ───────────────────────────────────────────────────────────────────

export interface OpsOrder {
  id: string; code: string; status: string; restaurant_name: string; market_city: string | null; customer: string; rider: string | null;
  total: string; currency: string; placed_at: string | null; estimated_delivery_time: string | null; minutes_late: number | null;
  waiting_for_rider_min: number | null; flags: string[]; pickup: [number, number] | null;
}

export function useOpsOrders(scope: string, view: "live" | "attention" | "today" | "search", q?: string) {
  return useQuery({
    queryKey: ["ops", "orders", scope, view, q],
    queryFn: async () => (await adminApi.get<OpsOrder[]>("/user/ops/orders", { params: { scope, view, q } })).data,
    refetchInterval: view === "search" ? false : 15_000,
    enabled: view !== "search" || Boolean(q && q.length >= 3),
  });
}

export interface OrderDetail {
  id: string; status: string; restaurant_name: string; customer_id: string; driver_id: string | null; market_city: string | null;
  items: { name: string; quantity: number; unit_price: number; total: number; options?: string[]; menu_item_id: string }[];
  status_history: { status: string; at: string; by?: string }[]; total: number; currency: string; tip: number;
  delivery_address: Record<string, string>; special_instructions: string | null; estimated_delivery_time: string | null;
  placed_at: string | null; created_at: string; rider?: { first_name?: string } | null;
}

export interface Refund { id: string; amount: number; reason: string | null; fault?: string | null; status: string; created_at: string; lines?: unknown[] }

export const REFUND_REASONS: { value: string; label: string; fault: string }[] = [
  { value: "missing_item", label: "Missing item", fault: "kitchen" },
  { value: "wrong_item", label: "Wrong item", fault: "kitchen" },
  { value: "quality", label: "Quality", fault: "kitchen" },
  { value: "late", label: "Late", fault: "delivery" },
  { value: "damaged_in_transit", label: "Damaged in transit", fault: "delivery" },
  { value: "rider_issue", label: "Rider issue", fault: "delivery" },
  { value: "goodwill", label: "Goodwill", fault: "platform" },
];

// ── dispatch ─────────────────────────────────────────────────────────────────

export interface MapRider { rider_id: string; lat: number; lng: number; at: string; km: number; status: string; order_id: string | null }
export interface Sos { id: string; rider_id: string; order_id: string | null; lat: number | null; lng: number | null; note: string | null; at: string }

export function useDispatch(city: string | null) {
  return useQuery({
    queryKey: ["dispatch", city],
    queryFn: async () => (await adminApi.get<{ centre: [number, number]; riders: MapRider[]; sos: Sos[] }>("/realtime/dispatch/riders", { params: { city } })).data,
    enabled: Boolean(city),
    refetchInterval: 10_000,
  });
}

// ── partners ─────────────────────────────────────────────────────────────────

export interface Kitchen {
  id: string; name: string; slug: string; city: string; country: string; status: string; cuisine_types: string[]; rating: number;
  fssai_number?: string | null; fssai_expires_on?: string | null; is_open?: boolean; created_at?: string; address?: Record<string, string>;
}

export interface RiderDoc {
  id: string; rider_id: string; rider_name: string; rider_phone: string | null; country: string; kind: string; status: string;
  file_key: string | null; note: string | null; submitted_at: string;
}

export const DOC_LABELS: Record<string, string> = { licence: "Driving licence", insurance: "Vehicle insurance", background_check: "Background check" };

// ── rules ────────────────────────────────────────────────────────────────────

export interface Rule {
  id: string; rule_key: string; version: number; family: string; template: string; key: string | null; slot: string; name: string | null;
  params: Record<string, unknown>; scope_level: string; scope_id: string; market_scope: string; status: string;
  effective_from: string; effective_to: string | null; created_by: string; created_at: string;
}

export const FAMILIES: { key: string; label: string }[] = [
  { key: "delivery_fee", label: "Delivery fees" },
  { key: "customer_fee", label: "Customer fees" },
  { key: "tax", label: "Taxes" },
  { key: "commission", label: "Commissions" },
  { key: "rider_pay", label: "Rider pay" },
  { key: "business", label: "Business rules" },
  { key: "promotion", label: "Promotions" },
];

export function apiMessage(e: unknown): string {
  const err = e as { response?: { data?: { detail?: unknown } } };
  const d = err.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object" && "message" in d) return String((d as { message: string }).message);
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  return "Something went wrong. Try again.";
}
