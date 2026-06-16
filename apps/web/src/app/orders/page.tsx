"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Order } from "@bhojango/types";

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

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  preparing: "Preparing",
  almost_ready: "Almost ready",
  ready_for_pickup: "Ready for pickup",
  picked_up: "Picked up",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

type DisplayOrder = Order & {
  items?: Array<{ quantity?: number }>;
  total?: number;
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

function OrderCard({ order }: { order: DisplayOrder }) {
  const t = useTranslations("orders");
  const statusLabel = STATUS_LABELS[order.status] ?? (t(`status.${order.status}` as never) as string);
  const colorClass = STATUS_COLORS[order.status] ?? "bg-gray-50 text-gray-700 dark:bg-gray-900 dark:text-gray-300";
  const isActive = !["delivered", "cancelled"].includes(order.status);
  const itemCount = order.items?.reduce((sum, item) => sum + Number(item.quantity ?? 0), 0) ?? 0;

  return (
    <Link
      href={`/orders/${order.id}`}
      className="block rounded-xl border border-gray-100 bg-white p-4 transition hover:shadow-md dark:border-gray-800 dark:bg-gray-900"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {t("orderNumber", { id: order.id.slice(0, 8).toUpperCase() })}
          </p>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {new Date(order.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${colorClass}`}>
          {statusLabel}
        </span>
      </div>

      <p className="mb-2 text-sm text-gray-700 dark:text-gray-300">{order.restaurant_name ?? "Restaurant"}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {t("items", { count: itemCount })} · {t("total", { amount: formatMoney(order.currency, order.total) })}
      </p>

      {isActive && (
        <div className="mt-3 flex items-center gap-1 text-xs font-medium text-emerald-500">
          <svg className="h-3 w-3 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" />
          </svg>
          {t("track")}
        </div>
      )}
    </Link>
  );
}

export default function OrdersPage() {
  const t = useTranslations("orders");
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const authReady = usePersistedAuthReady();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const { data } = await api.get("/order/orders?limit=50");
      return data as { items: DisplayOrder[]; total: number };
    },
    enabled: authReady && !!isAuthenticated,
  });

  useEffect(() => {
    if (!authReady) return;
    if (!isAuthenticated) {
      router.replace("/login?redirect=/orders");
    }
  }, [authReady, isAuthenticated, router]);

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-950">
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading orders...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div data-testid="orders-ready" className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="mx-auto max-w-2xl px-4 py-6">
        <h1 className="mb-6 text-xl font-bold text-gray-900 dark:text-gray-100">{t("title")}</h1>

        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-28 animate-pulse rounded-xl bg-white dark:bg-gray-900" />
            ))}
          </div>
        )}

        {isError && (
          <div className="py-16 text-center">
            <p className="text-gray-500 dark:text-gray-400">Failed to load orders. Please try again.</p>
          </div>
        )}

        {data && data.items.length === 0 && (
          <div className="py-16 text-center">
            <div className="mb-4 text-5xl">📦</div>
            <h2 className="mb-2 text-lg font-semibold text-gray-900 dark:text-gray-100">{t("noOrders")}</h2>
            <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">{t("noOrdersSubtext")}</p>
            <Link
              href="/restaurants"
              className="inline-block rounded-lg bg-emerald-500 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700"
            >
              Order Now
            </Link>
          </div>
        )}

        {data && data.items.length > 0 && (
          <div className="space-y-3">
            {data.items.map((order) => (
              <OrderCard key={order.id} order={order} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
