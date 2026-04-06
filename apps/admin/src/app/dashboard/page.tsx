"use client";

import { useQuery } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

interface KpiData {
  total_orders_today: number;
  total_revenue_today: number;
  active_orders: number;
  new_users_today: number;
  active_drivers: number;
  avg_delivery_time_minutes: number;
  currency: string;
}

function KpiCard({
  label,
  value,
  sub,
  icon,
  trend,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: string;
  trend?: { value: number; positive: boolean };
}) {
  return (
    <div className="bg-gray-900 rounded-xl p-5">
      <div className="flex items-start justify-between mb-3">
        <span className="text-2xl">{icon}</span>
        {trend && (
          <span className={`text-xs font-medium ${trend.positive ? "text-green-400" : "text-red-400"}`}>
            {trend.positive ? "↑" : "↓"} {Math.abs(trend.value)}%
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-sm text-gray-400 mt-0.5">{label}</p>
      {sub && <p className="text-xs text-gray-600 mt-1">{sub}</p>}
    </div>
  );
}

function RecentOrderRow({ order }: { order: Record<string, unknown> }) {
  const statusColors: Record<string, string> = {
    pending: "text-yellow-400",
    confirmed: "text-blue-400",
    preparing: "text-emerald-500",
    picked_up: "text-indigo-400",
    delivered: "text-green-400",
    cancelled: "text-red-400",
  };

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/50 transition">
      <td className="py-3 px-4 text-sm text-gray-300">
        #{String(order.id).slice(0, 8).toUpperCase()}
      </td>
      <td className="py-3 px-4 text-sm text-gray-300">{String(order.restaurant_name ?? "—")}</td>
      <td className="py-3 px-4 text-sm text-gray-300">
        {order.currency === "INR" ? "₹" : "$"}{Number(order.total ?? 0).toFixed(2)}
      </td>
      <td className={`py-3 px-4 text-sm font-medium capitalize ${statusColors[String(order.status)] ?? "text-gray-400"}`}>
        {String(order.status).replace("_", " ")}
      </td>
      <td className="py-3 px-4 text-xs text-gray-500">
        {new Date(String(order.created_at)).toLocaleTimeString()}
      </td>
    </tr>
  );
}

export default function DashboardPage() {
  const { data: kpi, isLoading: kpiLoading } = useQuery({
    queryKey: ["admin-kpi"],
    queryFn: async () => {
      const { data } = await adminApi.get("/order/admin/kpi");
      return data as KpiData;
    },
    refetchInterval: 60_000,
  });

  const { data: recentOrders } = useQuery({
    queryKey: ["admin-recent-orders"],
    queryFn: async () => {
      const { data } = await adminApi.get("/order/orders?limit=10&sort=created_at:desc");
      return data as { items: Record<string, unknown>[] };
    },
    refetchInterval: 30_000,
  });

  const currencySymbol = kpi?.currency === "INR" ? "₹" : "$";

  return (
    <AdminLayout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-500">
            {new Date().toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
          </p>
        </div>

        {/* KPI Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
          {kpiLoading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-gray-900 rounded-xl p-5 h-28 animate-pulse" />
            ))
          ) : (
            <>
              <KpiCard
                label="Orders Today"
                value={kpi?.total_orders_today ?? 0}
                icon="📦"
                trend={{ value: 12, positive: true }}
              />
              <KpiCard
                label="Revenue Today"
                value={`${currencySymbol}${((kpi?.total_revenue_today ?? 0) / 100).toLocaleString()}`}
                icon="💰"
                trend={{ value: 8, positive: true }}
              />
              <KpiCard
                label="Active Orders"
                value={kpi?.active_orders ?? 0}
                icon="🔴"
                sub="Right now"
              />
              <KpiCard
                label="New Users"
                value={kpi?.new_users_today ?? 0}
                icon="👤"
                trend={{ value: 3, positive: true }}
              />
              <KpiCard
                label="Active Drivers"
                value={kpi?.active_drivers ?? 0}
                icon="🚴"
              />
              <KpiCard
                label="Avg Delivery"
                value={`${kpi?.avg_delivery_time_minutes ?? 0} min`}
                icon="⏱️"
                trend={{ value: 2, positive: false }}
              />
            </>
          )}
        </div>

        {/* Recent Orders Table */}
        <div className="bg-gray-900 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-800 flex justify-between items-center">
            <h2 className="font-semibold text-white">Recent Orders</h2>
            <a href="/orders" className="text-sm text-emerald-500 hover:underline">
              View all
            </a>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Order ID", "Restaurant", "Amount", "Status", "Time"].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentOrders?.items.map((order) => (
                  <RecentOrderRow key={String(order.id)} order={order} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
