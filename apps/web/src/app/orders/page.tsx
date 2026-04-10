"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Order } from "@bhojango/types";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-50 text-yellow-700",
  confirmed: "bg-blue-50 text-blue-700",
  preparing: "bg-amber-50 text-amber-700",
  ready_for_pickup: "bg-purple-50 text-purple-700",
  picked_up: "bg-indigo-50 text-indigo-700",
  delivered: "bg-green-50 text-green-700",
  cancelled: "bg-red-50 text-red-700",
};

function OrderCard({ order }: { order: Order }) {
  const t = useTranslations("orders");
  const statusLabel = t(`status.${order.status}` as never) as string;
  const colorClass = STATUS_COLORS[order.status] ?? "bg-gray-50 text-gray-700";
  const isActive = !["delivered", "cancelled"].includes(order.status);

  return (
    <Link
      href={`/orders/${order.id}`}
      className="block bg-white rounded-xl p-4 hover:shadow-md transition border border-gray-100"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {t("orderNumber", { id: order.id.slice(0, 8).toUpperCase() })}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {new Date(order.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${colorClass}`}>
          {statusLabel}
        </span>
      </div>

      <p className="text-sm text-gray-700 mb-2">{order.restaurant_name ?? "Restaurant"}</p>
      <p className="text-xs text-gray-500">
        {t("items", { count: order.items?.length ?? 0 })} ·{" "}
        {t("total", { amount: `${order.currency === "INR" ? "₹" : "$"}${order.total?.toFixed(2)}` })}
      </p>

      {isActive && (
        <div className="mt-3 flex items-center gap-1 text-emerald-500 text-xs font-medium">
          <svg className="w-3 h-3 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
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

  const { data, isLoading, isError } = useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const { data } = await api.get("/order/orders?limit=50");
      return data as { items: Order[]; total: number };
    },
    enabled: !!isAuthenticated,
  });

  if (!isAuthenticated) {
    router.replace("/login?redirect=/orders");
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-gray-900 mb-6">{t("title")}</h1>

        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-28 bg-white rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {isError && (
          <div className="text-center py-16">
            <p className="text-gray-500">Failed to load orders. Please try again.</p>
          </div>
        )}

        {data && data.items.length === 0 && (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">📦</div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">{t("noOrders")}</h2>
            <p className="text-gray-500 text-sm mb-6">{t("noOrdersSubtext")}</p>
            <Link
              href="/restaurants"
              className="inline-block px-6 py-2.5 bg-emerald-500 text-white rounded-lg font-semibold hover:bg-emerald-700 transition text-sm"
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
