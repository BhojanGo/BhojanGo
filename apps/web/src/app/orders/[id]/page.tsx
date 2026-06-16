"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Order } from "@bhojango/types";

const STATUS_STEPS = [
  "pending",
  "confirmed",
  "preparing",
  "almost_ready",
  "ready_for_pickup",
  "picked_up",
  "delivered",
] as const;

const STATUS_LABELS: Record<string, string> = {
  pending: "Order placed",
  confirmed: "Restaurant accepted",
  preparing: "Preparing",
  almost_ready: "Almost ready",
  ready_for_pickup: "Ready for pickup",
  picked_up: "Picked up",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-300",
  confirmed: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300",
  preparing: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
  almost_ready: "bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300",
  ready_for_pickup: "bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300",
  picked_up: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300",
  delivered: "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300",
  cancelled: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300",
};

interface FeeBreakdown {
  food_subtotal: number;
  delivery_fee: number;
  platform_fee: number;
  restaurant_payout: number;
  tip: number;
  taxes: number;
  discount: number;
  total: number;
  currency: string;
}

interface OrderTimeline {
  order_id: string;
  status: string;
  estimated_prep_minutes: number;
  restaurant_accepted_at: string | null;
  actual_ready_at: string | null;
  timeline: { status: string; at: string | null }[];
}

type TrackingMessage = {
  type: "location_update" | "status_update" | "ping";
  lat?: number;
  lng?: number;
  status?: string;
  driver_name?: string;
  eta_minutes?: number;
};

type DisplayOrderItem = {
  menu_item_id: string;
  name: string;
  quantity: number;
  price?: number;
  unit_price?: number;
  total?: number;
  subtotal?: number;
  image_url?: string | null;
  customizations?: unknown[];
};

type DisplayOrder = Omit<Order, "items"> & {
  items?: DisplayOrderItem[];
  platform_fee?: number;
  restaurant_payout?: number;
};

function usePersistedAuthReady(): boolean {
  const [storesReady, setStoresReady] = useState(() => {
    if (typeof window === "undefined") return false;
    return useAuthStore.persist.hasHydrated();
  });

  useEffect(() => {
    let cancelled = false;
    const markReadyIfHydrated = () => {
      if (!cancelled && useAuthStore.persist.hasHydrated()) {
        setStoresReady(true);
      }
    };
    markReadyIfHydrated();
    const unsubscribeAuth = useAuthStore.persist.onFinishHydration(markReadyIfHydrated);
    return () => {
      cancelled = true;
      unsubscribeAuth();
    };
  }, []);

  return storesReady;
}

function formatMoney(currency: string | undefined, amount: number | undefined): string {
  const symbol = currency === "INR" ? "₹" : "$";
  return `${symbol}${Number(amount ?? 0).toFixed(2)}`;
}

function getItemTotal(item: DisplayOrderItem): number {
  if (typeof item.total === "number") return item.total;
  if (typeof item.subtotal === "number") return item.subtotal;
  if (typeof item.price === "number") return item.price * Number(item.quantity ?? 0);
  if (typeof item.unit_price === "number") return item.unit_price * Number(item.quantity ?? 0);
  return 0;
}

function getAddressLine(order: DisplayOrder): string {
  const address = order.delivery_address as unknown as Record<string, unknown> | null | undefined;
  if (!address) return "";
  const street = typeof address.street === "string" ? address.street : "";
  const city = typeof address.city === "string" ? address.city : "";
  const state = typeof address.state === "string" ? address.state : "";
  const zip =
    typeof address.zip === "string"
      ? address.zip
      : typeof address.postal_code === "string"
      ? address.postal_code
      : "";
  return [street, city, [state, zip].filter(Boolean).join(" ")].filter(Boolean).join(", ");
}

function StatusTimeline({ status }: { status: string }) {
  const currentIndex = STATUS_STEPS.indexOf(status as (typeof STATUS_STEPS)[number]);
  const normalizedIndex = currentIndex < 0 ? 0 : currentIndex;

  return (
    <div className="relative">
      <div className="flex justify-between">
        {STATUS_STEPS.map((step, i) => {
          const isPast = i <= normalizedIndex;
          const isCurrent = i === normalizedIndex;
          return (
            <div key={step} className="flex flex-1 flex-col items-center">
              <div
                className={`z-10 h-5 w-5 rounded-full border-2 transition-colors ${
                  isCurrent
                    ? "border-emerald-500 bg-emerald-500"
                    : isPast
                    ? "border-emerald-400 bg-emerald-400"
                    : "border-gray-300 bg-white dark:border-gray-700 dark:bg-gray-900"
                }`}
              />
              <p className={`mt-1 text-center text-xs ${isPast ? "text-emerald-700 dark:text-emerald-300" : "text-gray-400"}`}>
                {STATUS_LABELS[step] ?? step}
              </p>
            </div>
          );
        })}
      </div>
      <div className="absolute left-0 right-0 top-2.5 -z-0 h-0.5 bg-gray-200 dark:bg-gray-800">
        <div
          className="h-full bg-emerald-400 transition-all"
          style={{ width: `${Math.max(0, (normalizedIndex / (STATUS_STEPS.length - 1)) * 100)}%` }}
        />
      </div>
    </div>
  );
}

export default function OrderDetailPage() {
  const t = useTranslations("orders");
  const tTracking = useTranslations("tracking");
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated, accessToken } = useAuthStore();
  const authReady = usePersistedAuthReady();
  const orderId = params.id;
  const justPlaced = searchParams.get("success") === "true";

  const wsRef = useRef<WebSocket | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelNote, setCancelNote] = useState("");
  const [cancelError, setCancelError] = useState("");
  const [cancelMessage, setCancelMessage] = useState("");
  const [tracking, setTracking] = useState<{
    lat?: number;
    lng?: number;
    driverName?: string;
    etaMinutes?: number;
    wsStatus: "connecting" | "connected" | "disconnected";
  }>({ wsStatus: "disconnected" });

  const {
    data: order,
    refetch,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["order", orderId],
    queryFn: async () => {
      const { data } = await api.get(`/order/orders/${orderId}`);
      return data as DisplayOrder;
    },
    enabled: authReady && !!isAuthenticated && !!orderId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || ["delivered", "cancelled"].includes(status)) return false;
      return 30_000;
    },
  });

  const { data: breakdown } = useQuery({
    queryKey: ["order-breakdown", orderId],
    queryFn: async () => {
      const { data } = await api.get(`/order/orders/${orderId}/breakdown`);
      return data as FeeBreakdown;
    },
    enabled: authReady && !!isAuthenticated && !!orderId,
  });

  const { data: timeline } = useQuery({
    queryKey: ["order-timeline", orderId],
    queryFn: async () => {
      const { data } = await api.get(`/order/orders/${orderId}/timeline`);
      return data as OrderTimeline;
    },
    enabled: authReady && !!isAuthenticated && !!orderId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || ["delivered", "cancelled"].includes(status)) return false;
      return 30_000;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.patch(`/order/orders/${orderId}/cancel`, {
        reason: "customer_cancelled",
        note: cancelNote.trim() || undefined,
      });
      return data as DisplayOrder;
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["order", orderId], updated);
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["order-timeline", orderId] });
      setCancelOpen(false);
      setCancelError("");
      setCancelMessage("Order cancelled. Refund handling remains mock/pending in this SPR-03C slice.");
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (typeof detail === "string") {
        setCancelError(detail);
      } else if (detail && typeof detail === "object" && "message" in detail) {
        setCancelError(String((detail as { message?: unknown }).message));
      } else if (err instanceof Error) {
        setCancelError(err.message);
      } else {
        setCancelError("Could not cancel this order. Please try again.");
      }
    },
  });

  useEffect(() => {
    if (!authReady) return;
    if (!isAuthenticated) {
      router.replace(`/login?redirect=/orders/${orderId}`);
    }
  }, [authReady, isAuthenticated, orderId, router]);

  useEffect(() => {
    if (!order || ["delivered", "cancelled"].includes(order.status)) return;
    if (!accessToken) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8004"}/ws/track/${orderId}?token=${accessToken}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    setTracking((prev) => ({ ...prev, wsStatus: "connecting" }));

    ws.onopen = () => setTracking((prev) => ({ ...prev, wsStatus: "connected" }));
    ws.onclose = () => setTracking((prev) => ({ ...prev, wsStatus: "disconnected" }));

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as TrackingMessage;
        if (msg.type === "location_update") {
          setTracking((prev) => ({
            ...prev,
            lat: msg.lat,
            lng: msg.lng,
            driverName: msg.driver_name ?? prev.driverName,
            etaMinutes: msg.eta_minutes ?? prev.etaMinutes,
          }));
        } else if (msg.type === "status_update") {
          void refetch();
        }
      } catch {
        // Ignore malformed demo tracking messages.
      }
    };

    return () => {
      ws.close();
    };
  }, [order, accessToken, orderId, refetch]);

  const canCancel = order ? ["pending", "confirmed"].includes(order.status) : false;
  const isActive = order ? !["delivered", "cancelled"].includes(order.status) : false;
  const currencySymbol = order?.currency === "INR" ? "₹" : "$";
  const statusLabel = order ? STATUS_LABELS[order.status] ?? order.status : "";
  const statusColor = order ? STATUS_COLORS[order.status] ?? "bg-gray-50 text-gray-700" : "";
  const addressLine = order ? getAddressLine(order) : "";
  const itemCount = useMemo(
    () => order?.items?.reduce((sum, item) => sum + Number(item.quantity ?? 0), 0) ?? 0,
    [order]
  );

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-950">
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading order...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (isLoading || !order) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="space-y-3 text-center">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading order...</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-950">
        <div className="max-w-md rounded-xl border border-red-100 bg-white p-6 text-center dark:border-red-900 dark:bg-gray-900">
          <p className="text-sm text-red-600">Failed to load this order.</p>
          <button onClick={() => router.push("/orders")} className="mt-4 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium">
            Back to orders
          </button>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="order-detail-ready" className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="mx-auto max-w-2xl px-4 py-6">
        <div className="mb-6 flex items-center gap-3">
          <button
            onClick={() => router.push("/orders")}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-gray-300 transition hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            aria-label="Back to orders"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              {t("orderNumber", { id: order.id.slice(0, 8).toUpperCase() })}
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {new Date(order.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusColor}`}>{statusLabel}</span>
        </div>

        {justPlaced && (
          <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-900 dark:bg-emerald-950/30">
            <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-200">Order placed successfully</p>
            <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-300">
              This page is the SPR-03C confirmation and tracking entry point.
            </p>
          </div>
        )}

        {cancelMessage && (
          <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
            {cancelMessage}
          </div>
        )}

        {isActive && tracking.wsStatus === "connected" && (
          <div className="mb-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-900 dark:bg-emerald-950/30">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-medium text-emerald-800 dark:text-emerald-200">{tTracking("liveTracking")}</span>
            </div>
            {tracking.etaMinutes && (
              <span className="text-sm text-emerald-700 dark:text-emerald-300">
                {tTracking("eta", { time: tracking.etaMinutes })}
              </span>
            )}
          </div>
        )}

        {tracking.driverName && (
          <div className="mb-4 flex items-center gap-3 rounded-xl bg-white px-4 py-3 dark:bg-gray-900">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 font-semibold text-emerald-700">
              {tracking.driverName[0]}
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">{tTracking("driverAssigned")}</p>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {tTracking("driverName", { name: tracking.driverName })}
              </p>
            </div>
          </div>
        )}

        {order.status !== "cancelled" && (
          <div className="mb-4 rounded-xl bg-white p-5 dark:bg-gray-900">
            <StatusTimeline status={order.status} />
          </div>
        )}

        {order.status === "cancelled" && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900 dark:bg-red-950/30">
            <p className="text-sm font-semibold text-red-700 dark:text-red-200">Order Cancelled</p>
            {order.cancellation_reason && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-300">Reason: {order.cancellation_reason}</p>
            )}
            {order.cancellation_note && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-300">{order.cancellation_note}</p>
            )}
          </div>
        )}

        {isActive && tracking.lat && tracking.lng && (
          <div className="mb-4 flex h-48 items-center justify-center rounded-xl bg-gray-200 dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Driver at {tracking.lat.toFixed(4)}, {tracking.lng.toFixed(4)}
            </p>
          </div>
        )}

        <div className="mb-4 rounded-xl bg-white p-4 dark:bg-gray-900">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-900 dark:text-gray-100">{order.restaurant_name}</p>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{itemCount} item(s)</p>
            </div>
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{formatMoney(order.currency, order.total)}</p>
          </div>
          <div className="space-y-2">
            {order.items?.map((item) => (
              <div key={item.menu_item_id} className="flex justify-between gap-3 text-sm text-gray-700 dark:text-gray-300">
                <span>
                  {item.name} × {item.quantity}
                </span>
                <span>{formatMoney(order.currency, getItemTotal(item))}</span>
              </div>
            ))}
          </div>
          <div className="my-3 h-px bg-gray-100 dark:bg-gray-800" />
          <div className="space-y-1.5">
            <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>Food subtotal</span>
              <span>{currencySymbol}{(breakdown?.food_subtotal ?? order.subtotal ?? 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>Delivery fee</span>
              <span>{currencySymbol}{(breakdown?.delivery_fee ?? order.delivery_fee ?? 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>Platform revenue</span>
              <span>{currencySymbol}{(breakdown?.platform_fee ?? order.platform_fee ?? 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>Taxes</span>
              <span>{currencySymbol}{(breakdown?.taxes ?? order.taxes ?? 0).toFixed(2)}</span>
            </div>
            {(breakdown?.tip ?? order.tip ?? 0) > 0 && (
              <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
                <span>Tip</span>
                <span>{currencySymbol}{(breakdown?.tip ?? order.tip ?? 0).toFixed(2)}</span>
              </div>
            )}
            {(breakdown?.discount ?? order.discount ?? 0) > 0 && (
              <div className="flex justify-between text-sm text-emerald-600">
                <span>Discount</span>
                <span>-{currencySymbol}{(breakdown?.discount ?? order.discount ?? 0).toFixed(2)}</span>
              </div>
            )}
          </div>
          <div className="my-3 h-px bg-gray-100 dark:bg-gray-800" />
          <div className="flex justify-between font-semibold text-gray-900 dark:text-gray-100">
            <span>Total</span>
            <span>{formatMoney(order.currency, breakdown?.total ?? order.total)}</span>
          </div>
        </div>

        {timeline && timeline.timeline.length > 0 && (
          <div className="mb-4 rounded-xl bg-white p-4 dark:bg-gray-900">
            <p className="mb-3 font-semibold text-gray-900 dark:text-gray-100">Order timeline</p>
            <ol className="space-y-3">
              {timeline.timeline.map((entry, i) => (
                <li key={`${entry.status}-${i}`} className="flex items-start gap-3">
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
                  <div className="flex flex-1 justify-between gap-2">
                    <span className="text-sm text-gray-800 dark:text-gray-200">{STATUS_LABELS[entry.status] ?? entry.status}</span>
                    {entry.at && (
                      <span className="whitespace-nowrap text-xs text-gray-400">
                        {new Date(entry.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            {timeline.estimated_prep_minutes > 0 && timeline.actual_ready_at === null && order.status !== "cancelled" && (
              <p className="mt-3 text-xs text-gray-400">Estimated prep time: ~{timeline.estimated_prep_minutes} min</p>
            )}
          </div>
        )}

        {addressLine && (
          <div className="mb-4 rounded-xl bg-white p-4 dark:bg-gray-900">
            <p className="mb-1 text-sm font-semibold text-gray-900 dark:text-gray-100">{t("deliveryAddress")}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">{addressLine}</p>
          </div>
        )}

        <div className="mb-4 rounded-xl bg-white p-4 dark:bg-gray-900">
          <p className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Payment</p>
          <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
            <span>Method</span>
            <span className="font-medium capitalize text-gray-800 dark:text-gray-200">{order.payment_method.replaceAll("_", " ")}</span>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Refund processing is mock/pending in this SPR-03C slice; wallet/card refund orchestration is a later bounded stage.
          </p>
        </div>

        {canCancel && (
          <button
            onClick={() => {
              setCancelOpen(true);
              setCancelError("");
            }}
            className="w-full rounded-xl border border-red-500 py-3 font-semibold text-red-600 transition hover:bg-red-50 dark:hover:bg-red-950/30"
          >
            Cancel Order
          </button>
        )}

        {order.status === "delivered" && (
          <button
            onClick={() => {
              if (order.restaurant_id) router.push(`/restaurants/${order.restaurant_id}`);
            }}
            className="w-full rounded-xl border border-emerald-500 py-3 font-semibold text-emerald-500 transition hover:bg-emerald-50 dark:hover:bg-emerald-950/30"
          >
            {t("reorder")}
          </button>
        )}
      </div>

      {cancelOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl dark:bg-gray-900">
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Cancel this order?</h2>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              This is allowed only while the order is still pending or confirmed.
            </p>
            <label className="mt-4 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Cancellation note optional
              <textarea
                value={cancelNote}
                onChange={(e) => setCancelNote(e.target.value)}
                className="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-gray-700 dark:bg-gray-950"
                rows={3}
                placeholder="Changed my mind"
              />
            </label>
            {cancelError && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{cancelError}</p>}
            <div className="mt-5 flex gap-2">
              <button
                onClick={() => setCancelOpen(false)}
                className="flex-1 rounded-lg border border-gray-300 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                Keep Order
              </button>
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="flex-1 rounded-lg bg-red-600 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
              >
                {cancelMutation.isPending ? "Cancelling..." : "Cancel Order"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
