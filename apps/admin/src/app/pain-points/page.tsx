"use client";

import { useQuery } from "@tanstack/react-query";

import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

interface PainPointMetrics {
  total_orders: number;
  total_platform_revenue: number;
  long_distance_orders: number;
  long_distance_rate: number;
  avg_estimated_prep_minutes: number;
  avg_delivery_distance_km: number;
  orders_by_status: Record<string, number>;
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase font-semibold">{label}</p>
      <p className="text-2xl font-bold text-white mt-2">{value}</p>
      {hint && <p className="text-xs text-gray-500 mt-1">{hint}</p>}
    </div>
  );
}

export default function PainPointsPage() {
  const { data, isError } = useQuery({
    queryKey: ["admin-pain-points"],
    queryFn: async () => {
      const { data } = await adminApi.get("/order/orders/admin/pain-points");
      return data as PainPointMetrics;
    },
    refetchInterval: 60_000,
  });

  const statuses = Object.entries(data?.orders_by_status ?? {});
  const maxStatus = Math.max(1, ...statuses.map(([, c]) => c));

  return (
    <AdminLayout>
      <div className="p-6">
        <h1 className="text-xl font-bold text-white mb-1">Pain-Point Analytics</h1>
        <p className="text-sm text-gray-500 mb-6">
          Driver deadhead risk, restaurant readiness, and platform revenue at a glance.
        </p>

        {isError && (
          <div className="bg-red-950/40 border border-red-900 text-red-300 text-sm rounded-lg px-4 py-3 mb-6">
            Could not load metrics.
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <Stat label="Total orders" value={(data?.total_orders ?? 0).toLocaleString()} />
          <Stat
            label="Platform revenue"
            value={`$${(data?.total_platform_revenue ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
            hint="Commission across all models"
          />
          <Stat
            label="Long-distance orders"
            value={`${((data?.long_distance_rate ?? 0) * 100).toFixed(1)}%`}
            hint={`${data?.long_distance_orders ?? 0} flagged (deadhead risk)`}
          />
          <Stat
            label="Avg delivery distance"
            value={`${(data?.avg_delivery_distance_km ?? 0).toFixed(1)} km`}
            hint={`Avg prep ~${Math.round(data?.avg_estimated_prep_minutes ?? 0)} min`}
          />
        </div>

        <div className="bg-gray-900 rounded-xl p-5">
          <h2 className="font-semibold text-white mb-4">Orders by status</h2>
          {statuses.length > 0 ? (
            <div className="space-y-3">
              {statuses.map(([status, count]) => (
                <div key={status} className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-32 truncate capitalize">{status.replace(/_/g, " ")}</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-2.5">
                    <div className="bg-emerald-600 h-2.5 rounded-full transition-all" style={{ width: `${(count / maxStatus) * 100}%` }} />
                  </div>
                  <span className="text-xs text-gray-300 w-12 text-right">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600">No order data yet.</p>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
